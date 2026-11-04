# ==============================================================================
# state.py — Authoritative Match and Hand State Tracker
# Owner: Shared / Person A
#
# Responsibilities:
# - Maintain comprehensive game state across match and within each hand.
# - Dispatch engine event hooks to OpponentModel.
# - Provide helper calculations (pot odds, stack-to-pot ratio).
# ==============================================================================

from dataclasses import dataclass, field
from typing import Any

from opponent_model import OpponentModel


@dataclass
class GameState:
    """Tracks match configurations, current hand state, and public cards."""

    # Match-level parameters
    total_hands: int = 400
    starting_stack: int = 200
    small_blind: int = 1
    big_blind: int = 2
    time_bank_ms: int = 60_000
    per_response_ms: int = 5_000

    # Hand-level state
    hand_id: int = 0
    seat: str = "button"  # "button" or "big_blind"
    hole_cards: list[str] = field(default_factory=list)  # 3 before discard, 2 after
    board: list[str] = field(default_factory=list)
    pot: int = 0
    my_bet: int = 0
    opp_bet: int = 0
    to_call: int = 0
    my_stack: int = 200
    opp_stack: int = 200

    # Action parameters (from action_request)
    legal_actions: list[str] = field(default_factory=list)
    min_raise: int | None = None
    max_raise: int | None = None
    raises_left: int = 4
    street: str = "preflop"
    history: list[dict[str, Any]] = field(default_factory=list)
    time_left_ms: int = 60_000

    # Discard outcomes
    my_discard: str | None = None
    opp_discard: str | None = None

    def on_init(self, msg: dict[str, Any]) -> None:
        """Updates match configurations from 'init'."""
        self.total_hands = msg.get("total_hands", self.total_hands)
        self.starting_stack = msg.get("starting_stack", self.starting_stack)
        self.small_blind = msg.get("small_blind", self.small_blind)
        self.big_blind = msg.get("big_blind", self.big_blind)
        self.time_bank_ms = msg.get("time_bank_ms", self.time_bank_ms)
        self.per_response_ms = msg.get("per_response_ms", self.per_response_ms)
        self.time_left_ms = self.time_bank_ms

    def on_new_hand(self, msg: dict[str, Any]) -> None:
        """Resets state for a new hand deal from 'new_hand'."""
        self.hand_id = msg.get("hand_id", self.hand_id + 1)
        self.seat = msg.get("seat", "button")
        self.hole_cards = list(msg.get("hole_cards", []))
        self.board = []
        self.street = "preflop"
        self.my_discard = None
        self.opp_discard = None
        self.my_bet = self.small_blind if self.seat == "button" else self.big_blind
        self.opp_bet = self.big_blind if self.seat == "button" else self.small_blind
        self.my_stack = msg.get("stack", self.starting_stack)
        self.opp_stack = msg.get("opp_stack", self.starting_stack)
        self.pot = self.my_bet + self.opp_bet
        self.history = []

    def on_action_request(self, msg: dict[str, Any]) -> None:
        """Updates betting round state from 'action_request'."""
        self.hand_id = msg.get("hand_id", self.hand_id)
        self.street = msg.get("street", self.street)
        self.board = list(msg.get("board", self.board))
        self.pot = msg.get("pot", self.pot)
        self.my_bet = msg.get("my_bet", 0)
        self.opp_bet = msg.get("opp_bet", 0)
        self.to_call = msg.get("to_call", 0)
        self.my_stack = msg.get("my_stack", self.my_stack)
        self.opp_stack = msg.get("opp_stack", self.opp_stack)
        self.legal_actions = list(msg.get("legal_actions", []))
        self.min_raise = msg.get("min_raise")
        self.max_raise = msg.get("max_raise")
        self.raises_left = msg.get("raises_left", 4)
        self.history = list(msg.get("history", []))
        self.time_left_ms = msg.get("time_left_ms", self.time_left_ms)

    def on_discard_request(self, msg: dict[str, Any]) -> None:
        """Updates state upon receiving 'discard_request' post-flop."""
        self.hand_id = msg.get("hand_id", self.hand_id)
        self.hole_cards = list(msg.get("hole_cards", self.hole_cards))
        self.board = list(msg.get("board", self.board))
        self.pot = msg.get("pot", self.pot)
        self.my_stack = msg.get("my_stack", self.my_stack)
        self.opp_stack = msg.get("opp_stack", self.opp_stack)
        self.time_left_ms = msg.get("time_left_ms", self.time_left_ms)

    def on_discard_result(self, msg: dict[str, Any], opp_model: OpponentModel) -> None:
        """Records exposed discards from 'discard_result' and notifies opponent model."""
        self.my_discard = msg.get("my_discard")
        self.opp_discard = msg.get("opp_discard")
        self.hole_cards = list(msg.get("hole_cards", self.hole_cards))
        if opp_model:
            opp_model.on_discard_result(self.my_discard or "", self.opp_discard or "", self.board)

    def on_hand_result(self, msg: dict[str, Any], opp_model: OpponentModel) -> None:
        """Records end of hand outcome and notifies opponent model."""
        if opp_model:
            opp_model.on_hand_result(msg)

    def on_notice(self, msg: dict[str, Any]) -> None:
        """Records informational notice warning from match engine."""
        pass

    def pot_odds(self) -> float:
        """Calculates immediate pot odds: to_call / (pot + to_call)."""
        if self.to_call <= 0:
            return 0.0
        return self.to_call / float(self.pot + self.to_call)

    def stack_to_pot_ratio(self) -> float:
        """Calculates effective Stack-to-Pot Ratio (SPR)."""
        return min(self.my_stack, self.opp_stack) / float(max(1, self.pot))
