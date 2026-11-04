#!/usr/bin/env python3
"""Baseline Opponent: Checks when free (to_call == 0); folds to any bet/raise."""
import json
import sys

RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_VALUE = {r: i for i, r in enumerate(RANKS)}
SUIT_ORDER = {s: i for i, s in enumerate(SUITS)}


def choose_action(req: dict) -> dict:
    legal = req.get("legal_actions", [])
    if "check" in legal:
        return {"type": "action", "action": "check"}
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
