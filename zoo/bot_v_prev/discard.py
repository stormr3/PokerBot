# discard.py — choose the discard by sampled showdown equity of each keep (turn/river included)
import random
from time import perf_counter as now
from typing import Any

import equity
import timemgr
from evaluator import CARD_INT, default_discard
from postflop import tilt_k_from_history


def choose(req: dict[str, Any], state: Any, opp_model: Any) -> dict[str, str]:
    hole_s = req.get("hole_cards", [])
    if len(hole_s) != 3 or timemgr.low_time(state):
        return {"type": "discard", "card": default_discard(hole_s) if hole_s else "2s"}
    hole = [CARD_INT[c] for c in hole_s]
    flop = [CARD_INT[c] for c in req["board"][:3]]
    deadline = now() + timemgr.budget_ms(state, "discard") / 1000.0
    k = tilt_k_from_history(state.history, opp_model)
    cons = getattr(opp_model, "disc_consistency", 0.8)
    eqs = equity.keep_equities(hole, flop, k, 400, deadline, cons)
    best = max(eqs)
    near = [i for i, e in enumerate(eqs) if e >= best - 0.006]
    i = random.choice(near)
    return {"type": "discard", "card": hole_s[i]}
