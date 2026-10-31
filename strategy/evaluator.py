"""Hand evaluation module for 5-card and 7-card poker hands.

Official Specifications (Rulebook Section 4.5):
- At showdown, each player makes the best five-card hand from their remaining
  2 hole cards and the 5 board cards, using standard hand rankings.

Implementation Choices (Not Official Rules):
- Cactus Kev bitwise algorithm and prime product lookup tables:
  Internal choice for O(1) 5-card evaluation speed within memory constraints.
- Combination search: Iterating all 21 combinations of 5 cards from 7 (2 hole + 5 board).
- Rank scores in [1, 7462] where 1 is Royal Flush and 7462 is 7-5-4-3-2 unsuited.
These algorithms and score ranges are internal engineering choices, not rules.

Dependencies:
- Standard Library: typing, itertools
- NumPy: numpy (for lookup table array acceleration)
"""

from typing import Sequence


def evaluate_5cards(c1: int, c2: int, c3: int, c4: int, c5: int) -> int:
    """Evaluates 5 cards represented as 32-bit Cactus Kev integers.

    Note: Internal implementation choice for rapid hand scoring.

    Args:
        c1, c2, c3, c4, c5: 32-bit integer representations of 5 distinct cards.

    Returns:
        int: Hand rank integer in [1, 7462] (1 is Royal Flush, 7462 is worst high card).

    TODO:
        - Check flush: (c1 & c2 & c3 & c4 & c5 & 0xF000) != 0.
        - If flush: lookup rank bits in flushes table.
        - Check unique5 / straights: lookup rank bits in unique5 table.
        - Else: compute prime product of (card & 0xFF) and lookup in product table.
    """
    raise NotImplementedError("evaluate_5cards is not yet implemented.")


def evaluate_7cards(card_ids: Sequence[int]) -> int:
    """Evaluates best 5-card hand rank out of 7 cards (2 hole cards + 5 board cards).

    Official Rule (Section 4.5):
        Best 5-card hand from 2 remaining hole cards + 5 board cards.

    Args:
        card_ids: 7 integer card IDs in [0, 51].

    Returns:
        int: Strongest 5-card hand rank score.

    TODO:
        - Convert card IDs to 32-bit bitmasks.
        - Iterate over all 21 combinations of 5 cards from 7.
        - Return minimum score.
    """
    raise NotImplementedError("evaluate_7cards is not yet implemented.")
