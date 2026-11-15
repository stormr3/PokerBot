#!/usr/bin/env python3
"""Equity-driven zoo opponent with optional epsilon-random actions."""

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
    clamp_raise,
    count_street_raises,
    preflop_equity,
    raise_pot_frac,
    run_bot,
    simple_action,
)


class EqBot(BaseBot):
    def __init__(
        self,
        eps: float = 0.0,
        raise_eq: float = 0.62,
        raise_frac: float = 0.66,
        call_margin: float = 0.03,
        bluff_prob: float = 0.08,
        seed: int | None = None,
    ) -> None:
        super().__init__(seed=seed)
        self.eps = eps
        self.raise_eq = raise_eq
        self.raise_frac = raise_frac
        self.call_margin = call_margin
        self.bluff_prob = bluff_prob

    def _estimate_equity(self, req: dict) -> float:
        street = req.get("street", "preflop")
        if street == "preflop":
            if len(self.hole_cards) != 3:
                return 0.5
            n_raises = count_street_raises(req.get("history", []), "preflop")
            width = 100.0 if n_raises == 0 else max(20.0, 60.0 / n_raises)
            return preflop_equity(self.hole_cards, width)
        return self.postflop_equity(req, flop_samples=80, turn_samples=100, budget_s=0.03)

    def choose_action(self, req: dict) -> dict:
        legal = req.get("legal_actions", [])
        if self.eps > 0.0 and self.rng.random() < self.eps and legal:
            act = self.rng.choice(legal)
            if act == "raise" and can_raise(req):
                lo, hi = int(req["min_raise"]), int(req["max_raise"])
                cap = min(hi, max(lo, lo + max(10, int(req.get("pot", 0)))))
                return {"type": "action", "action": "raise", "amount": self.rng.randint(lo, cap)}
            if act != "raise":
                return simple_action(act)

        eq_val = self._estimate_equity(req)
        pot = int(req.get("pot", 0))
        to_call = int(req.get("to_call", 0))
        raise_ok = can_raise(req)

        if eq_val > self.raise_eq and raise_ok:
            return raise_pot_frac(req, self.raise_frac)

        if to_call > 0:
            pot_odds = to_call / float(max(1, pot + to_call))
            if eq_val > pot_odds + self.call_margin and "call" in legal:
                return simple_action("call")
            if raise_ok and self.rng.random() < self.bluff_prob:
                return raise_pot_frac(req, self.raise_frac)
            return simple_action("fold" if "fold" in legal else ("check" if "check" in legal else "call"))

        if raise_ok and self.rng.random() < self.bluff_prob:
            return raise_pot_frac(req, self.raise_frac)
        return simple_action("check" if "check" in legal else "call")

    def choose_discard(self, req: dict) -> str:
        return self.discard_by_equity(req, samples=120, budget_s=0.035)


def main(default_eps: float = 0.0) -> None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--eps", type=float, default=default_eps)
    p.add_argument("--seed", type=int, default=None)
    args, _ = p.parse_known_args()
    run_bot(EqBot(eps=args.eps, seed=args.seed))


if __name__ == "__main__":
    main(0.0)
