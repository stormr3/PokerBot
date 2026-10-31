"""Authoritative game and hand state tracking module.

Official Specifications (Protocol Specification Sections 2–5, Rulebook Section 4):
- Match initialization ('init'):
  - total_hands: 400 (Stage 1), ~1000 (Stage 2).
  - starting_stack: 200 chips per player (resets every hand).
  - small_blind: 1 chip, big_blind: 2 chips.
  - time_bank_ms: (provisional) 60,000 ms (Stage 1), 150,000 ms (Stage 2).
  - per_response_ms: (provisional) 5,000 ms limit for any single reply.
- Hand setup ('new_hand'):
  - hand_id: 1-indexed hand number.
  - seat: "button" (posts small blind 1, acts first preflop, second on later streets)
    or "big_blind" (posts big blind 2). Seats alternate every hand.
  - hole_cards: list of exactly 3 cards preflop.
  - stack, opp_stack: 200 before blinds.
- Action request ('action_request'):
  - street: "preflop", "flop", "turn", "river".
  - board: community cards dealt so far (0 preflop, 3 flop, 4 turn, 5 river).
  - pot: total chips in pot, including bets on current street.
  - my_bet, opp_bet: chips committed by each player on this street.
  - to_call: opp_bet - my_bet (0 means checking is legal).
  - legal_actions: authoritative subset of ["fold", "check", "call", "raise"].
  - min_raise, max_raise: authoritative range of raise-to amounts (present only if raise is legal).
    Raise amount is a "to" amount (total chips committed on current street after action),
    not the increment.
  - raises_left: bets or raises still allowed on this street (max 4 per street; BB is 1st preflop).
  - history: voluntary actions this hand oldest first (blinds omitted).
  - time_left_ms: authoritative remaining time bank.
- Discard request ('discard_request'):
  - Sent to both players at the same time after flop betting ends.
  - Sent ONLY if no player has folded. If a player folded before flop betting ends,
    there is no discard request.
  - If both players are all-in, the remaining board cards are dealt and the discard
    still takes place after the flop.
  - board: exactly the 3 flop cards.
  - Discards are simultaneous and hidden until 'discard_result'.
- Discard result ('discard_result'):
  - my_discard: card you discarded.
  - opp_discard: card opponent discarded. Both discards are public.
  - hole_cards: list of your 2 remaining hole cards.
- Hand result ('hand_result'):
  - result: "fold" or "showdown".
  - net: chips won (positive) or lost (negative).
  - my_hole_cards: your remaining hole cards (3 if hand ended before discard, 2 otherwise).
  - opp_hole_cards: opponent's 2 remaining cards at showdown, or null.
  - opp_discard: opponent discard if discard took place, or null.
- Notice ('notice'):
  - Informational error notice from engine ('malformed', 'illegal_action', 'illegal_discard').
  - No reply is expected.
- Duplicate deals:
  - Every deal is played twice with same cards swapped between seats.
  - The bot is not told which deals are duplicates of each other, keeps no state
    between matches, and must NOT predict paired hands.

Implementation Choices (Not Official Rules):
- Helper methods pot_odds() and stack_to_pot_ratio() are internal strategic
  conveniences; they are not part of the official engine protocol.

Dependencies:
- Standard Library: dataclasses, typing
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameState:
    """Tracks local match and hand state strictly conforming to the protocol specification."""

    # Match configuration from 'init' (time limits marked provisional per Section 8)
    total_hands: int = 400
    starting_stack: int = 200
    small_blind: int = 1
    big_blind: int = 2
    time_bank_ms: int = 60_000  # (provisional)
    per_response_ms: int = 5_000  # (provisional)

    # Hand configuration from 'new_hand'
    hand_id: int = 0
    seat: str = "button"  # "button" or "big_blind"
    hole_cards: list[str] = field(default_factory=list)  # 3 pre-discard, 2 post-discard
    board: list[str] = field(default_factory=list)
    pot: int = 0
    my_bet: int = 0
    opp_bet: int = 0
    to_call: int = 0
    my_stack: int = 200
    opp_stack: int = 200

    # Authoritative action parameters from 'action_request'
    legal_actions: list[str] = field(default_factory=list)
    min_raise: int | None = None
    max_raise: int | None = None
    raises_left: int = 4
    street: str = "preflop"
    history: list[dict[str, Any]] = field(default_factory=list)
    time_left_ms: int = 60_000

    # Discard phase data (discards are simultaneous and hidden until 'discard_result')
    my_discard: str | None = None
    opp_discard: str | None = None

    def update_init(self, msg: dict[str, Any]) -> None:
        """Updates match parameters from the official 'init' message.

        TODO:
            - Store total_hands, starting_stack, small_blind, big_blind, time_bank_ms, per_response_ms.
        """
        raise NotImplementedError("GameState.update_init is not yet implemented.")

    def update_new_hand(self, msg: dict[str, Any]) -> None:
        """Resets per-hand variables and populates data from 'new_hand'.

        TODO:
            - Reset street to 'preflop', clear board and discards.
            - Reset bets and commitments (blinds posted implicitly by engine).
            - Populate hand_id, seat, hole_cards (exactly 3 cards), stack, and opp_stack.
        """
        raise NotImplementedError("GameState.update_new_hand is not yet implemented.")

    def update_action_request(self, msg: dict[str, Any]) -> None:
        """Updates state from authoritative fields in 'action_request'.

        TODO:
            - Update street, board, pot, my_bet, opp_bet, to_call, my_stack, opp_stack.
            - Update legal_actions, min_raise, max_raise, raises_left, history, time_left_ms.
        """
        raise NotImplementedError("GameState.update_action_request is not yet implemented.")

    def update_discard_request(self, msg: dict[str, Any]) -> None:
        """Updates state upon receiving 'discard_request'.

        Official Rule:
            - Sent only if nobody folded before flop betting ends.
            - Sent even if both players are all-in.
            - board contains exactly the 3 flop cards.
            - Discard choices are simultaneous and hidden until discard_result.

        TODO:
            - Update hole_cards (3 cards), board (3 flop cards), pot, stacks, time_left_ms.
        """
        raise NotImplementedError("GameState.update_discard_request is not yet implemented.")

    def update_discard_result(self, msg: dict[str, Any]) -> None:
        """Records public discard outcomes from 'discard_result'.

        Official Rule:
            - Both discarded cards are now public.
            - Updates hole_cards to the 2 remaining hole cards.

        TODO:
            - Record my_discard and opp_discard.
            - Update hole_cards to the 2 remaining cards.
        """
        raise NotImplementedError("GameState.update_discard_result is not yet implemented.")

    def update_hand_result(self, msg: dict[str, Any]) -> None:
        """Updates end-of-hand results from 'hand_result'.

        Official Rule:
            - my_hole_cards contains 3 cards if hand ended before discard, 2 otherwise.
            - opp_hole_cards contains opponent's 2 cards only at showdown, otherwise null.
            - opp_discard contains opponent's discard if discard took place, otherwise null.

        TODO:
            - Record net chips won/lost and showdown outcomes.
        """
        raise NotImplementedError("GameState.update_hand_result is not yet implemented.")

    def update_notice(self, msg: dict[str, Any]) -> None:
        """Records engine notice messages (Section 5.7).

        Official Rule:
            - Informational only; no reply is expected.
            - Logs code ('malformed', 'illegal_action', 'illegal_discard') and applied action.

        TODO:
            - Log notice details to stderr.
        """
        raise NotImplementedError("GameState.update_notice is not yet implemented.")

    def pot_odds(self) -> float:
        """Calculates immediate pot odds: to_call / (pot + to_call).

        Note: Internal implementation convenience; not an official protocol field.

        Returns:
            float: Required equity to call (0.0 if to_call == 0).

        TODO:
            - Return 0.0 if to_call == 0 else to_call / (pot + to_call).
        """
        raise NotImplementedError("GameState.pot_odds is not yet implemented.")

    def stack_to_pot_ratio(self) -> float:
        """Calculates effective Stack-to-Pot Ratio (SPR).

        Note: Internal implementation convenience; not an official protocol field.

        Returns:
            float: Effective remaining stack divided by current pot.

        TODO:
            - Return min(my_stack, opp_stack) / max(1, pot).
        """
        raise NotImplementedError("GameState.stack_to_pot_ratio is not yet implemented.")
