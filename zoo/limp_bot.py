#!/usr/bin/env python3
"""LimpBot: limp/call preflop; postflop bets/raises only with top pair or better."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

_ZOO_DIR = str(Path(__file__).resolve().parent)
if _ZOO_DIR not in sys.path:
    sys.path.insert(0, _ZOO_DIR)

from zoo_common import (  # noqa: E402
    BaseBot,
    can_raise,
    is_top_pair_or_better,
    raise_pot_frac,
    run_bot,
    simple_action,
)


class LimpBot(BaseBot):
    def __init__(self, bet_frac: float = 0.66) -> None:
        super().__init__()
        self.bet_frac = bet_frac

    def choose_action(self, req: dict) -> dict:
        legal = req.get("legal_actions", [])
        street = req.get("street", "preflop")
        if street == "preflop":
            if "check" in legal:
                return simple_action("check")
            if "call" in legal:
                return simple_action("call")
            return simple_action("fold")

        board = req.get("board", [])
        strong = is_top_pair_or_better(self.hole_cards, board)
        if strong:
            hist = req.get("history", [])
            i_raised_street = any(
                h.get("street") == street and h.get("actor") == "me" and h.get("action") == "raise"
                for h in hist
            )
            if can_raise(req) and not i_raised_street:
                return raise_pot_frac(req, self.bet_frac)
            if "call" in legal:
                return simple_action("call")
            if "check" in legal:
                return simple_action("check")
            return simple_action("fold")

        if "check" in legal:
            return simple_action("check")
        return simple_action("fold")

    def choose_discard(self, req: dict) -> str:
        return self.discard_by_equity(req, samples=120, budget_s=0.035)


def main() -> None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--bet-frac", type=float, default=0.66)
    args, _ = p.parse_known_args()
    run_bot(LimpBot(bet_frac=args.bet_frac))


if __name__ == "__main__":
    main()
