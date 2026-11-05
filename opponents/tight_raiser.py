#!/usr/bin/env python3
"""Test opponent: genuinely tight preflop. Raises only with its top ~15% of hands.

Preflop: raise with the top hands, call a bet with the top half, otherwise check/fold.
Postflop: check/call (never raises, never folds). Discards the lowest rank.
Hand strength comes from src/preflop_data.py (PCT_RANDOM) when available, otherwise a
simple heuristic, so this file also works without the generated tables.
"""
import json
import sys
from pathlib import Path

RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_VALUE = {r: i for i, r in enumerate(RANKS)}
SUIT_ORDER = {s: i for i, s in enumerate(SUITS)}

RAISE_PCT = 0.85   # raise with the top 15%
CALL_PCT = 0.50    # call a raise with the top 50%

_PCT = None
_CANON = None
try:  # use the real hand ranking if the generated data exists
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from preflop_data import PCT_RANDOM as _PCT  # type: ignore
    from preflop_table import canonical_3card as _CANON  # type: ignore
except Exception:
    _PCT = None


def hand_pct(hole: list) -> float:
    if _PCT is not None and _CANON is not None and len(hole) == 3:
        try:
            return float(_PCT[_CANON(hole)])
        except Exception:
            pass
    if len(hole) != 3:
        return 0.5
    vals = sorted((RANK_VALUE[c[0]] for c in hole), reverse=True)  # 0..12
    if vals[0] == vals[1] == vals[2]:
        return 0.95
    if vals[0] == vals[1] or vals[1] == vals[2]:
        pair = vals[0] if vals[0] == vals[1] else vals[1]
        return 0.90 if pair >= 6 else 0.55
    return 0.90 if vals[2] >= 9 else (0.70 if vals[0] >= 12 and vals[1] >= 10 else 0.30)


class Bot:
    def __init__(self):
        self.hole = []

    def choose_action(self, req: dict) -> dict:
        legal = req.get("legal_actions", [])
        to_call = req.get("to_call", 0)
        if req.get("street") == "preflop":
            pct = hand_pct(self.hole)
            if pct >= RAISE_PCT and "raise" in legal and "min_raise" in req:
                lo, hi = req["min_raise"], req["max_raise"]
                target = req.get("opp_bet", 0) + int(0.75 * (req.get("pot", 0) + to_call))
                return {"type": "action", "action": "raise", "amount": max(lo, min(hi, target))}
            if to_call > 0:
                if pct >= CALL_PCT and "call" in legal:
                    return {"type": "action", "action": "call"}
                return {"type": "action", "action": "fold"}
            return {"type": "action", "action": "check"} if "check" in legal else {"type": "action", "action": "call"}
        if "check" in legal:
            return {"type": "action", "action": "check"}
        if "call" in legal:
            return {"type": "action", "action": "call"}
        return {"type": "action", "action": "fold"}

    @staticmethod
    def choose_discard(req: dict) -> dict:
        hole = req.get("hole_cards", [])
        worst = min(hole, key=lambda c: (RANK_VALUE[c[0]], SUIT_ORDER[c[1]]))
        return {"type": "discard", "card": worst}


def main():
    bot = Bot()
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        t = msg.get("type")
        reply = None
        if t == "new_hand":
            bot.hole = list(msg.get("hole_cards", []))
        elif t == "action_request":
            reply = bot.choose_action(msg)
        elif t == "discard_request":
            reply = bot.choose_discard(msg)
        elif t == "match_end":
            break
        if reply is not None:
            print(json.dumps(reply, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
