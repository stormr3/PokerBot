# ==============================================================================
# betting.py — Preflop and Postflop Betting Decision Engine
# Owner: Person B
#
# Responsibilities:
# - Determine legal betting action (check, call, raise, fold) for all streets.
# - Size raises within legal bounds [min_raise, max_raise].
# - Incorporate pot odds, equity estimates, position, and opponent modeling.
# ==============================================================================

from typing import Any

from config import DEFAULT_POT_FRACTION, USE_PREFLOP_TABLE
from preflop_table import get_preflop_recommendation


def calculate_raise_amount(
    pot: int,
    opp_bet: int,
    to_call: int,
    min_raise: int,
    max_raise: int,
    pot_fraction: float = DEFAULT_POT_FRACTION,
) -> int:
    """Computes a legal raise-to amount sized by a fraction of the pot."""
    # Target total commitment on this street
    target = opp_bet + int(pot_fraction * (pot + to_call))
    return max(min_raise, min(max_raise, target))


def decide(req: dict[str, Any], state: Any, opp_model: Any) -> dict[str, Any]:
    """Generates a legal action dictionary in response to an action_request.

    Args:
        req: Official engine action_request message dictionary.
        state: GameState instance.
        opp_model: OpponentModel instance.

    Returns:
        dict: Format {"type": "action", "action": "...", ["amount": ...]}
    """
    legal_actions = req.get("legal_actions", [])
    street = req.get("street", "preflop")
    to_call = req.get("to_call", 0)
    pot = req.get("pot", 0)
    opp_bet = req.get("opp_bet", 0)
    min_raise = req.get("min_raise")
    max_raise = req.get("max_raise")

    # Preflop decision branch
    if street == "preflop" and USE_PREFLOP_TABLE and state:
        hole_cards = state.hole_cards or req.get("hole_cards", [])
        rec = get_preflop_recommendation(hole_cards, state.seat, to_call)

        if rec == "raise" and "raise" in legal_actions and min_raise is not None and max_raise is not None:
            amt = calculate_raise_amount(pot, opp_bet, to_call, min_raise, max_raise, 0.75)
            return {"type": "action", "action": "raise", "amount": amt}
        if rec in legal_actions:
            return {"type": "action", "action": rec}

    # Postflop / standard baseline:
    # Check if free; call if reasonable; fold only if facing bet and unable to call
    if "check" in legal_actions:
        return {"type": "action", "action": "check"}

    if "call" in legal_actions:
        return {"type": "action", "action": "call"}

    if "fold" in legal_actions:
        return {"type": "action", "action": "fold"}

    return {"type": "action", "action": legal_actions[0] if legal_actions else "fold"}
