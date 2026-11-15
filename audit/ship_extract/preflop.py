# ==============================================================================
# preflop.py — Preflop strategy
# Owner: Person B
#
# Idea: every preflop table answers "what is my win chance if the opponent's hand
# comes from the best N% of hands". We estimate N ("width") for the opponent from how
# many raises have happened (and who they are, via opponent_model), look up our equity
# at that width, and compare it with the pot odds.
#   - First actions (open, limp, BB vs limp): nothing is known about their hand, so we
#     use the hand's percentile against fixed cutoffs from config.py.
#   - Facing a raise: equity vs their range against pot odds; re-raise when strong.
# Flags in config.py: USE_RANGE_TABLES (False = always width 100),
# USE_OPP_CLASSIFIER (False = fixed DEFAULT_OPP_WIDTH instead of the measured width).
# ==============================================================================

import sys
from typing import Any

import config
import preflop_table as pt
from bet_utils import call_or_check, can_raise, check_or_fold, raise_action, simple

_LOGGED: set[str] = set()


def _log_once(msg: str) -> None:
    if msg not in _LOGGED and len(_LOGGED) < 10:
        _LOGGED.add(msg)
        print(f"[preflop] {msg}", file=sys.stderr)


def count_preflop_raises(history: list[dict[str, Any]]) -> int:
    """Voluntary preflop raises by either player (the big blind is not in history)."""
    return sum(1 for h in history or [] if h.get("street") == "preflop" and h.get("action") == "raise")


def infer_seat(req: dict[str, Any], state: Any) -> str:
    """Seat from state; if missing, infer it from the request."""
    seat = getattr(state, "seat", None) if state is not None else None
    if seat in ("button", "big_blind"):
        return seat
    _log_once("seat missing in state; inferring from request")
    pre = [h for h in req.get("history", []) if h.get("street") == "preflop"]
    if pre:  # the button always acts first preflop
        return "button" if pre[0].get("actor") == "me" else "big_blind"
    return "button" if req.get("my_bet", 1) <= 1 else "big_blind"


def estimate_width(n_raises: int, opp_model: Any) -> float:
    """Percent of all hands the opponent could hold, given the raises so far."""
    if not config.USE_RANGE_TABLES or n_raises <= 0:
        return 100.0
    width = None
    if config.USE_OPP_CLASSIFIER and opp_model is not None:
        try:
            width = float(opp_model.preflop_width(n_raises))
        except Exception as err:
            _log_once(f"opponent width failed ({err}); using default")
    if width is None:
        width = config.DEFAULT_OPP_WIDTH * config.PREFLOP_RERAISE_FACTOR ** (n_raises - 1)
    return min(100.0, max(config.PREFLOP_MIN_WIDTH, width))


def _passive_fallback(req: dict[str, Any]) -> dict[str, Any]:
    """When the hole cards are unknown: check if free, call a cheap bet, else fold."""
    legal = req.get("legal_actions", [])
    to_call = req.get("to_call", 0)
    pot = req.get("pot", 0)
    if "check" in legal:
        return simple("check")
    if "call" in legal and to_call / float(max(1, pot + to_call)) <= 0.30:
        return simple("call")
    return check_or_fold(req)


def decide(req: dict[str, Any], state: Any, opp_model: Any) -> dict[str, Any]:
    """Legal preflop action for an action_request."""
    legal = req.get("legal_actions", [])
    to_call = req.get("to_call", 0)
    pot = req.get("pot", 0)

    hole = list(getattr(state, "hole_cards", None) or []) if state is not None else []
    if len(hole) != 3:
        _log_once(f"expected 3 hole cards in state, got {hole}")
        return _passive_fallback(req)

    seat = infer_seat(req, state)
    n_raises = count_preflop_raises(req.get("history", []))
    pct = pt.get_percentile(hole)
    raise_ok = can_raise(req)

    # 1. Free to check: big blind after a limp
    if to_call <= 0:
        if raise_ok and pct >= config.PREFLOP_BB_RAISE_PCT:
            return raise_action(req, 0.75)
        return check_or_fold(req)

    # 2. Button's first action (nobody has raised): open, limp or fold
    if n_raises == 0:
        if raise_ok and pct >= config.PREFLOP_OPEN_PCT:
            return raise_action(req, 0.75)
        if "call" in legal and pct >= config.PREFLOP_LIMP_PCT:
            return simple("call")
        return check_or_fold(req) if "fold" in legal else call_or_check(req)

    # 3. Facing a raise: equity vs the opponent's estimated range against pot odds
    width = estimate_width(n_raises, opp_model)
    equity = pt.equity_at_width(hole, width)
    pot_odds = to_call / float(max(1, pot + to_call))
    pos_buffer = config.PREFLOP_CALL_BUFFER_IP if seat == "button" else config.PREFLOP_CALL_BUFFER_OOP
    stack_frac = min(1.0, to_call / float(max(1, req.get("my_stack", 0) + req.get("my_bet", 0))))
    required = pot_odds - pos_buffer + config.PREFLOP_CALL_MARGIN + config.PREFLOP_BIG_BET_MARGIN * stack_frac

    threshold = config.PREFLOP_3BET_EQUITY_VS_RANGE if n_raises == 1 else config.PREFLOP_4BET_EQUITY_VS_RANGE
    if raise_ok and equity >= threshold:
        return raise_action(req, 0.85 if n_raises == 1 else 1.0)
    if "call" in legal and equity >= required:
        return simple("call")
    return check_or_fold(req)
