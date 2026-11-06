# timemgr.py — per-decision time budgets from the remaining bank
_SHARE = {"flop": 0.70, "discard": 0.90, "turn": 0.60, "river": 0.50}


def budget_ms(state, kind: str) -> float:
    left = float(state.time_left_ms)
    hands_left = max(1, state.total_hands - state.hand_id + 1)
    pace = 0.8 * left / hands_left
    b = pace * _SHARE.get(kind, 0.3)
    if left < 6000:
        b = min(b, 4.0)
    return max(2.0, min(b, 250.0))


def low_time(state) -> bool:
    return state.time_left_ms < 1500
