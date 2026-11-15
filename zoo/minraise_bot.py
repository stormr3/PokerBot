#!/usr/bin/env python3
"""MinRaiseBot: min-raises constantly whenever legal."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

_ZOO_DIR = str(Path(__file__).resolve().parent)
if _ZOO_DIR not in sys.path:
    sys.path.insert(0, _ZOO_DIR)

from zoo_common import BaseBot, can_raise, run_bot, simple_action  # noqa: E402


class MinRaiseBot(BaseBot):
    def __init__(self, raise_prob: float = 1.0, seed: int | None = None) -> None:
        super().__init__(seed=seed)
        self.raise_prob = raise_prob

    def choose_action(self, req: dict) -> dict:
        legal = req.get("legal_actions", [])
        if can_raise(req) and (self.raise_prob >= 1.0 or self.rng.random() < self.raise_prob):
            return {"type": "action", "action": "raise", "amount": int(req["min_raise"])}
        if "check" in legal:
            return simple_action("check")
        if "call" in legal:
            return simple_action("call")
        return simple_action("fold")


def main() -> None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--raise-prob", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=None)
    args, _ = p.parse_known_args()
    run_bot(MinRaiseBot(raise_prob=args.raise_prob, seed=args.seed))


if __name__ == "__main__":
    main()
