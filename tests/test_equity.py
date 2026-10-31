"""Unit test scaffolding for strategy.equity module.

Responsibilities:
- Verifies Monte Carlo equity estimation against known analytical benchmarks.
- Verifies dead card exclusion (exposed discards, private cards, board).
- Benchmarks rollout speed to ensure per-request latency target (< 15 ms) is met.

Dependencies:
- Standard Library: unittest
"""

import unittest


class TestEquity(unittest.TestCase):
    """Test suite for Monte Carlo equity simulation."""

    def test_equity_known_situations(self) -> None:
        """Verifies equity estimation for dominant matchups (e.g., AA vs 72o).

        TODO:
            - Set up preflop/flop scenarios with known approximate equity.
            - Run simulate_equity_vs_range and assert estimated equity within tolerance.
        """
        pass

    def test_dead_card_exclusion(self) -> None:
        """Verifies that dead cards (exposed discards) are never dealt in rollouts.

        TODO:
            - Provide dead card IDs and assert they never appear in sampled boards or hands.
        """
        pass


if __name__ == "__main__":
    unittest.main()
