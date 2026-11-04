#!/usr/bin/env python3
"""Baseline Opponent: Chooses randomly among legal actions and hole card discards."""
import json
import random
import sys


def choose_action(req: dict) -> dict:
    legal = req.get("legal_actions", [])
    roll = random.random()
    if "raise" in legal and roll < 0.25 and "min_raise" in req and "max_raise" in req:
        min_r = req["min_raise"]
        max_r = req["max_raise"]
        amount = random.randint(min_r, min(max_r, min_r + 10))
        return {"type": "action", "action": "raise", "amount": amount}
    if "check" in legal and roll < 0.6:
        return {"type": "action", "action": "check"}
    if "call" in legal and roll < 0.8:
        return {"type": "action", "action": "call"}
    if "check" in legal:
        return {"type": "action", "action": "check"}
    return {"type": "action", "action": "fold"}


def choose_discard(req: dict) -> dict:
    hole = req.get("hole_cards", [])
    return {"type": "discard", "card": random.choice(hole)}


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
