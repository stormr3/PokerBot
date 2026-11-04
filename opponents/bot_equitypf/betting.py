# ==============================================================================
# betting.py — Preflop and Postflop Betting Decision Engine
# Owner: Person B
#
# Responsibilities:
# - Determine legal betting action (check, call, raise, fold) for all streets.
# - Size raises within legal bounds [min_raise, max_raise].
# - Incorporate pot odds, canonical equity estimates, position, and opponent modeling.
# ==============================================================================

from typing import Any

from config import (
    DEFAULT_POT_FRACTION,
    PREFLOP_3BET_EQUITY,
    PREFLOP_BB_RAISE_EQUITY,
    PREFLOP_CALL_BUFFER_IP,
    PREFLOP_CALL_BUFFER_OOP,
    PREFLOP_LIMP_EQUITY,
    PREFLOP_OPEN_EQUITY,
    USE_PREFLOP_TABLE,
)
from preflop_table import get_preflop_equity


def calculate_raise_amount(
    pot: int,
    opp_bet: int,
    to_call: int,
    min_raise: int,
    max_raise: int,
    pot_fraction: float = DEFAULT_POT_FRACTION,
) -> int:
    """Computes a legal raise-to amount sized by a fraction of the pot."""
    target = opp_bet + int(pot_fraction * (pot + to_call))
    clamped = max(min_raise, min(max_raise, target))
    return int(clamped)


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
    raises_left = req.get("raises_left", 4)

    # --------------------------------------------------------------------------
    # Preflop Decision Engine (Canonical Equity & Pot-Odds)
    # --------------------------------------------------------------------------
    if street == "preflop" and USE_PREFLOP_TABLE:
        hole_cards = (state.hole_cards if state else None) or req.get("hole_cards", [])
        seat = (state.seat if state else None) or req.get("seat", "button")
        equity = get_preflop_equity(hole_cards)

        can_raise = (
            "raise" in legal_actions
            and min_raise is not None
            and max_raise is not None
            and max_raise >= min_raise
            and raises_left > 0
        )

        # Case 1: Free to check (e.g. BB facing limp or free action)
        if to_call <= 0:
            if equity >= PREFLOP_BB_RAISE_EQUITY and can_raise:
                amt = calculate_raise_amount(pot, opp_bet, to_call, min_raise, max_raise, DEFAULT_POT_FRACTION)
                return {"type": "action", "action": "raise", "amount": amt}
            if "check" in legal_actions:
                return {"type": "action", "action": "check"}

        # Case 2: Button opening (seat == "button" and to_call == 1)
        elif seat == "button" and to_call <= 1:
            if equity >= PREFLOP_OPEN_EQUITY and can_raise:
                amt = calculate_raise_amount(pot, opp_bet, to_call, min_raise, max_raise, 0.75)
                return {"type": "action", "action": "raise", "amount": amt}
            if equity >= PREFLOP_LIMP_EQUITY and "call" in legal_actions:
                return {"type": "action", "action": "call"}
            if "check" in legal_actions:
                return {"type": "action", "action": "check"}
            if "fold" in legal_actions:
                return {"type": "action", "action": "fold"}

        # Case 3: Facing a bet or 3-bet (to_call > 0)
        else:
            pot_odds = to_call / float(pot + to_call)
            pos_buffer = PREFLOP_CALL_BUFFER_IP if seat == "button" else PREFLOP_CALL_BUFFER_OOP

            # Re-raise with strong premium holdings
            if equity >= PREFLOP_3BET_EQUITY and can_raise:
                amt = calculate_raise_amount(pot, opp_bet, to_call, min_raise, max_raise, 0.85)
                return {"type": "action", "action": "raise", "amount": amt}

            # Call if pot odds are satisfied
            if equity >= (pot_odds - pos_buffer) and "call" in legal_actions:
                return {"type": "action", "action": "call"}

            # Insufficient equity: fold (or check if legal)
            if "fold" in legal_actions:
                return {"type": "action", "action": "fold"}
            if "check" in legal_actions:
                return {"type": "action", "action": "check"}

    # --------------------------------------------------------------------------
    # Postflop / Baseline Decision Engine
    # --------------------------------------------------------------------------
    if "check" in legal_actions:
        return {"type": "action", "action": "check"}

    if "call" in legal_actions:
        return {"type": "action", "action": "call"}

    if "fold" in legal_actions:
        return {"type": "action", "action": "fold"}

    return {"type": "action", "action": legal_actions[0] if legal_actions else "fold"}
