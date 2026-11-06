# ==============================================================================
# opponent_model.py — Opponent modeling and preflop range-width classifier
# Owner: Person B
#
# Main output: preflop_width(n_raises) = the percent of all hands the opponent could
# hold when they make the n-th raise of a hand. preflop.py uses it to pick the right
# equity table (EQUITY_TOP<width>).
#
# Why not just use raise frequency? A HIGH raise frequency proves a wide range, but a
# LOW one proves nothing: a tight bot and a random bot that raises 15% of the time both
# look the same. So:
#   * frequency is only a floor on the width (it can widen the estimate, never tighten),
#   * showdown evidence decides how selective their raises are: at showdown we see their
#     two kept cards plus the discard (their original 3 cards); we record that hand's
#     percentile whenever they raised preflop. Raised hands spread over the whole ranking
#     = random raiser (wide); concentrated near the top = genuinely tight.
#   * evidence is blended in slowly (few samples are noisy) and we do not go tighter
#     than PREFLOP_MIN_WIDTH_NO_EVIDENCE until enough showdowns have been seen.
# Every callback is wrapped so a bug here can never crash the bot.
# ==============================================================================

from dataclasses import dataclass, field
import random
import sys
from typing import Sequence

import config

try:
    import preflop_table as _pt
except Exception:  # pragma: no cover - the model still works without evidence
    _pt = None

_ERRORS_LOGGED = 0
_RANDOM_AT_WIDTH = 80.0   # an opponent whose raising range is this wide cannot be selective at all


def _log_err(where: str, err: Exception) -> None:
    global _ERRORS_LOGGED
    if _ERRORS_LOGGED < 5:
        _ERRORS_LOGGED += 1
        print(f"[opponent_model] {where} failed: {type(err).__name__}: {err}", file=sys.stderr)


def _quantile(values: list[float], q: float) -> float:
    s = sorted(values)
    if not s:
        return 0.0
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (pos - lo) * (s[hi] - s[lo])


@dataclass
class OpponentModel:
    """Tracks statistical profile and historical tendencies of the opponent."""

    hands_observed: int = 0
    vpip_count: int = 0             # Voluntarily Put Money In Pot
    pfr_count: int = 0              # Preflop Raise count
    folds_to_raise: int = 0
    raises_faced: int = 0
    discards_seen: list[str] = field(default_factory=list)
    showdown_hands_seen: list[list[str]] = field(default_factory=list)

    # Preflop raise tracking (per opponent decision)
    open_chances: int = 0           # opponent acted with no raise yet this hand
    open_raises: int = 0
    face_chances: int = 0           # opponent acted facing a raise
    face_raises: int = 0
    # Percentile (0..1) of the hands they raised preflop with, seen at showdown
    raised_pcts: list[float] = field(default_factory=list)

    # Postflop behaviour
    post_opps: int = 0        # opp acted with no bet to face (postflop)
    post_bets: int = 0
    faced_bets: int = 0       # opp faced my bet/raise (postflop)
    faced_folds: int = 0
    disc_n: int = 0           # showdowns where we could check their discard
    disc_ok: int = 0          # ... and it matched the heuristic-best keep

    # ------------------------------------------------------------------ callbacks

    def on_discard_result(self, my_discard: str, opp_discard: str, board: list[str]) -> None:
        """Callback triggered when the engine reveals both players' discards."""
        try:
            if opp_discard:
                self.discards_seen.append(opp_discard)
        except Exception as err:
            _log_err("on_discard_result", err)

    def on_hand_result(self, msg: dict) -> None:
        """Callback triggered at the end of each hand to update frequencies."""
        try:
            self.hands_observed += 1
            history = msg.get("history", []) or []

            vpip = False
            pfr = False
            raises_so_far = 0
            opp_raised = False
            for entry in history:
                if entry.get("street") != "preflop":
                    continue
                act = entry.get("action")
                if entry.get("actor") == "opp":
                    if act in ("call", "raise"):
                        vpip = True
                    if act == "raise":
                        pfr = True
                        opp_raised = True
                    if raises_so_far == 0:
                        self.open_chances += 1
                        self.open_raises += act == "raise"
                    else:
                        self.face_chances += 1
                        self.face_raises += act == "raise"
                if act == "raise":
                    raises_so_far += 1
            if vpip:
                self.vpip_count += 1
            if pfr:
                self.pfr_count += 1

            self._postflop_stats(history)
            opp_hole = msg.get("opp_hole_cards")
            if opp_hole:
                self.showdown_hands_seen.append(list(opp_hole))
                try:
                    self._check_discard(msg)
                except Exception as err:
                    _log_err("check_discard", err)
                opp_discard = msg.get("opp_discard")
                if opp_raised and opp_discard and _pt is not None:
                    three = list(opp_hole) + [opp_discard]
                    if len(three) == 3 and len(set(three)) == 3:
                        self.raised_pcts.append(_pt.get_percentile(three))
        except Exception as err:
            _log_err("on_hand_result", err)

    def _postflop_stats(self, history) -> None:
        street, outstanding = None, None
        for e in history:
            st, act, actor = e.get("street"), e.get("action"), e.get("actor")
            if st == "preflop":
                continue
            if st != street:
                street, outstanding = st, None
            if actor == "opp":
                if outstanding == "me":
                    self.faced_bets += 1
                    self.faced_folds += act == "fold"
                else:
                    self.post_opps += 1
                    self.post_bets += act == "raise"
            if act == "raise":
                outstanding = actor
            elif act == "call":
                outstanding = None

    def _check_discard(self, msg) -> None:
        board, hole, d = msg.get("board") or [], msg.get("opp_hole_cards"), msg.get("opp_discard")
        if len(board) < 3 or not hole or not d or len(hole) != 2:
            return
        from equity import keep_score
        from evaluator import CARD_INT
        a, b, dd = CARD_INT[hole[0]], CARD_INT[hole[1]], CARD_INT[d]
        flop = [CARD_INT[c] for c in board[:3]]
        self.disc_n += 1
        if keep_score(a, b, flop) >= max(keep_score(a, dd, flop), keep_score(b, dd, flop)) - 1e-9:
            self.disc_ok += 1

    @property
    def fold_to_bet(self) -> float:
        return (self.faced_folds + 3.0) / (self.faced_bets + 8.0)

    @property
    def agg_freq(self) -> float:
        return (self.post_bets + 2.0) / (self.post_opps + 5.0)

    @property
    def disc_consistency(self) -> float:
        return (self.disc_ok + 0.8 * 5) / (self.disc_n + 5.0)

    @property
    def is_station(self) -> bool:
        return self.faced_bets >= 12 and self.fold_to_bet < 0.25

    # ------------------------------------------------------------------ statistics

    @property
    def vpip_rate(self) -> float:
        return (self.vpip_count / self.hands_observed) if self.hands_observed > 0 else 0.5

    @property
    def pfr_rate(self) -> float:
        return (self.pfr_count / self.hands_observed) if self.hands_observed > 0 else 0.2

    @property
    def open_raise_freq(self) -> float:
        """Raw share of their no-raise-yet decisions that were raises."""
        return self.open_raises / self.open_chances if self.open_chances else 0.0

    def _evidence_width(self) -> float | None:
        """Width implied by the hands they raised with (None until a few samples)."""
        if len(self.raised_pcts) < 3:
            return None
        q = _quantile(self.raised_pcts, config.OPP_EVIDENCE_QUANTILE)
        return 100.0 * (1.0 - q)

    def open_width(self) -> float:
        """Percent of all hands they raise with (their first raise of a hand)."""
        k = config.OPP_FREQ_PRIOR_STRENGTH
        prior = config.DEFAULT_OPP_WIDTH / 100.0
        freq_w = 100.0 * (self.open_raises + k * prior) / (self.open_chances + k)

        width = freq_w
        ev_w = self._evidence_width()
        n = len(self.raised_pcts)
        if ev_w is not None:
            weight = n / float(n + config.OPP_EVIDENCE_PRIOR_STRENGTH)
            width = freq_w + weight * max(0.0, ev_w - freq_w)   # evidence can only widen
        if n < config.OPP_EVIDENCE_MIN_SAMPLES:
            width = max(width, config.PREFLOP_MIN_WIDTH_NO_EVIDENCE)
        return min(100.0, max(config.PREFLOP_MIN_WIDTH, width))

    def preflop_width(self, n_raises: int) -> float:
        """Width (percent of hands) of the opponent's range when they make raise number n.

        n <= 1: their opening raise. n >= 2: re-raises. A selective opponent narrows with
        each raise (PREFLOP_RERAISE_FACTOR); a random one does not narrow at all.
        """
        try:
            w1 = self.open_width()
            if n_raises <= 1:
                return w1
            pivot = config.DEFAULT_OPP_WIDTH
            randomness = min(1.0, max(0.0, (w1 - pivot) / (_RANDOM_AT_WIDTH - pivot)))
            factor = config.PREFLOP_RERAISE_FACTOR + (1.0 - config.PREFLOP_RERAISE_FACTOR) * randomness
            return min(100.0, max(config.PREFLOP_MIN_WIDTH, w1 * factor ** (n_raises - 1)))
        except Exception as err:
            _log_err("preflop_width", err)
            return min(100.0, max(config.PREFLOP_MIN_WIDTH,
                                  config.DEFAULT_OPP_WIDTH * config.PREFLOP_RERAISE_FACTOR ** max(0, n_raises - 1)))

    @property
    def style(self) -> str:
        """Coarse label: unknown / maniac / random_raiser / tight / station / normal."""
        try:
            if self.hands_observed < 15:
                return "unknown"
            n = len(self.raised_pcts)
            ev_w = self._evidence_width()
            if self.open_chances >= 10 and self.open_raise_freq >= 0.70:
                return "maniac"
            if n >= config.OPP_EVIDENCE_MIN_SAMPLES and ev_w is not None:
                if ev_w >= 70 and self.open_raise_freq < 0.40:
                    return "random_raiser"
                if self.open_width() <= 20:
                    return "tight"
            if self.open_raise_freq < 0.10 and self.vpip_rate >= 0.80:
                return "station"
            return "normal"
        except Exception:
            return "unknown"

    def sample_range(
        self,
        available_deck: Sequence[str],
        num_samples: int = 1,
    ) -> list[tuple[str, str]]:
        """Samples simulated opponent 2-card holdings from the available deck pool."""
        samples: list[tuple[str, str]] = []
        deck_list = list(available_deck)
        if len(deck_list) < 2:
            return samples

        for _ in range(num_samples):
            c1, c2 = random.sample(deck_list, 2)
            samples.append((c1, c2))
        return samples
