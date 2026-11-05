# ==============================================================================
# betting.py — Street router
# Owner: Shared
#
# Thin dispatcher: preflop goes to preflop.decide(), every other street to
# postflop.decide(). Shared helpers live in bet_utils.py.
# ==============================================================================

from typing import Any

import config
import postflop
import preflop
from bet_utils import calculate_raise_amount  # noqa: F401  (re-exported for compatibility)


def decide(req: dict[str, Any], state: Any, opp_model: Any) -> dict[str, Any]:
    """Generates a legal action dictionary in response to an action_request."""
    if req.get("street", "preflop") == "preflop" and config.USE_PREFLOP_TABLE:
        return preflop.decide(req, state, opp_model)
    return postflop.decide(req, state, opp_model)
