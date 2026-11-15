# postflop.py — flop/turn/river betting from equity vs a discard-filtered, action-tilted range
import random
import sys
from time import perf_counter as now
from typing import Any

import equity as eq
import timemgr
from bet_utils import call_or_check, can_raise, check_or_fold, raise_action, simple
from evaluator import CARD_INT, eval_cards

_H: dict[str, Any] = {"id": None}


def _trust(opp) -> float:
    """How strong this opponent's bets have proven at showdown (learned), 0.6..1.3."""
    return max(0.6, min(1.3, 0.85 + 0.5 * (getattr(opp, "bet_value_rate", 0.6) - 0.5)))


def tilt_k_from_history(history, opp) -> int:
    """Best-of-k draws for the opponent's pre-discard range (stronger after aggression)."""
    k = 1
    if any(h.get("street") == "preflop" and h.get("actor") == "opp" and h.get("action") == "raise" for h in history or []):
        k += 1
    if any(h.get("street") == "flop" and h.get("actor") == "opp" and h.get("action") == "raise" for h in history or []):
        k += 1
    if getattr(opp, "agg_freq", 0.4) > 0.6:
        k -= 1
    return max(1, min(3, k))


def _power(history, opp, req=None) -> float:
    p, outstanding, street = 0.0, None, None
    for e in history or []:
        st, act, actor = e.get("street"), e.get("action"), e.get("actor")
        if st != street:
            street, outstanding = st, None
        if actor == "opp":
            if st == "preflop":
                if act == "raise":
                    p += 0.3
            elif act == "raise":
                p += 1.7 if outstanding == "me" else 1.0
            elif act == "check":
                p -= 0.2
            elif act == "call":
                p += 0.15
        if act == "raise":
            outstanding = actor
        elif act == "call":
            outstanding = None
    if req and req.get("to_call", 0) > 0:  # bigger bets are stronger, small ones weaker
        frac = req["to_call"] / float(max(1, req["pot"] - req["to_call"]))
        p += 0.9 * (min(frac, 1.5) - 0.6)
    return max(-0.6, min(4.0, p * (_trust(opp) if p > 0 else 1.0)))


def _range(state, board, hole, opp):
    key = tuple(board)
    rng = _H["rng"]
    if key in rng:
        return rng[key]
    bset = set(board)
    if "base" not in _H:
        dead = set(hole) | bset
        for d in (state.my_discard, state.opp_discard):
            if d:
                dead.add(CARD_INT[d])
        od = CARD_INT[state.opp_discard] if state.opp_discard else None
        _H["base"] = eq.build_base(board[:3], dead, od, getattr(opp, "disc_consistency", 0.8))
    pairs0, w0 = _H["base"]
    pairs, w = [], []
    for p, x in zip(pairs0, w0):
        if p[0] not in bset and p[1] not in bset:
            pairs.append(p)
            w.append(x)
    strs, pct = eq.street_data(pairs, w, board)
    rng[key] = (pairs, w, strs, pct)
    return rng[key]


def _size(req, frac):
    a = raise_action(req, frac)
    if a["amount"] - req.get("my_bet", 0) >= 0.45 * req.get("my_stack", 0):
        a["amount"] = int(req["max_raise"])
    return a


def _cheap(req):
    legal = req.get("legal_actions", [])
    if "check" in legal:
        return simple("check")
    pot, tc = req.get("pot", 0), req.get("to_call", 0)
    if "call" in legal and tc / float(max(1, pot + tc)) <= 0.25:
        return simple("call")
    return check_or_fold(req)


def _choose(e, req, street, state, opp, hole3):
    legal = req["legal_actions"]
    pot, to_call = req["pot"], req["to_call"]
    canr = can_raise(req)
    fold_p = getattr(opp, "fold_to_bet", 0.4)
    agg = getattr(opp, "agg_freq", 0.4)
    station = getattr(opp, "is_station", False)
    river = street == "river"
    hist = req.get("history", [])
    i_bet = any(h.get("street") == street and h.get("actor") == "me" and h.get("action") == "raise" for h in hist)

    if to_call > 0:
        odds = to_call / float(pot + to_call)
        ip = getattr(state, "seat", "button") == "button"
        stack_frac = min(1.0, to_call / float(max(1, req.get("my_stack", 1))))
        margin = 0.025 + (0.03 if i_bet else 0.0) + (0.0 if ip or street == "flop" else 0.02) + 0.06 * stack_frac
        if hole3:
            margin += 0.015
        if canr and e >= (0.82 if river else 0.80) and random.random() < 0.85:
            return _size(req, 0.9)
        if e >= odds + margin:
            return simple("call")
        if e >= odds + margin - 0.03 and random.random() < 0.4:
            return simple("call")
        return check_or_fold(req)

    if not canr:
        return call_or_check(req)
    vthr = (0.58 if river else 0.60) - (0.05 if station else 0.0)
    if e >= vthr:
        if e > 0.90 and not river and agg > 0.5 and random.random() < 0.35:
            return simple("check")
        frac = min(1.0, 0.45 + (e - vthr) * 1.6 + (0.1 if station else 0.0))
        return _size(req, frac)
    if canr and e < (0.15 if river else 0.28) and not station:
        f = max(0.0, min(1.5, (fold_p - 0.38) / 0.2))
        if random.random() < 0.3 * f:
            return _size(req, 0.6)
    return simple("check")


def decide(req: dict[str, Any], state: Any, opp: Any) -> dict[str, Any]:
    try:
        if state.hand_id != _H.get("id"):
            _H.clear()
            _H.update(id=state.hand_id, rng={})
        if timemgr.low_time(state):
            return _cheap(req)
        street = req["street"]
        board = [CARD_INT[c] for c in req["board"]]
        hole = [CARD_INT[c] for c in state.hole_cards]
        deadline = now() + timemgr.budget_ms(state, street) / 1000.0
        hist = req.get("history", [])
        hole3 = len(hole) == 3
        if hole3:
            e = max(eq.keep_equities(hole, board[:3], tilt_k_from_history(hist, opp), 300, deadline,
                                     getattr(opp, "disc_consistency", 0.8)))
        else:
            pairs, w, strs, pct = _range(state, board, hole, opp)
            pw = _power(hist, opp, req)
            weights = [x * (0.15 + p) ** pw for x, p in zip(w, pct)]
            if len(board) == 5:
                e = eq.eq_river(eval_cards(hole + board), strs, weights)
            else:
                known = set(hole) | set(board)
                for d in (state.my_discard, state.opp_discard):
                    if d:
                        known.add(CARD_INT[d])
                e = eq.eq_turn(hole, board, pairs, weights, known, 400, deadline)
        return _choose(e, req, street, state, opp, hole3)
    except Exception as err:  # never crash
        print(f"[postflop] {type(err).__name__}: {err}", file=sys.stderr)
        return _cheap(req)
