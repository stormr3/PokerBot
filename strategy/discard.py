"""Flop discard decision engine module.

Official Specifications (Protocol Specification Section 4 & 5.4, Rulebook Section 4.4):
- Timing & Flow:
  - After flop betting round, if no player has folded, each player secretly chooses
    one hole card to discard.
  - Both choices are made simultaneously.
  - Both discarded cards are then revealed to both players and removed from play.
  - Discard still takes place if both players are all-in.
  - If a player folds before flop betting ends, there is NO discard.
- Request & Reply:
  - 'discard_request' board contains EXACTLY the 3 flop cards.
  - Bot replies with exactly one line: {"type": "discard", "card": "<card>"} naming
    one of its current 3 hole cards.
- Simultaneous & Hidden Information:
  - Discards are simultaneous and hidden until 'discard_result' is received from the engine.
  - The decision MUST NOT attempt to inspect or anticipate the opponent's private discard.

Implementation Choices (Not Official Rules):
- Retained Hand Evaluation: Testing the 3 candidate 2-card holdings formed by removing
  each card c_i from {c0, c1, c2}.
- Scoring Heuristics: Combining Monte Carlo equity estimates with draw retention bonuses
  (e.g., flush/straight potential) to rank candidates.
- Dynamic Budgeting: Adjusting rollout iterations based on time_left_ms.
These evaluation heuristics are internal strategy choices, not tournament rules.

Dependencies:
- Standard Library: typing
- Strategy modules: strategy.cards, strategy.equity, strategy.opponent
"""

from typing import Any


def evaluate_discard_candidates(
    hole_cards: list[str],
    board: list[str],
    opp_model: Any,
    time_left_ms: int,
) -> dict[str, float]:
    """Calculates expected score for each of the 3 candidate discards.

    Note: Internal implementation choice for candidate ranking.

    Args:
        hole_cards: List of 3 hole card strings (e.g., ['Ah', 'Kd', '7c']).
        board: Exactly the 3 flop cards from discard_request.
        opp_model: Opponent model for sampling simulated opponent holdings.
        time_left_ms: Remaining match time bank in milliseconds.

    Returns:
        dict[str, float]: Mapping from each card to expected retained equity.

    TODO:
        - For each card c_i in hole_cards:
          - Form retained 2-card hand H_i = hole_cards - {c_i}.
          - Adapt simulation budget based on time_left_ms.
          - Run equity simulation against independent opponent discard model
            (simulated opponent discards using only opponent cards + flop board).
          - Calculate draw potential bonus.
          - Assign composite score to candidate c_i.
        - Return dictionary mapping card strings to scores.
    """
    raise NotImplementedError("evaluate_discard_candidates is not yet implemented.")


def choose_discard(
    hole_cards: list[str],
    board: list[str],
    opp_model: Any,
    time_left_ms: int,
) -> dict[str, str]:
    """Selects optimal card to discard and returns candidate discard reply.

    Official Rule:
        Reply must be {"type": "discard", "card": "<card>"} where card is in hole_cards.

    Args:
        hole_cards: List of 3 hole card strings.
        board: Exactly the 3 flop cards.
        opp_model: Opponent model.
        time_left_ms: Remaining match time bank in milliseconds.

    Returns:
        dict[str, str]: Candidate reply dict: {"type": "discard", "card": "<card>"}.
        Must be validated through core.safety.sanitize_discard before emitting.

    TODO:
        - Call evaluate_discard_candidates.
        - Choose card with highest retained equity.
        - Return candidate dictionary {"type": "discard", "card": chosen_card}.
    """
    raise NotImplementedError("choose_discard is not yet implemented.")
