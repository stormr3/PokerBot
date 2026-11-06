# ==============================================================================
# postflop.py — Flop / Turn / River Decision Engine
# Owner: Person A (to be replaced by the equity-based version)
#
# Moved here unchanged from the old betting.py: check if free, else call, else fold.
# Keep this module self-contained so it can be rewritten without touching preflop.py.
# ==============================================================================

from typing import Any


def decide(req: dict[str, Any], state: Any, opp_model: Any) -> dict[str, Any]:
    """Baseline postflop strategy (placeholder): never folds when it can check/call."""
    legal_actions = req.get("legal_actions", [])

    if "check" in legal_actions:
        return {"type": "action", "action": "check"}

    if "call" in legal_actions:
        return {"type": "action", "action": "call"}

    if "fold" in legal_actions:
        return {"type": "action", "action": "fold"}

    return {"type": "action", "action": legal_actions[0] if legal_actions else "fold"}
