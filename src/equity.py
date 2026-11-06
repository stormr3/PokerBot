# equity.py — discard-aware equity: keep scoring, flop rollouts, discard-filtered opponent range
import math
import random
from itertools import accumulate
from time import perf_counter as now

from evaluator import STRAIGHT, eval_cards


def keep_score(a: int, b: int, flop) -> float:
    """Cheap proxy for how good (a,b) is on this flop (made hand + draws). Models opponent discards."""
    cards = (a, b) + tuple(flop)
    s = eval_cards(cards)
    cat = s >> 20
    v = cat + ((s >> 16) & 15) / 13.0
    if cat < 4:
        sc = [0, 0, 0, 0]
        rm = 0
        for c in cards:
            sc[c & 3] += 1
            rm |= 1 << (c >> 2)
        for suit in range(4):
            if sc[suit] == 4 and ((a & 3) == suit or (b & 3) == suit):
                v += 0.55
                break
        outs = 0
        for r in range(13):
            if not (rm >> r) & 1 and STRAIGHT[rm | (1 << r)]:
                outs += 1
        v += 0.4 if outs >= 2 else (0.15 if outs == 1 else 0.0)
    return v


def keep_equities(my3, flop, tilt_k, n, deadline, cons=0.8, min_n=30):
    """Showdown equity of discarding each of my 3 cards (index i discarded), with future streets
    sampled. Opponent: 3 random unseen cards (best of tilt_k draws = stronger range after aggression),
    keeps the heuristic-best pair with prob `cons`, then turn/river are drawn."""
    used = set(my3) | set(flop)
    unseen = [c for c in range(52) if c not in used]
    flop = tuple(flop)
    cache = {}

    def ks(a, b):
        if a > b:
            a, b = b, a
        k = a * 64 + b
        v = cache.get(k)
        if v is None:
            v = cache[k] = keep_score(a, b, flop)
        return v

    mk = [(my3[1], my3[2]), (my3[0], my3[2]), (my3[0], my3[1])]
    tot = [0.0, 0.0, 0.0]
    cnt = 0
    need = 3 * tilt_k + 2
    while cnt < n:
        if cnt >= min_n and (cnt & 15) == 0 and now() > deadline:
            break
        pool = random.sample(unseen, need)
        best = None
        for j in range(tilt_k):
            t = pool[3 * j:3 * j + 3]
            sc = (ks(t[1], t[2]), ks(t[0], t[2]), ks(t[0], t[1]))
            m = max(sc)
            if best is None or m > best[0]:
                best = (m, t, sc)
        _, t, sc = best
        i = sc.index(max(sc)) if random.random() < cons else random.randrange(3)
        opp = [x for k2, x in enumerate(t) if k2 != i]
        board = flop + (pool[-2], pool[-1])
        os_ = eval_cards(opp + list(board))
        for d in range(3):
            ms = eval_cards(list(mk[d]) + list(board))
            tot[d] += 1.0 if ms > os_ else (0.5 if ms == os_ else 0.0)
        cnt += 1
    return [x / cnt for x in tot]


def build_base(flop, dead, opp_d, cons=0.8):
    """Opponent kept-pair range after the exposed discard `opp_d` (None = unfiltered).
    w(a,b) ~ 1 if d was the heuristic-best drop out of {a,b,d}, else small."""
    unseen = [c for c in range(52) if c not in dead]
    flop = tuple(flop)
    cache = {}

    def ks(a, b):
        if a > b:
            a, b = b, a
        k = a * 64 + b
        v = cache.get(k)
        if v is None:
            v = cache[k] = keep_score(a, b, flop)
        return v

    floor = max(0.02, (1.0 - cons) * 0.6)
    pairs, w = [], []
    n = len(unseen)
    for i in range(n):
        a = unseen[i]
        sad = ks(a, opp_d) if opp_d is not None else 0.0
        for j in range(i + 1, n):
            b = unseen[j]
            if opp_d is None:
                wt = 1.0
            else:
                d = ks(a, b) - max(sad, ks(b, opp_d))
                wt = 1.0 if d >= 0 else max(floor, math.exp(d / 0.25))
            pairs.append((a, b))
            w.append(wt)
    return pairs, w


def street_data(pairs, w, board):
    """Per-pair strengths on `board` and weighted percentiles (for action tilt)."""
    bl = list(board)
    strs = [eval_cards([a, b] + bl) for a, b in pairs]
    order = sorted(range(len(pairs)), key=strs.__getitem__)
    tot = sum(w)
    cum = 0.0
    pct = [0.0] * len(pairs)
    for i in order:
        pct[i] = (cum + 0.5 * w[i]) / tot
        cum += w[i]
    return strs, pct


def eq_river(my_score, strs, weights):
    num = den = 0.0
    for s, wt in zip(strs, weights):
        den += wt
        if my_score > s:
            num += wt
        elif my_score == s:
            num += 0.5 * wt
    return num / den if den else 0.5


def eq_turn(my2, board, pairs, weights, known, n, deadline, min_n=60):
    """Turn equity vs weighted pair range, sampling the river."""
    pool = [c for c in range(52) if c not in known]
    cum = list(accumulate(weights))
    idx = random.choices(range(len(pairs)), cum_weights=cum, k=n)
    base_me = list(my2) + list(board)
    base_op = list(board)
    tot = 0.0
    done = 0
    for ix in idx:
        if done >= min_n and (done & 31) == 0 and now() > deadline:
            break
        a, b = pairs[ix]
        r = random.choice(pool)
        while r == a or r == b:
            r = random.choice(pool)
        ms = eval_cards(base_me + [r])
        os_ = eval_cards([a, b] + base_op + [r])
        tot += 1.0 if ms > os_ else (0.5 if ms == os_ else 0.0)
        done += 1
    return tot / done
