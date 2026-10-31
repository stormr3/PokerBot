"""Opponent modeling and independent simulation module.

Official Specifications (Protocol Specification Section 3 & 4):
- Discard timing: After flop betting ends, if no player folded, each player secretly
  chooses one hole card to discard. Both choices are made simultaneously.
- Hidden until revealed: Both discards remain hidden until 'discard_result' is sent by the engine.
- Duplicate deals: Every deal is played twice with cards swapped between seats.
  The bot is not told which deals are duplicates and keeps no state between matches;
  the bot must NOT attempt to predict paired hands.

Implementation Choices (Not Official Rules):
- Statistical tracking of opponent tendencies (VPIP, aggression, discard frequencies).
- Sampling plausible opponent holdings from unknown deck cards.
- Simulated opponent discard logic: An independent rational heuristic that evaluates
  the simulated opponent's 3 cards against the flop board WITHOUT inspecting the
  bot's private hole cards.
These modeling choices are internal heuristics, not official competition rules.

Dependencies:
- Standard Library: dataclasses, typing
- NumPy: numpy (for weighted sampling)
"""

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class OpponentModel:
    """Maintains statistical profile of opponent; generates realistic simulation samples."""

    hands_observed: int = 0
    vpip_count: int = 0
    pfr_count: int = 0
    fold_to_raise_count: int = 0
    observed_discards: list[str] = field(default_factory=list)

    def record_hand_history(self, history: list[dict], opp_discard: str | None, opp_hole: list[str] | None) -> None:
        """Updates opponent statistical model from completed hand results.

        Note: Internal implementation choice for learning opponent play styles.

        Args:
            history: Action history of the completed hand.
            opp_discard: Opponent's exposed discard (if discard occurred).
            opp_hole: Opponent's hole cards (if showdown reached).

        TODO:
            - Increment hands_observed.
            - Update VPIP/PFR and discard distributions.
        """
        raise NotImplementedError("OpponentModel.record_hand_history is not yet implemented.")

    def sample_opponent_hole_cards(
        self,
        unknown_card_ids: Sequence[int],
        num_cards: int = 2,
    ) -> list[int]:
        """Samples simulated opponent hole cards from the unknown deck pool.

        Note: Internal implementation choice for Monte Carlo rollouts.

        Args:
            unknown_card_ids: Pool of cards not in bot hand, board, or dead cards.
            num_cards: Number of cards to sample (3 pre-discard, 2 post-discard).

        Returns:
            list[int]: Sampled opponent card integer IDs.

        TODO:
            - Sample num_cards without replacement.
        """
        raise NotImplementedError("OpponentModel.sample_opponent_hole_cards is not yet implemented.")

    def simulate_opponent_discard(
        self,
        opp_hole_ids: Sequence[int],
        flop_board_ids: Sequence[int],
    ) -> int:
        """Simulates an opponent's discard choice independently given their 3 cards and flop.

        Critical Invariant:
            Operates strictly on the simulated opponent cards and public flop board cards.
            Must NOT inspect or access the bot's private hole cards.

        Args:
            opp_hole_ids: 3 simulated opponent card IDs.
            flop_board_ids: 3 community flop card IDs.

        Returns:
            int: The card ID chosen for discard by the simulated opponent.

        TODO:
            - Form the 3 candidate 2-card holdings for the opponent.
            - Evaluate each candidate using fast heuristic (keeping pairs, draws).
            - Return the card ID that yields the lowest retained potential.
        """
        raise NotImplementedError("OpponentModel.simulate_opponent_discard is not yet implemented.")
