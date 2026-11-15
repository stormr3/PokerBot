#!/usr/bin/env python3
"""TrapBot: checks strong hands postflop to check-raise; passive otherwise."""

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
    hand_percentile,
    raise_pot_frac,
    run_bot,
    simple_action,
)


class TrapBot(BaseBot):
    def __init__(
        self,
        trap_eq: float = 0.68,
        raise_frac: float = 0.85,
        call_margin: float = 0.03,
        seed: int | None = None,
    ) -> None:
        super().__init__(seed=seed)
        self.trap_eq = trap_eq
        self.raise_frac = raise_frac
        self.call_margin = call_margin

    def choose_action(self, req: dict) -> dict:
        legal = req.get("legal_actions", [])
        street = req.get("street", "preflop")
        pot = int(req.get("pot", 0))
        to_call = int(req.get("to_call", 0))

        if street == "preflop":
            pct = hand_percentile(self.hole_cards) if len(self.hole_cards) == 3 else 0.5
            if to_call == 0 and "check" in legal:
                return simple_action("check")
            if "call" in legal:
                if pct >= 0.78 or (pct >= 0.42 and to_call <= 8):
                    return simple_action("call")
            return simple_action("fold" if "fold" in legal else ("check" if "check" in legal else "call"))

        # Postflop: always check when free (sets up check-raise with strong hands).
        if to_call == 0 and "check" in legal:
            return simple_action("check")

        eq_val = self.postflop_equity(req, flop_samples=80, turn_samples=100, budget_s=0.03)
        hist = req.get("history", [])
        i_raised_street = any(
            h.get("street") == street and h.get("actor") == "me" and h.get("action") == "raise"
            for h in hist
        )
        if eq_val >= self.trap_eq and can_raise(req) and (not i_raised_street or eq_val >= 0.85):
            return raise_pot_frac(req, self.raise_frac)

        pot_odds = to_call / float(max(1, pot + to_call))
        if eq_val >= pot_odds + self.call_margin and "call" in legal:
            return simple_action("call")
        return simple_action("fold" if "fold" in legal else ("check" if "check" in legal else "call"))

    def choose_discard(self, req: dict) -> str:
        return self.discard_by_equity(req, samples=120, budget_s=0.035)


def main() -> None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--trap-eq", type=float, default=0.68)
    p.add_argument("--raise-frac", type=float, default=0.85)
    args, _ = p.parse_known_args()
    run_bot(TrapBot(trap_eq=args.trap_eq, raise_frac=args.raise_frac))


if __name__ == "__main__":
    main()
