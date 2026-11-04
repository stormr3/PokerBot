# ==============================================================================
# opponent_model.py — Opponent Modeling & Range Tracking Module
# Owner: Person B
#
# Responsibilities:
# - Track opponent tendencies across duplicate hands (VPIP, PFR, fold frequencies).
# - Track revealed discards and showdown holdings.
# - Provide sampled opponent ranges for equity estimation.
# ==============================================================================

from dataclasses import dataclass, field
import random
from typing import Sequence


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

    def on_discard_result(self, my_discard: str, opp_discard: str, board: list[str]) -> None:
        """Callback triggered when the engine reveals both players' discards."""
        if opp_discard:
            self.discards_seen.append(opp_discard)

    def on_hand_result(self, msg: dict) -> None:
        """Callback triggered at the end of each hand to update frequencies."""
        self.hands_observed += 1
        history = msg.get("history", [])

        # Inspect preflop actions for VPIP and PFR
        vpip = False
        pfr = False
        for entry in history:
            if entry.get("street") == "preflop" and entry.get("actor") == "opp":
                act = entry.get("action")
                if act in ("call", "raise"):
                    vpip = True
                if act == "raise":
                    pfr = True
        if vpip:
            self.vpip_count += 1
        if pfr:
            self.pfr_count += 1

        # Check showdown holdings
        opp_hole = msg.get("opp_hole_cards")
        if opp_hole:
            self.showdown_hands_seen.append(list(opp_hole))

    @property
    def vpip_rate(self) -> float:
        return (self.vpip_count / self.hands_observed) if self.hands_observed > 0 else 0.5

    @property
    def pfr_rate(self) -> float:
        return (self.pfr_count / self.hands_observed) if self.hands_observed > 0 else 0.2

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
