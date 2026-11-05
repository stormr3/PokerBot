# ==============================================================================
# bet_utils.py — Shared betting helpers (raise sizing, legality, safe fallbacks)
# Owner: Shared
#
# Used by preflop.py and postflop.py so neither imports the other.
# ==============================================================================

from typing import Any

from config import DEFAULT_POT_FRACTION


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


def can_raise(req: dict[str, Any]) -> bool:
    """True when raising is legal and the request carries a usable raise range."""
    min_raise = req.get("min_raise")
    max_raise = req.get("max_raise")
    return (
        "raise" in req.get("legal_actions", [])
        and min_raise is not None
        and max_raise is not None
        and max_raise >= min_raise
        and req.get("raises_left", 4) > 0
    )


def raise_action(req: dict[str, Any], pot_fraction: float) -> dict[str, Any]:
    """A legal raise sized by pot_fraction (caller must check can_raise first)."""
    amt = calculate_raise_amount(
        req.get("pot", 0),
        req.get("opp_bet", 0),
        req.get("to_call", 0),
        int(req["min_raise"]),
        int(req["max_raise"]),
        pot_fraction,
    )
    return {"type": "action", "action": "raise", "amount": amt}


def simple(action: str) -> dict[str, Any]:
    return {"type": "action", "action": action}


def check_or_fold(req: dict[str, Any]) -> dict[str, Any]:
    legal = req.get("legal_actions", [])
    if "check" in legal:
        return simple("check")
    if "fold" in legal:
        return simple("fold")
    return simple(legal[0] if legal else "fold")


def call_or_check(req: dict[str, Any]) -> dict[str, Any]:
    legal = req.get("legal_actions", [])
    if "check" in legal:
        return simple("check")
    if "call" in legal:
        return simple("call")
    return simple("fold")
