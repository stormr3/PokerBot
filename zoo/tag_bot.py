#!/usr/bin/env python3
"""TagBot: tight-aggressive (tight preflop, 3-bets premium, c-bets ~70% on flop)."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

_ZOO_DIR = str(Path(__file__).resolve().parent)
if _ZOO_DIR not in sys.path:
    sys.path.insert(0, _ZOO_DIR)

from zoo_common import (  # noqa: E402
    BaseBot,
    can_raise,
    count_street_raises,
    hand_percentile,
    raise_pot_frac,
    run_bot,
    simple_action,
)


class TagBot(BaseBot):
    def __init__(
        self,
        open_pct: float = 0.72,       # open top 28%
        threebet_pct: float = 0.88,   # 3-bet top 12%
        cbet_prob: float = 0.70,      # flop c-bet frequency as PFA
        value_eq: float = 0.62,
        seed: int | None = None,
    ) -> None:
        super().__init__(seed=seed)
        self.open_pct = open_pct
        self.threebet_pct = threebet_pct
        self.cbet_prob = cbet_prob
        self.value_eq = value_eq

    def choose_action(self, req: dict) -> dict:
        legal = req.get("legal_actions", [])
        street = req.get("street", "preflop")
        pot = int(req.get("pot", 0))
        to_call = int(req.get("to_call", 0))
        hist = req.get("history", [])
        raise_ok = can_raise(req)

        if street == "preflop":
            pct = hand_percentile(self.hole_cards) if len(self.hole_cards) == 3 else 0.5
            n_raises = count_street_raises(hist, "preflop")
            if to_call <= 0:
                if raise_ok and pct >= max(self.open_pct, 0.75):
                    return raise_pot_frac(req, 0.75)
                return simple_action("check" if "check" in legal else "fold")
            if n_raises == 0:
                if raise_ok and pct >= self.open_pct:
                    return raise_pot_frac(req, 0.75)
                return simple_action("fold" if "fold" in legal else ("check" if "check" in legal else "call"))
            if n_raises == 1:
                if raise_ok and pct >= self.threebet_pct:
                    return raise_pot_frac(req, 0.85)
                if "call" in legal and (pct >= 0.76 or (pct >= 0.64 and to_call <= 12)):
                    return simple_action("call")
                return simple_action("fold" if "fold" in legal else "check")
            # Facing 3-bet or 4-bet
            if raise_ok and pct >= 0.95:
                return raise_pot_frac(req, 1.0)
            if "call" in legal and pct >= 0.84:
                return simple_action("call")
            return simple_action("fold" if "fold" in legal else "check")

        # Postflop
        eq_val = self.postflop_equity(req, flop_samples=80, turn_samples=100, budget_s=0.03)

        if street == "flop" and to_call == 0 and raise_ok:
            pre_raises = [h for h in hist if h.get("street") == "preflop" and h.get("action") == "raise"]
            was_pfa = bool(pre_raises and pre_raises[-1].get("actor") == "me")
            flop_actions = [h for h in hist if h.get("street") == "flop"]
            if was_pfa and not any(h.get("actor") == "me" for h in flop_actions):
                if eq_val >= self.value_eq:
                    return raise_pot_frac(req, 0.60)
                # Value c-bets (~38% of flop PFA hands) + bluff c-bets -> ~cbet_prob overall
                bluff_rate = max(0.0, min(1.0, (self.cbet_prob - 0.35) / 0.65))
                if self.rng.random() < bluff_rate:
                    return raise_pot_frac(req, 0.55)
                return simple_action("check")

        if to_call == 0:
            if raise_ok and eq_val >= self.value_eq:
                return raise_pot_frac(req, 0.65)
            return simple_action("check" if "check" in legal else "call")

        pot_odds = to_call / float(max(1, pot + to_call))
        if raise_ok and eq_val >= 0.80:
            return raise_pot_frac(req, 0.85)
        if "call" in legal and eq_val >= pot_odds + 0.03:
            return simple_action("call")
        return simple_action("fold" if "fold" in legal else "check")

    def choose_discard(self, req: dict) -> str:
        return self.discard_by_equity(req, samples=120, budget_s=0.035)


def main() -> None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--open-pct", type=float, default=0.72)
    p.add_argument("--threebet-pct", type=float, default=0.88)
    p.add_argument("--cbet-prob", type=float, default=0.70)
    p.add_argument("--seed", type=int, default=None)
    args, _ = p.parse_known_args()
    run_bot(TagBot(open_pct=args.open_pct, threebet_pct=args.threebet_pct, cbet_prob=args.cbet_prob, seed=args.seed))


if __name__ == "__main__":
    main()
