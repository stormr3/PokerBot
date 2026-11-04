# ==============================================================================
# evaluator.py — Hand Strength Evaluation Module
# Owner: Person A
#
# Responsibilities:
# - Evaluate 5-card poker hands into comparable rank tuples.
# - Find the best 5-card hand out of 2 hole cards and up to 5 board cards.
# - Provide tournament default discard tiebreaker (lowest rank; tiebreak: s, h, d, c).
# ==============================================================================

from collections import Counter
from itertools import combinations
from typing import Sequence

RANKS: str = "23456789TJQKA"
SUITS: str = "shdc"  # Also the official engine tiebreak order for discards
RANK_VALUE: dict[str, int] = {r: i + 2 for i, r in enumerate(RANKS)}
SUIT_ORDER: dict[str, int] = {s: i for i, s in enumerate(SUITS)}
VALID_CARDS: set[str] = {r + s for r in RANKS for s in SUITS}

HAND_NAMES: tuple[str, ...] = (
    "high card",
    "one pair",
    "two pair",
    "three of a kind",
    "straight",
    "flush",
    "full house",
    "four of a kind",
    "straight flush",
)


def rank5(cards: Sequence[str]) -> tuple:
    """Computes the strength of exactly 5 cards as a comparable tuple (higher is better).

    Matches the official engine.py evaluator specification:
        Category 8: Straight flush
        Category 7: Four of a kind
        Category 6: Full house
        Category 5: Flush
        Category 4: Straight
        Category 3: Three of a kind
        Category 2: Two pair
        Category 1: One pair
        Category 0: High card
    """
    values = sorted((RANK_VALUE[c[0]] for c in cards), reverse=True)
    flush = len({c[1] for c in cards}) == 1
    uniq = sorted(set(values), reverse=True)
    straight_high = 0

    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight_high = uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:  # A-2-3-4-5 wheel straight
            straight_high = 5

    groups = sorted(Counter(values).items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    shape = [n for _, n in groups]
    by_group = tuple(v for v, _ in groups)

    if straight_high and flush:
        return (8, straight_high)
    if shape == [4, 1]:
        return (7,) + by_group
    if shape == [3, 2]:
        return (6,) + by_group
    if flush:
        return (5,) + tuple(values)
    if straight_high:
        return (4, straight_high)
    if shape == [3, 1, 1]:
        return (3,) + by_group
    if shape == [2, 2, 1]:
        return (2,) + by_group
    if shape == [2, 1, 1, 1]:
        return (1,) + by_group
    return (0,) + tuple(values)


def best_hand(hole: Sequence[str], board: Sequence[str]) -> tuple:
    """Finds the best 5-card hand from hole cards + board cards."""
    all_cards = list(hole) + list(board)
    if len(all_cards) < 5:
        return rank5(all_cards + ["2s"] * (5 - len(all_cards)))
    return max(rank5(combo) for combo in combinations(all_cards, 5))


def compare_hands(hole_a: Sequence[str], hole_b: Sequence[str], board: Sequence[str]) -> int:
    """Compares two hands at showdown: returns 1 if A wins, -1 if B wins, 0 on tie."""
    score_a = best_hand(hole_a, board)
    score_b = best_hand(hole_b, board)
    if score_a > score_b:
        return 1
    if score_b > score_a:
        return -1
    return 0


def default_discard(hole: Sequence[str]) -> str:
    """Official engine tiebreak discard: lowest rank; tiebreak spades, hearts, diamonds, clubs."""
    return min(hole, key=lambda c: (RANK_VALUE[c[0]], SUIT_ORDER[c[1]]))
