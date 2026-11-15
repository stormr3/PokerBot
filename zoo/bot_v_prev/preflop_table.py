# ==============================================================================
# preflop_table.py — Preflop equity data access (no decisions)
# Owner: Person B
#
# Data comes from preflop_data.py (generated offline by tools/generate_preflop_table.py,
# a plain Python module: NO file reads at runtime). It holds, per canonical 3-card hand:
#   EQUITY_TOP<N>   win chance if the opponent's hand is only from the best N% of hands
#   EQUITY_RANDOM   win chance vs any hand (the "top 100%" level)
#   PCT_RANDOM      hand percentile 0..1 (1 = best)
# Whatever EQUITY_TOP<N> tables exist are picked up automatically. If preflop_data
# cannot be imported, one line goes to stderr and a heuristic is used instead.
# ==============================================================================

import re
import sys
from collections import Counter
from typing import Sequence

RANK_STR = "23456789TJQKA"
RANK_MAP = {r: i for i, r in enumerate(RANK_STR)}
_RANK_VALUE = {r: i + 2 for i, r in enumerate(RANK_STR)}  # 2..14

_LEVELS: dict[int, dict[str, float]] = {}   # width percent -> {key: equity}
_PCT: dict[str, float] = {}
_LOAD_ERROR: str | None = None


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


def _load() -> None:
    """Import the generated tables once, at module import time."""
    global _LOAD_ERROR
    try:
        import preflop_data as pd  # generated module, shipped in the zip
    except Exception as err:  # missing or broken data must never crash the bot
        _LOAD_ERROR = f"{type(err).__name__}: {err}"
        print(f"[preflop_table] preflop_data unavailable ({_LOAD_ERROR}); using heuristic equity",
              file=sys.stderr)
        return

    for name in dir(pd):
        m = re.fullmatch(r"EQUITY_TOP(\d+)", name)
        table = getattr(pd, name, None)
        if m and isinstance(table, dict) and table:
            _LEVELS[int(m.group(1))] = table
    rnd = getattr(pd, "EQUITY_RANDOM", None)
    if isinstance(rnd, dict) and rnd:
        _LEVELS[100] = rnd
    pct = getattr(pd, "PCT_RANDOM", None)
    if isinstance(pct, dict):
        _PCT.update(pct)
    if not _LEVELS:
        _LOAD_ERROR = "no equity tables found in preflop_data"
        print(f"[preflop_table] {_LOAD_ERROR}; using heuristic equity", file=sys.stderr)


_load()


def tables_loaded() -> bool:
    return bool(_LEVELS)


def levels() -> list[int]:
    """Sorted list of available widths (percent), e.g. [5, 10, 15, 25, 40, 60, 100]."""
    return sorted(_LEVELS)


# ------------------------------------------------------------------------------
# Heuristic fallbacks (only used when the generated data is missing)
# ------------------------------------------------------------------------------

def _heuristic_equity(cards: Sequence[str]) -> float:
    if len(cards) < 3:
        return 0.50

    ranks = [c[0] for c in cards]
    suits = [c[1] for c in cards]
    values = sorted([_RANK_VALUE.get(r, 2) for r in ranks], reverse=True)
    counts = Counter(ranks).most_common()

    if counts[0][1] == 3:
        return 0.78
    if counts[0][1] == 2:
        pair_val = _RANK_VALUE.get(counts[0][0], 2)
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


def _heuristic_percentile(cards: Sequence[str]) -> float:
    return min(1.0, max(0.0, (_heuristic_equity(cards) - 0.35) / 0.43))


# ------------------------------------------------------------------------------
# Public lookups
# ------------------------------------------------------------------------------

def get_percentile(cards: Sequence[str]) -> float:
    """Hand rank in [0, 1] (combo-weighted; 1.0 = best hand)."""
    if not cards or len(cards) < 3:
        return 0.5
    v = _PCT.get(canonical_3card(cards))
    return float(v) if v is not None else _heuristic_percentile(cards)


def equity_at_width(cards: Sequence[str], width: float = 100.0) -> float:
    """Win chance vs an opponent whose hand is from the best `width` percent of hands.

    Linearly interpolates between the two nearest generated levels (clamped to the
    available range, normally 5..100).
    """
    if not cards or len(cards) < 3:
        return 0.50
    if not _LEVELS:
        eq = _heuristic_equity(cards)
        return min(0.95, max(0.05, eq - 0.0012 * (100.0 - float(width))))

    key = canonical_3card(cards)
    lv = sorted(_LEVELS)
    w = min(max(float(width), lv[0]), lv[-1])
    if len(lv) == 1:
        v = _LEVELS[lv[0]].get(key)
        return float(v) if v is not None else _heuristic_equity(cards)
    for lo, hi in zip(lv, lv[1:]):
        if lo <= w <= hi:
            e_lo = _LEVELS[lo].get(key)
            e_hi = _LEVELS[hi].get(key)
            if e_lo is None or e_hi is None:
                break
            t = (w - lo) / float(hi - lo)
            return float(e_lo + t * (e_hi - e_lo))
    return _heuristic_equity(cards)


def get_preflop_equity(cards: Sequence[str]) -> float:
    """Equity vs a random hand (the 'top 100%' level). Kept for compatibility."""
    return equity_at_width(cards, 100.0)


def classify_3cards(cards: Sequence[str]) -> tuple[str, int]:
    """Classifies 3 hole cards into pattern and numeric tier (backward compatibility)."""
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
