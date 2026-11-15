#!/usr/bin/env python3
"""ShoveBot: preflop jams top X% of hands, otherwise checks/folds."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

_ZOO_DIR = str(Path(__file__).resolve().parent)
if _ZOO_DIR not in sys.path:
    sys.path.insert(0, _ZOO_DIR)

from zoo_common import BaseBot, can_raise, hand_percentile, run_bot, simple_action  # noqa: E402


class ShoveBot(BaseBot):
    def __init__(self, top_x: float = 15.0) -> None:
        super().__init__()
        self.top_x = top_x
        self.threshold = 1.0 - max(0.0, min(100.0, top_x)) / 100.0
        self.shoved_or_top = False

    def on_new_hand(self, msg: dict) -> None:
        super().on_new_hand(msg)
        pct = hand_percentile(self.hole_cards) if len(self.hole_cards) == 3 else 0.0
        self.shoved_or_top = pct >= self.threshold

    def choose_action(self, req: dict) -> dict:
        legal = req.get("legal_actions", [])
        street = req.get("street", "preflop")
        if street == "preflop":
            if self.shoved_or_top:
                if can_raise(req):
                    return {"type": "action", "action": "raise", "amount": int(req["max_raise"])}
                if "call" in legal:
                    return simple_action("call")
                if "check" in legal:
                    return simple_action("check")
            return simple_action("check" if "check" in legal else "fold")

        if self.shoved_or_top:
            if "check" in legal:
                return simple_action("check")
            if "call" in legal:
                return simple_action("call")
        return simple_action("check" if "check" in legal else "fold")


def main(default_top_x: float = 15.0) -> None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--top-x", type=float, default=default_top_x)
    args, _ = p.parse_known_args()
    run_bot(ShoveBot(top_x=args.top_x))


if __name__ == "__main__":
    main(15.0)
