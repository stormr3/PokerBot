# evaluator.py — fast integer hand evaluator (card int = rank_idx*4 + suit_idx, suits "shdc")
from typing import Sequence

RANKS = "23456789TJQKA"
SUITS = "shdc"  # also the engine's discard tie-break order
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANKS)}
SUIT_ORDER = {s: i for i, s in enumerate(SUITS)}
INT_CARD = [r + s for r in RANKS for s in SUITS]
CARD_INT = {c: i for i, c in enumerate(INT_CARD)}
VALID_CARDS = set(INT_CARD)
HAND_NAMES = ("high card", "one pair", "two pair", "three of a kind", "straight",
              "flush", "full house", "four of a kind", "straight flush")


def _build_straight() -> list[int]:
    t = [0] * 8192
    for m in range(8192):
        for top in range(12, 3, -1):
            p = 31 << (top - 4)
            if m & p == p:
                t[m] = top + 1
                break
        else:
            if m & 0x100F == 0x100F:  # A-2-3-4-5
                t[m] = 4
    return t


STRAIGHT = _build_straight()


def eval_cards(cards) -> int:
    """Score of the best 5-card hand among 5..7 int cards. Higher is better; score>>20 = category."""
    cnt = [0] * 13
    sm = [0, 0, 0, 0]
    sc = [0, 0, 0, 0]
    rm = 0
    for c in cards:
        r = c >> 2
        s = c & 3
        cnt[r] += 1
        sm[s] |= 1 << r
        sc[s] += 1
        rm |= 1 << r
    fm = 0
    for s in range(4):
        if sc[s] >= 5:
            fm = sm[s]
            break
    if fm:
        st = STRAIGHT[fm]
        if st:
            return (8 << 20) | st
    quads, trips, pairs, singles = [], [], [], []
    for r in range(12, -1, -1):
        n = cnt[r]
        if n == 0:
            continue
        if n == 4:
            quads.append(r)
        elif n == 3:
            trips.append(r)
        elif n == 2:
            pairs.append(r)
        else:
            singles.append(r)
    if quads:
        k = max(trips[0] if trips else -1, pairs[0] if pairs else -1, singles[0] if singles else -1)
        return (7 << 20) | (quads[0] << 16) | (k << 12)
    if trips and (len(trips) > 1 or pairs):
        p = max(trips[1] if len(trips) > 1 else -1, pairs[0] if pairs else -1)
        return (6 << 20) | (trips[0] << 16) | (p << 12)
    if fm:
        out = 5 << 20
        shift = 16
        for r in range(12, -1, -1):
            if fm >> r & 1:
                out |= r << shift
                shift -= 4
                if shift < 0:
                    break
        return out
    st = STRAIGHT[rm]
    if st:
        return (4 << 20) | st
    if trips:
        ks = sorted(pairs + singles, reverse=True)[:2]
        out = (3 << 20) | (trips[0] << 16)
        shift = 12
        for k in ks:
            out |= k << shift
            shift -= 4
        return out
    if len(pairs) >= 2:
        k = max(pairs[2] if len(pairs) > 2 else -1, singles[0] if singles else -1)
        return (2 << 20) | (pairs[0] << 16) | (pairs[1] << 12) | (max(k, 0) << 8)
    if pairs:
        out = (1 << 20) | (pairs[0] << 16)
        shift = 12
        for k in singles[:3]:
            out |= k << shift
            shift -= 4
        return out
    out = 0
    shift = 16
    for k in singles[:5]:
        out |= k << shift
        shift -= 4
    return out


# ---- string-based compatibility helpers ----
def to_ints(cards: Sequence[str]) -> list[int]:
    return [CARD_INT[c] for c in cards]


def best_hand(hole: Sequence[str], board: Sequence[str]) -> int:
    return eval_cards(to_ints(list(hole) + list(board)))


def compare_hands(a: Sequence[str], b: Sequence[str], board: Sequence[str]) -> int:
    x, y = best_hand(a, board), best_hand(b, board)
    return (x > y) - (x < y)


def default_discard(hole: Sequence[str]) -> str:
    return min(hole, key=lambda c: (RANK_VALUE[c[0]], SUIT_ORDER[c[1]]))
