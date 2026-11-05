#!/usr/bin/env python3
"""Test opponent: raises about 15% of the time with RANDOM cards, otherwise checks/calls.

It looks "tight" if you only look at raise frequency, but its raises carry no information
about its hand. Used to test that the opponent classifier does not mistake it for a tight bot.
"""
import json
import random
import sys

RAISE_PROB = 0.15
RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_VALUE = {r: i for i, r in enumerate(RANKS)}
SUIT_ORDER = {s: i for i, s in enumerate(SUITS)}
RNG = random.Random()


def choose_action(req: dict) -> dict:
    legal = req.get("legal_actions", [])
    if "raise" in legal and "min_raise" in req and RNG.random() < RAISE_PROB:
        lo, hi = req["min_raise"], req["max_raise"]
        amount = RNG.randint(lo, min(hi, max(lo, lo * 3)))
        return {"type": "action", "action": "raise", "amount": amount}
    if "check" in legal:
        return {"type": "action", "action": "check"}
    if "call" in legal:
        return {"type": "action", "action": "call"}
    return {"type": "action", "action": "fold"}


def choose_discard(req: dict) -> dict:
    hole = req.get("hole_cards", [])
    worst = min(hole, key=lambda c: (RANK_VALUE[c[0]], SUIT_ORDER[c[1]]))
    return {"type": "discard", "card": worst}


def main():
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
        if t == "action_request":
            reply = choose_action(msg)
        elif t == "discard_request":
            reply = choose_discard(msg)
        elif t == "match_end":
            break
        if reply is not None:
            print(json.dumps(reply, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
