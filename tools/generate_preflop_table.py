#!/usr/bin/env python3
# ==============================================================================
# tools/generate_preflop_table.py — Preflop Canonical Equity Generator
#
# Generates high-sample Monte Carlo equity estimates for all 1,755 canonical
# 3-card hands in Discard Hold'em and saves them to src/data/preflop_equity.npz.
# ==============================================================================

import multiprocessing as mp
import os
from pathlib import Path
import random
import sys
import time
from itertools import combinations

# Add src to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import numpy as np
from evaluator import rank5, VALID_CARDS

RANK_STR = "23456789TJQKA"
RANK_MAP = {r: i for i, r in enumerate(RANK_STR)}
DECK = sorted(list(VALID_CARDS))
COMBO_7_5 = list(combinations(range(7), 5))


def canonical_3card(cards: list[str]) -> str:
    """Maps any 3 cards to an unambiguous canonical 6-character string.

    Sorts ranks descending (2..A).
    Normalizes suits to canonical s, h, d representation.
    """
    sorted_cards = sorted(cards, key=lambda c: RANK_MAP[c[0]], reverse=True)
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


def get_canonical_combos() -> list[tuple[str, list[str]]]:
    """Generates all 1,755 unique canonical 3-card hands."""
    combos = list(combinations(DECK, 3))
    canon_map = {}
    for c in combos:
        k = canonical_3card(list(c))
        if k not in canon_map:
            canon_map[k] = list(c)
    return sorted(canon_map.items())


def best_7(c7: tuple) -> tuple:
    """Finds best 5-card score from 7 cards using precomputed index combinations."""
    return max(rank5((c7[i0], c7[i1], c7[i2], c7[i3], c7[i4])) for i0, i1, i2, i3, i4 in COMBO_7_5)


def eval_hand_worker(item: tuple[str, list[str], int, int]) -> tuple[str, float]:
    """Monte Carlo simulation worker for a single canonical hand."""
    canon_key, h1, num_sims, seed = item
    if seed is not None:
        random.seed(seed)

    combos_h1 = list(combinations(h1, 2))
    rem_deck = [c for c in DECK if c not in h1]
    wins = 0.0

    for _ in range(num_sims):
        sampled = random.sample(rem_deck, 8)
        h2 = sampled[:3]
        b0, b1, b2, b3, b4 = sampled[3:]

        # Player 1 optimal discard on flop
        best_h1 = max(combos_h1, key=lambda r: rank5((r[0], r[1], b0, b1, b2)))

        # Player 2 optimal discard on flop
        r0, r1, r2 = (h2[0], h2[1]), (h2[0], h2[2]), (h2[1], h2[2])
        sc0 = rank5((r0[0], r0[1], b0, b1, b2))
        sc1 = rank5((r1[0], r1[1], b0, b1, b2))
        sc2 = rank5((r2[0], r2[1], b0, b1, b2))
        if sc0 >= sc1 and sc0 >= sc2:
            best_h2 = r0
        elif sc1 >= sc2:
            best_h2 = r1
        else:
            best_h2 = r2

        # Showdown best 5-of-7
        s1 = best_7((best_h1[0], best_h1[1], b0, b1, b2, b3, b4))
        s2 = best_7((best_h2[0], best_h2[1], b0, b1, b2, b3, b4))
        if s1 > s2:
            wins += 1.0
        elif s1 == s2:
            wins += 0.5

    return canon_key, wins / num_sims


def generate_table(num_sims: int = 2000, output_path: Path | None = None) -> None:
    """Computes equity table and saves to compressed .npz archive."""
    if output_path is None:
        data_dir = SRC_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        output_path = data_dir / "preflop_equity.npz"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    canon_items = get_canonical_combos()
    print("=" * 65)
    print(f"Generating Preflop Canonical Equity Table ({len(canon_items)} hands)")
    print(f"Simulations per hand: {num_sims} (SE <= {0.5 / (num_sims**0.5):.4f})")
    print("=" * 65)

    n_proc = min(16, os.cpu_count() or 4)
    print(f"Launching pool with {n_proc} worker processes...")

    # Assign distinct reproducible seeds
    work_items = [(k, h, num_sims, 42 + idx * 1000) for idx, (k, h) in enumerate(canon_items)]

    with mp.Pool(processes=n_proc) as pool:
        results = pool.map(eval_hand_worker, work_items, chunksize=10)

    elapsed = time.time() - t0
    print(f"Calculation complete: {len(results)} hands evaluated in {elapsed:.1f} s!")

    # Sort results alphabetically by canonical key for binary search / consistency
    results.sort(key=lambda x: x[0])
    keys = np.array([x[0] for x in results], dtype="<U6")
    equities = np.array([x[1] for x in results], dtype=np.float32)

    np.savez_compressed(output_path, keys=keys, equities=equities)
    file_size = output_path.stat().st_size
    print(f"Successfully saved to: {output_path}")
    print(f"File size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    print(f"Equity stats — min: {equities.min():.4f}, max: {equities.max():.4f}, mean: {equities.mean():.4f}")
    print("=" * 65)


if __name__ == "__main__":
    sims = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    generate_table(num_sims=sims)
