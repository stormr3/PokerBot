# ==============================================================================
# equity.py — Monte Carlo Equity Estimation Module
# Owner: Person A
#
# Responsibilities:
# - Estimate showdown win probability of private cards against opponent ranges.
# - Support dead card exclusion (known cards, exposed discards).
# - Respect time budgets per request to never trigger timeouts.
# ==============================================================================

import random
import time
from typing import Sequence

from evaluator import VALID_CARDS, compare_hands


def estimate(
    my_cards: Sequence[str],
    board: Sequence[str],
    opp_range: list[tuple[str, str]] | None = None,
    dead_cards: Sequence[str] | None = None,
    time_budget_ms: float = 10.0,
    max_simulations: int = 100,
) -> float:
    """Estimates showdown equity (win probability in [0.0, 1.0]) via Monte Carlo rollout.

    Args:
        my_cards: Player's remaining hole cards (2 cards).
        board: Community board cards dealt so far (0, 3, 4, or 5).
        opp_range: Optional list of candidate 2-card holdings for the opponent.
        dead_cards: Known cards excluded from play (e.g. exposed discards).
        time_budget_ms: Maximum computation time allocated for this estimation.
        max_simulations: Maximum number of Monte Carlo iterations.

    Returns:
        float: Win equity, where 1.0 is certainty of winning and 0.0 is certainty of loss.
    """
    start_time = time.monotonic()
    deadline = start_time + (time_budget_ms / 1000.0)

    # If showdown is already fixed (river with 5 cards) and opponent range has 1 hand:
    if len(board) == 5 and opp_range and len(opp_range) == 1:
        res = compare_hands(my_cards, opp_range[0], board)
        return 1.0 if res > 0 else (0.5 if res == 0 else 0.0)

    # Build unknown deck pool
    known = set(my_cards) | set(board)
    if dead_cards:
        known |= set(dead_cards)
    pool = [c for c in VALID_CARDS if c not in known]

    needed_board = 5 - len(board)
    wins = 0.0
    sims = 0

    while sims < max_simulations:
        # Time guard
        if (sims & 15 == 0) and time.monotonic() >= deadline:
            break

        # Sample opponent cards and remaining board cards
        if opp_range and len(opp_range) > 0:
            opp_holding = random.choice(opp_range)
            # Ensure sampled holding doesn't overlap with known cards
            if opp_holding[0] in known or opp_holding[1] in known:
                continue
            sim_deck = [c for c in pool if c != opp_holding[0] and c != opp_holding[1]]
            runout = random.sample(sim_deck, needed_board) if needed_board > 0 else []
        else:
            sampled = random.sample(pool, 2 + needed_board)
            opp_holding = (sampled[0], sampled[1])
            runout = sampled[2:]

        full_board = list(board) + runout
        res = compare_hands(my_cards, opp_holding, full_board)
        if res > 0:
            wins += 1.0
        elif res == 0:
            wins += 0.5
        sims += 1

    if sims == 0:
        return 0.5
    return wins / sims
