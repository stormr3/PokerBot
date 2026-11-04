# ==============================================================================
# preflop_table.py — Precomputed Preflop Range & Classification Module
# Owner: Person B
#
# Responsibilities:
# - Classify 3-card hole card combinations into strength tiers (Tier 1..5).
# - Pure Python lookup tables and classification helpers (no runtime file reads).
# - Provide baseline opening and calling recommendations based on seat position.
# ==============================================================================

from collections import Counter
from typing import Sequence

from evaluator import RANK_VALUE


def classify_3cards(cards: Sequence[str]) -> tuple[str, int]:
    """Classifies 3 hole cards into a descriptive pattern and numeric tier (1=best, 5=worst).

    Tiers:
        Tier 1: Three of a kind, high pairs (AA, KK, QQ, JJ), triple broadway (e.g. AKQ).
        Tier 2: Medium pocket pairs (TT-77), two high broadway cards (AK, AQ), 3-flush broadway.
        Tier 3: Low pocket pairs (66-22), connected cards, suited connectors.
        Tier 4: One high card (A or K) with uncoordinated low cards.
        Tier 5: Uncoordinated low unsuited cards ("trash").
    """
    if len(cards) < 3:
        return ("unknown", 5)

    ranks = [c[0] for c in cards]
    suits = [c[1] for c in cards]
    values = sorted([RANK_VALUE[r] for r in ranks], reverse=True)
    counts = Counter(ranks).most_common()

    # Three of a kind (e.g. 8s 8h 8d)
    if counts[0][1] == 3:
        return ("trips", 1)

    # Pocket pair
    if counts[0][1] == 2:
        pair_val = RANK_VALUE[counts[0][0]]
        if pair_val >= 11:  # JJ, QQ, KK, AA
            return ("high_pair", 1)
        if pair_val >= 7:   # 77 - TT
            return ("medium_pair", 2)
        return ("low_pair", 3)

    # All three broadway (T, J, Q, K, A)
    if values[2] >= 10:
        return ("triple_broadway", 1)

    # 3-flush
    if len(set(suits)) == 1:
        if values[0] >= 12:  # Ace or King high 3-flush
            return ("high_3flush", 2)
        return ("suited_3flush", 3)

    # Connected cards (e.g. 7-8-9, J-T-9)
    if values[0] - values[1] == 1 and values[1] - values[2] == 1:
        return ("straight_connected", 2 if values[0] >= 10 else 3)

    # Ace or King with one broadway
    if values[0] >= 13 and values[1] >= 10:
        return ("broadway_ace_king", 2)

    # High card Ace or King
    if values[0] >= 13:
        return ("ace_or_king_high", 4)

    return ("uncoordinated", 5)


def get_preflop_recommendation(cards: Sequence[str], seat: str, to_call: int) -> str:
    """Returns a baseline action recommendation ('raise', 'call', 'check', 'fold').

    Args:
        cards: Player's 3 hole cards.
        seat: 'button' (acts 1st preflop) or 'big_blind' (acts 2nd preflop).
        to_call: Chips needed to call.
    """
    pattern, tier = classify_3cards(cards)

    if seat == "button":
        # Button: open-raise with top tiers, call or fold with weak tiers
        if tier <= 3:
            return "raise"
        if tier == 4 and to_call <= 1:
            return "call"
        return "fold" if to_call > 0 else "check"

    # Big blind
    if to_call == 0:
        return "check"
    if tier <= 2:
        return "raise"
    if tier <= 4:
        return "call"
    return "fold"
