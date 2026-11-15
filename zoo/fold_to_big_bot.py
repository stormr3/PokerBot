#!/usr/bin/env python3
"""FoldToBigBot: checks when free, calls bets up to ~40% of prior pot, folds to larger."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

_ZOO_DIR = str(Path(__file__).resolve().parent)
if _ZOO_DIR not in sys.path:
    sys.path.insert(0, _ZOO_DIR)

from zoo_common import BaseBot, run_bot, simple_action  # noqa: E402


class FoldToBigBot(BaseBot):
    def __init__(self, max_pot_frac: float = 0.40) -> None:
        super().__init__()
        self.max_pot_frac = max_pot_frac

    def choose_action(self, req: dict) -> dict:
        legal = req.get("legal_actions", [])
        to_call = int(req.get("to_call", 0))
        if to_call <= 0:
            return simple_action("check" if "check" in legal else "call")

        street = req.get("street", "preflop")
        pot = int(req.get("pot", 0))
        prior_pot = max(1, pot - to_call)
        # Allow 1-chip SB limp so hands reach postflop; otherwise enforce ~40% pot threshold.
        if (street == "preflop" and to_call <= 1) or (to_call / float(prior_pot) <= self.max_pot_frac + 0.02):
            if "call" in legal:
                return simple_action("call")
        return simple_action("fold" if "fold" in legal else ("check" if "check" in legal else "call"))


def main() -> None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--max-pot-frac", type=float, default=0.40)
    args, _ = p.parse_known_args()
    run_bot(FoldToBigBot(max_pot_frac=args.max_pot_frac))


if __name__ == "__main__":
    main()
