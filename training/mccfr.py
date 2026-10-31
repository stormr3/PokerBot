"""Offline Monte Carlo CFR (MCCFR) research harness for Discard Hold'em subgames.

Responsibilities:
- Self-contained offline research tool for testing Outcome-Sampling or
  External-Sampling MCCFR on abstracted Discard Hold'em situations.
- Investigates precomputed blueprint strategy tables and abstraction buckets.
- Operates completely independently from bot.py and runtime competition packages.

Dependencies:
- Standard Library: typing, random
- NumPy: numpy (for regret array operations)
"""

from typing import Any


def run_mccfr_experiment(config: dict[str, Any]) -> None:
    """Runs an offline MCCFR training experiment with the specified abstraction config.

    Args:
        config: Experiment parameters (abstraction buckets, iterations, sample rate).

    TODO:
        - Construct abstracted subgame representation for Discard Hold'em.
        - Implement external-sampling MCCFR traversal.
        - Record convergence and exploitability metrics.
    """
    raise NotImplementedError("run_mccfr_experiment is not yet implemented.")


if __name__ == "__main__":
    print("MCCFR offline research scaffold.")
