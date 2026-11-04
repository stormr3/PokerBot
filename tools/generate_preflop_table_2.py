#!/usr/bin/env python3
# ==============================================================================
# tools/generate_preflop_table.py  --  Preflop equity tables for Discard Hold'em
#
# Offline tool (NOT shipped in the submission zip). Needs only numpy.
#
# Produces src/preflop_data.py, a plain Python module (no file reads at runtime):
#   EQUITY_RANDOM   {key: equity vs a random 3-card hand}
#   EQUITY_TOP<N>   {key: equity vs an opponent who only plays the top N% hands}
#                   (default N = 40 and 15: "facing a raise" / "facing a 3-bet")
#   PCT_RANDOM      {key: combo-weighted percentile of the hand, 0..1}
# Keys are the 6-char canonical strings used by preflop_table.canonical_3card().
#
# What is simulated for every canonical 3-card hand:
#   deal opponent 3 cards + 5 board cards  ->  flop discard by BOTH players
#   (draw-aware: each option is scored by rollouts of random turn/river vs a
#   random opponent hand, not by made-hand strength only)  ->  showdown.
# Ties count 0.5.
#
# Usage:
#   python tools/generate_preflop_table.py --selftest
#   python tools/generate_preflop_table.py --quick          # minutes, noisy
#   python tools/generate_preflop_table.py                  # default quality
#   python tools/generate_preflop_table.py --sims 20000 --rollouts 24
# ==============================================================================

import argparse
import multiprocessing as mp
import os
import sys
import time
from itertools import combinations
from pathlib import Path

import numpy as np

RANK_STR = "23456789TJQKA"
SUIT_STR = "shdc"
RANK_MAP = {r: i for i, r in enumerate(RANK_STR)}
PRIMES = np.array([2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41], dtype=np.int64)

# Card index c = 4 * rank + suit  (rank 0..12 = 2..A, suit 0..3 = s,h,d,c)


def card_str(c: int) -> str:
    return RANK_STR[c >> 2] + SUIT_STR[c & 3]


def canonical_3card(cards) -> str:
    """Same canonical key as preflop_table.canonical_3card (strings in, str out)."""
    sorted_cards = sorted(cards, key=lambda c: RANK_MAP[c[0]], reverse=True)
    r0, r1, r2 = sorted_cards[0][0], sorted_cards[1][0], sorted_cards[2][0]
    s0, s1, s2 = sorted_cards[0][1], sorted_cards[1][1], sorted_cards[2][1]
    if r0 == r1 == r2:
        return f"{r0}s{r1}h{r2}d"
    if r0 == r1:
        if s2 == s0 or s2 == s1:
            return f"{r0}s{r1}h{r2}s"
        return f"{r0}s{r1}h{r2}d"
    if r1 == r2:
        if s0 == s1 or s0 == s2:
            return f"{r0}s{r1}s{r2}h"
        return f"{r0}d{r1}s{r2}h"
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


def all_triples() -> np.ndarray:
    """All 22,100 three-card hands as an (22100, 3) array of card indices."""
    return np.array(list(combinations(range(52), 3)), dtype=np.int64)


# ------------------------------------------------------------------------------
# Vectorised 7-card evaluator
#   score = category << 20 | up to five 4-bit ranks   (higher = better)
#   Non-flush strength comes from a lookup on the rank multiset (prime product);
#   flush / straight flush from a lookup on the 13-bit mask of the flush suit.
# ------------------------------------------------------------------------------

def _straight_high(mask: int) -> int:
    for h in range(12, 3, -1):
        w = 0b11111 << (h - 4)
        if mask & w == w:
            return h
    wheel = (1 << 12) | 0b1111  # A,2,3,4,5
    if mask & wheel == wheel:
        return 3
    return -1


def _pack(cat: int, ranks) -> int:
    s = cat << 20
    for i, r in enumerate(ranks[:5]):
        s |= r << (16 - 4 * i)
    return s


def _score_counts(counts) -> int:
    present = [r for r in range(12, -1, -1) if counts[r]]
    mask = sum(1 << r for r in present)
    quads = [r for r in present if counts[r] == 4]
    trips = [r for r in present if counts[r] == 3]
    pairs = [r for r in present if counts[r] == 2]
    if quads:
        q = quads[0]
        return _pack(7, [q, max(r for r in present if r != q)])
    if trips and (len(trips) > 1 or pairs):
        return _pack(6, [trips[0], max(trips[1:] + pairs)])
    sh = _straight_high(mask)
    if sh >= 0:
        return _pack(4, [sh])
    if trips:
        t = trips[0]
        return _pack(3, [t] + [r for r in present if r != t][:2])
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        return _pack(2, [p1, p2, max(r for r in present if r not in (p1, p2))])
    if len(pairs) == 1:
        p = pairs[0]
        return _pack(1, [p] + [r for r in present if r != p][:3])
    return _pack(0, present[:5])


class Evaluator:
    def __init__(self) -> None:
        keys, vals = [], []
        counts = [0] * 13

        def rec(rank: int, left: int) -> None:
            if rank == 13:
                if left == 0:
                    k = 1
                    for r in range(13):
                        k *= int(PRIMES[r]) ** counts[r]
                    keys.append(k)
                    vals.append(_score_counts(counts))
                return
            for c in range(min(4, left) + 1):
                counts[rank] = c
                rec(rank + 1, left - c)
            counts[rank] = 0

        rec(0, 7)
        order = np.argsort(np.array(keys, dtype=np.int64))
        self.keys = np.array(keys, dtype=np.int64)[order]
        self.vals = np.array(vals, dtype=np.int64)[order]

        flush = np.zeros(8192, dtype=np.int64)
        for m in range(8192):
            if bin(m).count("1") < 5:
                continue
            sh = _straight_high(m)
            if sh >= 0:
                flush[m] = _pack(8, [sh])
            else:
                top = [r for r in range(12, -1, -1) if m >> r & 1][:5]
                flush[m] = _pack(5, top)
        self.flush = flush

    def eval7(self, cards: np.ndarray) -> np.ndarray:
        """cards: int array (..., 7) of card indices -> int scores (...)."""
        shp = cards.shape[:-1]
        c = cards.reshape(-1, 7)
        r = c >> 2
        s = c & 3
        key = PRIMES[r].prod(axis=1)
        # Rows with duplicate cards (invalid rollouts, weighted 0 later) can give
        # garbage keys/masks: clamp so the lookups never index out of range.
        idx = np.minimum(np.searchsorted(self.keys, key), len(self.keys) - 1)
        score = self.vals[idx]
        bits = np.left_shift(1, r)
        fm = np.zeros(len(c), dtype=np.int64)
        for su in range(4):
            m = s == su
            fm += np.where(m.sum(axis=1) >= 5, (bits * m).sum(axis=1), 0)
        return np.maximum(score, self.flush[fm & 8191]).reshape(shp)


# ------------------------------------------------------------------------------
# Simulation
# ------------------------------------------------------------------------------

_OPTIONS = ((0, 1), (0, 2), (1, 2))  # which two of the 3 hole cards to KEEP


def choose_keep(ev: Evaluator, rng: np.random.Generator, hole: np.ndarray,
                flop: np.ndarray, rollouts: int) -> np.ndarray:
    """Draw-aware discard. hole (N,3), flop (N,3) -> kept cards (N,2).

    For each keep-pair, play `rollouts` random (opponent 2 cards, turn, river)
    scenarios; the SAME scenarios are used for all three options (paired
    comparison = less noise). Pick the keep-pair with the best win rate.
    """
    n = hole.shape[0]
    draws = rng.integers(0, 52, size=(n, rollouts, 4))
    known = np.concatenate([hole, flop], axis=1)
    valid = np.ones((n, rollouts), dtype=bool)
    for i in range(4):
        d = draws[:, :, i]
        for j in range(6):
            valid &= d != known[:, j][:, None]
        for j in range(i):
            valid &= d != draws[:, :, j]
    w = valid.astype(np.float64)

    flop_b = np.broadcast_to(flop[:, None, :], (n, rollouts, 3))
    opp7 = np.concatenate([draws[:, :, 0:2], flop_b, draws[:, :, 2:4]], axis=2)
    so = ev.eval7(opp7)

    eq = np.zeros((n, 3))
    for o, (a, b) in enumerate(_OPTIONS):
        keep = np.stack([hole[:, a], hole[:, b]], axis=1)[:, None, :]
        keep = np.broadcast_to(keep, (n, rollouts, 2))
        sh = ev.eval7(np.concatenate([keep, flop_b, draws[:, :, 2:4]], axis=2))
        res = (sh > so).astype(np.float64) + 0.5 * (sh == so)
        eq[:, o] = (res * w).sum(axis=1)

    best = eq.argmax(axis=1)
    pick = np.array(_OPTIONS)[best]                      # (N,2) indices into hole
    return np.take_along_axis(hole, pick, axis=1)


def simulate_hand(ev: Evaluator, hero, n: int, rollouts: int, seed,
                  opp_range) -> float:
    """Equity of one 3-card hand. opp_range None = uniform random opponent."""
    rng = np.random.default_rng(seed)
    hero = np.array(hero, dtype=np.int64)

    if opp_range is None:
        keys = rng.random((n, 52))
        keys[:, hero] = 2.0
        order = np.argsort(keys, axis=1)[:, :8]
        opp, board = order[:, :3], order[:, 3:8]
        weight = np.ones(n)
    else:
        opp = opp_range[rng.integers(0, len(opp_range), n)]
        for _ in range(30):                               # resample card collisions
            bad = np.isin(opp, hero).any(axis=1)
            if not bad.any():
                break
            opp[bad] = opp_range[rng.integers(0, len(opp_range), int(bad.sum()))]
        bad = np.isin(opp, hero).any(axis=1)
        weight = (~bad).astype(np.float64)
        keys = rng.random((n, 52))
        keys[:, hero] = 2.0
        keys[np.arange(n)[:, None], opp] = 2.0
        board = np.argsort(keys, axis=1)[:, :5]

    flop = board[:, :3]
    hero_hole = np.broadcast_to(hero, (n, 3))
    keep_h = choose_keep(ev, rng, hero_hole, flop, rollouts)
    keep_o = choose_keep(ev, rng, opp, flop, rollouts)

    sh = ev.eval7(np.concatenate([keep_h, board], axis=1))
    so = ev.eval7(np.concatenate([keep_o, board], axis=1))
    res = (sh > so).astype(np.float64) + 0.5 * (sh == so)
    return float((res * weight).sum() / max(weight.sum(), 1.0))


# ------------------------------------------------------------------------------
# Multiprocessing plumbing (initializer keeps big arrays out of task pickles)
# ------------------------------------------------------------------------------

_EV = None
_RANGES = {}


def _init_worker(ranges):
    global _EV, _RANGES
    _EV = Evaluator()
    _RANGES = ranges


def _work(item):
    key, hero, n, rollouts, seed, range_name = item
    return key, simulate_hand(_EV, hero, n, rollouts, seed, _RANGES.get(range_name))


def get_classes():
    """{canonical key: representative triple (card indices)} - must be 1755."""
    reps = {}
    for t in combinations(range(52), 3):
        k = canonical_3card([card_str(c) for c in t])
        if k not in reps:
            reps[k] = list(t)
    return reps


def run_pass(classes, n, rollouts, seed, range_name, ranges, procs, label):
    items = [(k, h, n, rollouts, seed + 7919 * i, range_name)
             for i, (k, h) in enumerate(sorted(classes.items()))]
    t0 = time.time()
    out = {}
    if procs <= 1:
        _init_worker(ranges)
        for i, it in enumerate(items, 1):
            k, v = _work(it)
            out[k] = v
            if i % 100 == 0 or i == len(items):
                _progress(label, i, len(items), t0)
    else:
        with mp.Pool(procs, initializer=_init_worker, initargs=(ranges,)) as pool:
            for i, (k, v) in enumerate(pool.imap_unordered(_work, items, chunksize=4), 1):
                out[k] = v
                if i % 100 == 0 or i == len(items):
                    _progress(label, i, len(items), t0)
    return out


def _progress(label, i, total, t0):
    el = time.time() - t0
    eta = el / i * (total - i)
    print(f"  [{label}] {i}/{total}  elapsed {el:5.0f}s  eta {eta:5.0f}s", flush=True)


def build_range(triples, triple_keys, equity, top_pct):
    """Combo-weighted top-N% range: all triples whose class equity >= cutoff."""
    eq = np.array([equity[k] for k in triple_keys])
    cutoff = np.quantile(eq, 1.0 - top_pct / 100.0)
    return triples[eq >= cutoff]


def combo_percentiles(triple_keys, equity):
    eq = np.array([equity[k] for k in triple_keys])
    srt = np.sort(eq)
    pct = {}
    for k in set(triple_keys):
        v = equity[k]
        lo = np.searchsorted(srt, v, side="left")
        hi = np.searchsorted(srt, v, side="right")
        pct[k] = (lo + 0.5 * (hi - lo)) / len(srt)
    return pct


# ------------------------------------------------------------------------------
# Self test
# ------------------------------------------------------------------------------

def _ref_rank5(cards):
    ranks = sorted((c >> 2 for c in cards), reverse=True)
    flush = len({c & 3 for c in cards}) == 1
    cnt = {}
    for r in ranks:
        cnt[r] = cnt.get(r, 0) + 1
    groups = sorted(cnt.items(), key=lambda kv: (-kv[1], -kv[0]))
    shape = [g[1] for g in groups]
    order = tuple(g[0] for g in groups)
    uniq = sorted(cnt, reverse=True)
    sh = None
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            sh = uniq[0]
        elif uniq == [12, 3, 2, 1, 0]:
            sh = 3
    if flush and sh is not None:
        return (8, sh)
    if shape == [4, 1]:
        return (7,) + order
    if shape == [3, 2]:
        return (6,) + order
    if flush:
        return (5,) + tuple(ranks)
    if sh is not None:
        return (4, sh)
    if shape == [3, 1, 1]:
        return (3,) + order
    if shape == [2, 2, 1]:
        return (2,) + order
    if shape == [2, 1, 1, 1]:
        return (1,) + order
    return (0,) + tuple(ranks)


def _ref_best7(cards):
    return max(_ref_rank5(c) for c in combinations(cards, 5))


def selftest(trials=20000) -> bool:
    print("Self test")
    ok = True
    classes = get_classes()
    print(f"  canonical classes: {len(classes)} (expected 1755)")
    ok &= len(classes) == 1755

    ev = Evaluator()
    rng = np.random.default_rng(1)
    deals = np.argsort(rng.random((trials, 52)), axis=1)[:, :9]
    board = deals[:, :5]
    a = np.concatenate([deals[:, 5:7], board], axis=1)
    b = np.concatenate([deals[:, 7:9], board], axis=1)
    sa, sb = ev.eval7(a), ev.eval7(b)
    bad = 0
    for i in range(trials):
        ra = _ref_best7([int(x) for x in a[i]])
        rb = _ref_best7([int(x) for x in b[i]])
        ref = (ra > rb) - (ra < rb)
        got = int(sa[i] > sb[i]) - int(sa[i] < sb[i])
        bad += ref != got
    # Extra: flush-heavy deals (few suits) to exercise the flush tables
    fl = np.argsort(rng.random((trials // 4, 52)), axis=1)[:, :14]
    fl = (fl >> 2) * 4 + (fl & 1)                         # squash to 2 suits (dupes possible)
    keep = np.array([len(set(r[:7])) == 7 and len(set(r[7:])) == 7 for r in fl])
    fl = fl[keep]
    fa, fb = ev.eval7(fl[:, :7]), ev.eval7(fl[:, 7:14])
    for i in range(len(fl)):
        ra = _ref_best7([int(x) for x in fl[i, :7]])
        rb = _ref_best7([int(x) for x in fl[i, 7:14]])
        bad += ((ra > rb) - (ra < rb)) != (int(fa[i] > fb[i]) - int(fa[i] < fb[i]))
    print(f"  evaluator vs reference: {bad} mismatches in {trials + len(fl)} matchups")
    ok &= bad == 0

    def hand(s):
        return [RANK_STR.index(x[0]) * 4 + SUIT_STR.index(x[1]) for x in s.split()]
    e_aaa = simulate_hand(ev, hand("As Ah Ad"), 3000, 12, 5, None)
    e_222 = simulate_hand(ev, hand("2s 2h 2d"), 3000, 12, 6, None)
    e_72 = simulate_hand(ev, hand("7s 2h 3d"), 3000, 12, 7, None)
    print(f"  AAA {e_aaa:.3f}   222 {e_222:.3f}   732o {e_72:.3f}")
    ok &= e_aaa > 0.70 and e_72 < 0.45 and e_aaa > e_222 + 0.2
    print("  RESULT:", "PASS" if ok else "FAIL")
    return bool(ok)


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

def write_module(path: Path, tables: dict, meta: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# AUTO-GENERATED by tools/generate_preflop_table.py. Do not edit.\n")
        f.write(f"# {meta}\n\n")
        for name, d in tables.items():
            f.write(f"{name} = {{\n")
            for k in sorted(d):
                f.write(f'    "{k}": {d[k]:.4f},\n')
            f.write("}\n\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=8000, help="simulations per hand per table")
    ap.add_argument("--rollouts", type=int, default=16, help="rollouts per discard decision")
    ap.add_argument("--ranges", type=str, default="40,15",
                    help="comma list of opponent top-N%% ranges, '' for none")
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--quick", action="store_true", help="sims=1000 rollouts=8 (noisy)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if args.quick:
        args.sims, args.rollouts = 1000, 8

    root = Path(__file__).resolve().parent.parent
    out = Path(args.out) if args.out else root / "src" / "preflop_data.py"
    pcts = [int(x) for x in args.ranges.split(",") if x.strip()]

    classes = get_classes()
    assert len(classes) == 1755, len(classes)
    print(f"{len(classes)} classes, {args.sims} sims, {args.rollouts} rollouts, "
          f"{args.procs} procs, SE <= {0.5 / args.sims ** 0.5:.4f}")

    t0 = time.time()
    eq_random = run_pass(classes, args.sims, args.rollouts, args.seed, None, {}, args.procs, "random")

    triples = all_triples()
    triple_keys = [canonical_3card([card_str(c) for c in t]) for t in triples]
    tables = {"EQUITY_RANDOM": eq_random}
    ranges = {}
    for p in pcts:
        ranges[f"top{p}"] = build_range(triples, triple_keys, eq_random, p)
    for p in pcts:
        name = f"top{p}"
        print(f"range {name}: {len(ranges[name])} combos")
        tables[f"EQUITY_TOP{p}"] = run_pass(classes, args.sims, args.rollouts,
                                           args.seed + 1000 * p, name, ranges, args.procs, name)
    tables["PCT_RANDOM"] = {k: round(v, 4) for k, v in combo_percentiles(triple_keys, eq_random).items()}

    # Sanity report
    w = np.array([eq_random[k] for k in triple_keys])
    print(f"combo-weighted mean equity vs random: {w.mean():.4f} (expect ~0.5)")
    ranked = sorted(eq_random.items(), key=lambda kv: -kv[1])
    print("top 5   :", ", ".join(f"{k} {v:.3f}" for k, v in ranked[:5]))
    print("bottom 5:", ", ".join(f"{k} {v:.3f}" for k, v in ranked[-5:]))

    write_module(out, tables, f"sims={args.sims} rollouts={args.rollouts} seed={args.seed}")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
