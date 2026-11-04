# ==============================================================================
# preflop_table.py — Precomputed Canonical Equity & Pot-Odds Preflop Module
# Owner: Person B
#
# Responsibilities:
# - Map 3-card hole card holdings to canonical isomorphism classes (1,755 keys).
# - Provide O(1) showdown equity lookup using precomputed .npz table in src/data/.
# - Provide pot-odds and equity based recommendations for preflop street.
# - Guarantee fallback heuristics if precomputed table cannot be read.
# ==============================================================================

from collections import Counter
from pathlib import Path
from typing import Sequence

import config
from evaluator import RANK_VALUE

RANK_STR = "23456789TJQKA"
RANK_MAP = {r: i for i, r in enumerate(RANK_STR)}

# Precomputed equity table in-memory cache: canonical_key -> float equity in [0.0, 1.0]
_EQUITY_CACHE: dict[str, float] = {}
_TABLE_LOADED: bool = False


def canonical_3card(cards: Sequence[str]) -> str:
    """Maps any 3 cards to an unambiguous canonical 6-character string.

    Sorts ranks descending (2..A).
    Normalizes suits to canonical s, h, d representation.
    """
    if len(cards) < 3:
        return "2s2h2d"

    sorted_cards = sorted(cards, key=lambda c: RANK_MAP.get(c[0], 0), reverse=True)
    r0, r1, r2 = sorted_cards[0][0], sorted_cards[1][0], sorted_cards[2][0]
    s0, s1, s2 = sorted_cards[0][1], sorted_cards[1][1], sorted_cards[2][1]

    # Trips (r0 == r1 == r2)
    if r0 == r1 == r2:
        return f"{r0}s{r1}h{r2}d"

    # High Pair (r0 == r1 > r2)
    if r0 == r1:
        if s2 == s0 or s2 == s1:
            return f"{r0}s{r1}h{r2}s"
        return f"{r0}s{r1}h{r2}d"

    # Low Pair (r0 > r1 == r2)
    if r1 == r2:
        if s0 == s1 or s0 == s2:
            return f"{r0}s{r1}s{r2}h"
        return f"{r0}d{r1}s{r2}h"

    # Distinct ranks (r0 > r1 > r2)
    distinct_suits = len({s0, s1, s2})
    if distinct_suits == 1:
        return f"{r0}s{r1}s{r2}s"
    if distinct_suits == 3:
        return f"{r0}s{r1}h{r2}d"
    if s0 == s1:
        return f"{r0}s{r1}s{r2}d"
    if s0 == s2:
        return f"{r0}s{r1}d{r2}s"
    return f"{r0}d{r1}s{r2}s"


def _load_equity_table() -> None:
    """Loads precomputed canonical equity table from .npz file into in-memory dict."""
    global _EQUITY_CACHE, _TABLE_LOADED
    if _TABLE_LOADED:
        return

    base_dir = Path(__file__).resolve().parent
    candidate_paths = [
        base_dir / "data" / "preflop_equity.npz",
        base_dir / "preflop_equity.npz",
        Path.cwd() / "src" / "data" / "preflop_equity.npz",
        Path.cwd() / "data" / "preflop_equity.npz",
    ]

    for p in candidate_paths:
        if p.is_file():
            try:
                import numpy as np

                data = np.load(str(p), mmap_mode=None)
                keys = data["keys"]
                eqs = data["equities"]
                _EQUITY_CACHE = {str(k): float(v) for k, v in zip(keys, eqs)}
                _TABLE_LOADED = True
                return
            except Exception:
                continue

    _TABLE_LOADED = True  # Avoid re-probing if files are missing


def _heuristic_equity(cards: Sequence[str]) -> float:
    """Heuristic equity estimation fallback if precomputed table is not loaded."""
    if len(cards) < 3:
        return 0.50

    ranks = [c[0] for c in cards]
    suits = [c[1] for c in cards]
    values = sorted([RANK_VALUE.get(r, 2) for r in ranks], reverse=True)
    counts = Counter(ranks).most_common()

    if counts[0][1] == 3:
        return 0.78
    if counts[0][1] == 2:
        pair_val = RANK_VALUE.get(counts[0][0], 2)
        return 0.50 + (pair_val / 14.0) * 0.28
    if len(set(suits)) == 1:
        return 0.45 + (values[0] / 14.0) * 0.15
    if values[2] >= 10:
        return 0.60
    if values[0] >= 13 and values[1] >= 10:
        return 0.55
    if values[0] >= 12:
        return 0.50
    return 0.35 + (values[0] / 14.0) * 0.10


def get_preflop_equity(cards: Sequence[str]) -> float:
    """Returns precomputed showdown equity in [0.0, 1.0] for the given 3 hole cards.

    Performs an O(1) hash lookup from the preloaded canonical .npz table.
    """
    _load_equity_table()
    if not cards or len(cards) < 3:
        return 0.50

    key = canonical_3card(cards)
    if key in _EQUITY_CACHE:
        return _EQUITY_CACHE[key]
    return _heuristic_equity(cards)


def classify_3cards(cards: Sequence[str]) -> tuple[str, int]:
    """Classifies 3 hole cards into pattern and numeric tier (for backward compatibility)."""
    equity = get_preflop_equity(cards)
    if equity >= 0.70:
        return ("monster", 1)
    if equity >= 0.60:
        return ("strong", 2)
    if equity >= 0.50:
        return ("medium", 3)
    if equity >= 0.40:
        return ("weak", 4)
    return ("trash", 5)


def get_preflop_recommendation(cards: Sequence[str], seat: str, to_call: int, pot: int = 3) -> str:
    """Returns baseline action recommendation using canonical equity and pot odds.

    Args:
        cards: Player's 3 hole cards.
        seat: 'button' or 'big_blind'.
        to_call: Chips needed to call.
        pot: Total pot size including current bets.
    """
    equity = get_preflop_equity(cards)

    # Free to check
    if to_call <= 0:
        if seat == "big_blind" and equity >= config.PREFLOP_BB_RAISE_EQUITY:
            return "raise"
        return "check"

    # Button opening (to_call == 1, pot == 3)
    if seat == "button" and to_call == 1:
        if equity >= config.PREFLOP_OPEN_EQUITY:
            return "raise"
        if equity >= config.PREFLOP_LIMP_EQUITY:
            return "call"
        return "fold"

    # Facing bet or 3-bet
    pot_odds = to_call / float(pot + to_call)
    buffer = config.PREFLOP_CALL_BUFFER_IP if seat == "button" else config.PREFLOP_CALL_BUFFER_OOP

    if equity >= config.PREFLOP_3BET_EQUITY:
        return "raise"
    if equity >= (pot_odds - buffer):
        return "call"
    return "fold"
