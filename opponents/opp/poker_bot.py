"""
poker_bot.py
------------
Competition-playing agent for 3-Card Discard Hold'em.
Combines:
  1. Offline MCCFR Policy Engine: uses the MCCFR policy embedded in this file.
  2. Safety Layer: complete JSON protocol conformance, action sanitization, 0-notice guarantee.
  3. Table-Driven Hand Evaluator: monotonic integer 5-card & 7-card evaluations.
  4. 3-Card Discard Optimization: evaluates all 3 discard candidates using Common Random
     Numbers (CRN) against Bayesian opponent discard posteriors and range weighting.
  5. Range-Aware Equity Engine: exact river enumeration (903 combos) + Monte Carlo flop/turn.
  6. OpponentModel: Bayesian smoothing over opponent aggression, fold-to-bet, calling/raising habits.
  7. Master Strategy Controller: blends CFR policy with real-time EV, pot odds, SPR, and position.
"""

import sys
import json
import time
import random
import math
from collections import Counter
from itertools import combinations, combinations_with_replacement
from pathlib import Path


# ==============================================================================
# CONFIGURATION
# ==============================================================================
CONFIG = {
    # Bot Meta
    "bot_name": "poker_bot_v4",
    "version": "4.0.0",
    "policy_file": "mccfr_policy.json",
    "debug_stderr": False,
    "max_stderr_bytes": 48 * 1024,  # 48 KB safety budget (engine limit: 64 KB)

    # Time Management (ms)
    "min_decision_time_ms": 5.0,
    "max_decision_time_ms": 120.0,
    "time_bank_cushion_ms": 3000,   # Below 3s: fast heuristic fallback
    "panic_time_ms": 1000,          # Below 1s: instant check/fold fallback

    # Equity Engine & Sampling
    "discard_mc_samples": 260,      # Common Random Numbers samples for discard evaluation
    "postflop_mc_samples": 360,     # Monte Carlo iterations on flop/turn
    "preflop_mc_samples": 130,      # Range-weighted preflop equity samples
    "min_adaptive_samples": 60,     # Minimum samples before deadline checks
    "discard_tie_margin": 0.005,    # Avoid unnecessary randomization between close discards
    "opponent_optimal_discard_prior": 0.96,  # Target opponent (Ansh) uses proxy_keep
    "policy_blend": 0.25,           # Use learned policy as a prior, not as an override
    "bet_size_mix": (0.50, 0.75, 1.00),

    # Thresholds & Margins
    "preflop_open_min_p": 0.25,
    "preflop_limp_min_p": 0.10,
    "pot_odds_margin_ip": 0.01,
    "pot_odds_margin_oop": 0.03,
    "pot_odds_margin_river": 0.01,

    # Match-level Control
    "lock_mode_enabled": True,
    "default_sigma": 20.0,
    "tighten_win_prob": 0.85,
    "desperation_win_prob": 0.25,
}

# ==============================================================================
# CARD AND DECK DEFINITIONS
# ==============================================================================
RANKS = "23456789TJQKA"
SUITS = "shdc"  # Engine tie-break order: s, h, d, c
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANKS)}
SUIT_ORDER = {s: i for i, s in enumerate(SUITS)}
VALID_CARDS = {r + s for r in RANKS for s in SUITS}

# Card conversions: (rank_val 2..14, suit_val 0..3)
CARD_TO_INT = {r + s: (RANK_VALUE[r], SUIT_ORDER[s]) for r in RANKS for s in SUITS}
INT_TO_CARD = {v: k for k, v in CARD_TO_INT.items()}
ALL_CARDS_INT = list(CARD_TO_INT.values())

ACTIONS = ("fold", "check_call", "bet_raise")

# Embedded preflop H3 percentile table (Base64 encoded, 1,911 canonical classes)
PREFLOP_B64 = "ATAjNQdOCAMmXjAEGUIoCgcwKkqKHU4aYQA4Xg8AEpEQBRKRBQEKA05iDwMXOQsZSnOUax4QikaOtTMoAUoNAAIwCSAVnBoCBQ9abyAEAioXDHuOAQFCMyZeThEaFSZiBEogEXQtV3ZOg8+OvYZ2iqCqORcSBQ1aOQIjBkp/FwcbFWITAQBKEyOUojUIAzWiKNkTEQ1Tg0IZKDOuwQwKCgYwCA1LoAgNFRNOI29af3aGV6Bwe7G42WKKybiSzMerwpTnFU49PgoFKgEdAkY2DhszG3AJEx1CFQdCLUsgCAw2OaAjMwRwFmk+KAxeayhPE2JaKzAegzkEA3QKJjM5BEIXBpktORcTOiQmS3B/cMUgJgI6PjRlHRE2EVNGYkJsycrdksquseyZxa672bHMot7vwoQ0NhckOkYkExllLREDMCZPAwkJGQ4ZcEIeBA9lGBbPVy0JU086ESsg1WIKIEMwe16EdtoLDB1mXyEhSzokSwe4kgNXNjQWT0NDlXfpRlNUIStPDz4mJyl0q4Qx8ZwkPiFbJBirK4pGVHfhMRhGCzEGX6ILDoYkOlshW5xLvvTb8NTM28/Ux+zH777W5sLoosXn0sx0d2lGLQVUQycLQ4oJSx8H1wckCFQrY5xsCT46PieVNjorDik+T5kYHZWLCxFUFiFjDkyODi4JDEcQP0OOoDYM5IYWBTEnFDZMoldjoydDHUw7FmZbBlsYKzdEP8pPVH9fLFdHMS5pX0QhykyAGjtPO3BjLkRQdz90ZoZfo7K7cVtxTHRxKZ0SX4C4cYbtG1SVNEQ7X44bKRRjq7J7nSJYbI5j6eTF6eG+7uLq4NvC5vDr32zz4N7o4ujc5evKnVsOLGZxFC4UroAlPzdjzy4nMT9MKXyrGzs7KWk7tYseAVtMRFXFG7hmHw8/oylVWBTHMXFHNywPLlAcP1Ay19IaMh9fH4tQN2yZzRAUB1UWR5U3Ep21i0erWOK+fDwUp2lsxTyZz3dj3Vh8d01sTXQ0h1ijQKuLLGZEMuWabUBtVRwebc1Ai3GjUDfmVScNRFxcPLsqi4w0oGSjYIBmj7tg7ty1d2SanciVVUCE1NqAWFXK74QylU21Lh83p75gcZ3FuNK1QL6jhMKvwvDl/d3N6rbx7ePt7t7y6vLg6rbo/PHl7MXU+O/q6EQ0LBxtRwYcAmlHQGQiZ5ZFUFUGdwiygDxkH2kulnxQF2BtNFgvQGfIQBBZUXIofJp4sh8NC1FROEElaYeAQbikSFkvUYcLam0VyqgahByEBTyHeGRnKG2oh1HW5SpINVEiInwsnbJWpMJNVg81MhyFEkF1mpJ4mjyWZKjvklEaJTg4gKSPsr6soFyaz2eHeBiybUgiIoeMuYzWPKBRlsjfqNbpeFl1knWWlniWpNiaj4+PqPSWgVJnj6+al1mSfDjGr8/NeFziuWrNl1np3WeBtlYqqKRuRYEvfa/ffcjDyPR5hZdcrIi2ar9gl6SFiMtkfZ6PfcvS4TK22oH26tjc5u7w4fvj9fT34O7z2vz46vfs9Pjt9fPx+vPx9ekil24sXIhZYCJSXBhnRaGXMjwqZT09yJdINbtScnmoXXIynrl5pBWIv2d1JYxZZbldnuyQjEh9jCBSkq+7nh7lrxrLnl1yYIhqSG7IGX0eboEeRYF9tl1Bdcuo2Lt5tiNhapDPPWhdcnLtdVYvVl04eRwSs2q7Ya9ugUisv7ldRT1WJV1ZeZ5h0NiIrO49SCxoRQ2QrLNoTSWsaknSa0GkaLDhvHVBw2HYv4jJoca5fZ6839Xuw0lSv2t5sL+bw25ok5ieZaV+1ZChk9ip89x1jMZJiLOC3U2Fs+mpsIzQy7fjm2uYv4VhpZtJv7Ohk8t5wJufvNKCk6ywm9p++dOCa5+py8bN3M2ft5Csk8PTwN/kif1yuW6hb62hsLl+rdDGs5+QUqm6qZil6LrQ4pjAvOL48PTu/f75/vn1/ffz8/Hw9/b2+vn3/P77+/767PL38vr79euzOC0cYbwlfnOTa1KFjaGTc1YvZWhJn4JJc0F+U+HVxlNTfk1+SY2z4Ho9gpR6hVrA3rS3cy9FiWGNiXbhby/ckFpXXnqpkHqC6KnhenY1M62RI7y6pdCCy7qN7euJtG+l36V6m5jD3LTWvL0QrbQ4V3NrEL1zzaXO1eKb3ZheiZjTgoZ/zNOtrcbWmPaJpoZauqqfybfdnMO3sJ+q0HrD2pTr1rfVe0pvpoOwqnvO15zXxJzjjbfOe8QqsFPTsdDHpq3M2K606tmq0+uD8PTAZYmmjcTAwMSZyarTwcGi4871f3tvg6am48HXlHaR57FolI20yZSK1c7nsefB+PLBvXPVpqbfuqqc2sSuvdG3tOTk7PyKkdHETUrb5+Vv26fR19vm0dnB2ZHbx9G10czB5Obw8sSqtaeOsa7Tf6fX1M7f2dSD46fJ3e/50c6i3r2R3tTZ4+fo3q7R5NvX0pmn4Lq9ycfg6+bsvcfm7/b5/f78/vz+9fr28fL4+/n8+vr69Pj48vv9/fv///z+9vf///bt"


# 2-card (standard Hold'em) preflop percentile: key 'hi-lo' + p(air)/s(uited)/o(ffsuit)
PREFLOP2_PCT = {
    '10-10p': 0.9796,
    '10-2o': 0.2459,
    '10-2s': 0.3213,
    '10-3o': 0.27,
    '10-3s': 0.3695,
    '10-4o': 0.3032,
    '10-4s': 0.3424,
    '10-5o': 0.3484,
    '10-5s': 0.3725,
    '10-6o': 0.3575,
    '10-6s': 0.4148,
    '10-7o': 0.4208,
    '10-7s': 0.5701,
    '10-8o': 0.5023,
    '10-8s': 0.6003,
    '10-9o': 0.5792,
    '10-9s': 0.6727,
    '11-10o': 0.6395,
    '11-10s': 0.7541,
    '11-11p': 0.9842,
    '11-2o': 0.2941,
    '11-2s': 0.3635,
    '11-3o': 0.3997,
    '11-3s': 0.4781,
    '11-4o': 0.4087,
    '11-4s': 0.4389,
    '11-5o': 0.4449,
    '11-5s': 0.5204,
    '11-6o': 0.3816,
    '11-6s': 0.5234,
    '11-7o': 0.4932,
    '11-7s': 0.5852,
    '11-8o': 0.5385,
    '11-8s': 0.6697,
    '11-9o': 0.6486,
    '11-9s': 0.73,
    '12-10o': 0.7662,
    '12-10s': 0.8054,
    '12-11o': 0.8537,
    '12-11s': 0.8658,
    '12-12p': 0.9887,
    '12-2o': 0.3906,
    '12-2s': 0.5671,
    '12-3o': 0.4842,
    '12-3s': 0.4751,
    '12-4o': 0.4661,
    '12-4s': 0.5732,
    '12-5o': 0.552,
    '12-5s': 0.6335,
    '12-6o': 0.6094,
    '12-6s': 0.5973,
    '12-7o': 0.5113,
    '12-7s': 0.6667,
    '12-8o': 0.5913,
    '12-8s': 0.6938,
    '12-9o': 0.6576,
    '12-9s': 0.7843,
    '13-10o': 0.8296,
    '13-10s': 0.9065,
    '13-11o': 0.8748,
    '13-11s': 0.9291,
    '13-12o': 0.8884,
    '13-12s': 0.9442,
    '13-13p': 0.9932,
    '13-2o': 0.5294,
    '13-2s': 0.6033,
    '13-3o': 0.5611,
    '13-3s': 0.7195,
    '13-4o': 0.6275,
    '13-4s': 0.6637,
    '13-5o': 0.6184,
    '13-5s': 0.7225,
    '13-6o': 0.6878,
    '13-6s': 0.7572,
    '13-7o': 0.6787,
    '13-7s': 0.7421,
    '13-8o': 0.7481,
    '13-8s': 0.8597,
    '13-9o': 0.7994,
    '13-9s': 0.8356,
    '14-10o': 0.9155,
    '14-10s': 0.9412,
    '14-11o': 0.9005,
    '14-11s': 0.9472,
    '14-12o': 0.9351,
    '14-12s': 0.9668,
    '14-13o': 0.9532,
    '14-13s': 0.9638,
    '14-14p': 0.9977,
    '14-2o': 0.6998,
    '14-2s': 0.7722,
    '14-3o': 0.7134,
    '14-3s': 0.7602,
    '14-4o': 0.7903,
    '14-4s': 0.8688,
    '14-5o': 0.736,
    '14-5s': 0.8386,
    '14-6o': 0.7783,
    '14-6s': 0.8627,
    '14-7o': 0.8205,
    '14-7s': 0.8944,
    '14-8o': 0.8446,
    '14-8s': 0.9216,
    '14-9o': 0.8115,
    '14-9s': 0.9095,
    '2-2p': 0.5452,
    '3-2o': 0.0045,
    '3-2s': 0.0739,
    '3-3p': 0.7066,
    '4-2o': 0.0136,
    '4-2s': 0.095,
    '4-3o': 0.0498,
    '4-3s': 0.1403,
    '4-4p': 0.7262,
    '5-2o': 0.0317,
    '5-2s': 0.1071,
    '5-3o': 0.089,
    '5-3s': 0.2398,
    '5-4o': 0.1312,
    '5-4s': 0.2278,
    '5-5p': 0.8816,
    '6-2o': 0.0226,
    '6-2s': 0.1373,
    '6-3o': 0.0588,
    '6-3s': 0.2157,
    '6-4o': 0.1011,
    '6-4s': 0.2368,
    '6-5o': 0.1704,
    '6-5s': 0.3092,
    '6-6p': 0.9253,
    '7-2o': 0.0407,
    '7-2s': 0.1554,
    '7-3o': 0.0679,
    '7-3s': 0.2308,
    '7-4o': 0.1222,
    '7-4s': 0.2338,
    '7-5o': 0.2006,
    '7-5s': 0.2881,
    '7-6o': 0.2097,
    '7-6s': 0.3394,
    '7-7p': 0.96,
    '8-2o': 0.0799,
    '8-2s': 0.1433,
    '8-3o': 0.1131,
    '8-3s': 0.1765,
    '8-4o': 0.1614,
    '8-4s': 0.2519,
    '8-5o': 0.2217,
    '8-5s': 0.3273,
    '8-6o': 0.279,
    '8-6s': 0.3756,
    '8-7o': 0.3152,
    '8-7s': 0.46,
    '8-8p': 0.9706,
    '9-2o': 0.1493,
    '9-2s': 0.264,
    '9-3o': 0.1916,
    '9-3s': 0.2851,
    '9-4o': 0.1825,
    '9-4s': 0.3243,
    '9-5o': 0.2579,
    '9-5s': 0.3665,
    '9-6o': 0.3333,
    '9-6s': 0.4359,
    '9-7o': 0.4299,
    '9-7s': 0.4721,
    '9-8o': 0.454,
    '9-8s': 0.5173,
    '9-9p': 0.9751,
}


def canonicalize_3card(cards_3):
    """Sort cards descending by rank; map suits to 0, 1, 2 in order of appearance."""
    sorted_c = sorted(cards_3, key=lambda c: (c[0], -c[1]), reverse=True)
    suit_map = {}
    canon = []
    for r, s in sorted_c:
        if s not in suit_map:
            suit_map[s] = len(suit_map)
        canon.append((r, suit_map[s]))
    return tuple(canon)


class PreflopTable:
    """Preflop H3 equity percentile lookup table decoded at launch in ~20 ms."""
    def __init__(self, b64_str: str):
        deck = [(r, s) for r in range(2, 15) for s in range(4)]
        classes = sorted(set(canonicalize_3card(c) for c in combinations(deck, 3)))
        self.class_to_idx = {c: i for i, c in enumerate(classes)}
        import base64
        raw_bytes = base64.b64decode(b64_str)
        self.percentiles = [b / 255.0 for b in raw_bytes]

    def get_percentile(self, cards_3) -> float:
        """Returns percentile rank p in [0.0, 1.0] (1.0 = best). Handles 2- or 3-card hands."""
        if len(cards_3) == 2:
            (r0, s0), (r1, s1) = cards_3
            hi, lo = max(r0, r1), min(r0, r1)
            t = "p" if hi == lo else ("s" if s0 == s1 else "o")
            return PREFLOP2_PCT.get(f"{hi}-{lo}{t}", 0.5)
        cn = canonicalize_3card(cards_3)
        idx = self.class_to_idx.get(cn)
        if idx is not None and idx < len(self.percentiles):
            return self.percentiles[idx]
        return 0.5


PREFLOP_TABLE = PreflopTable(PREFLOP_B64)


# ==============================================================================
# LOGGING (STDERR ONLY, STRICTLY CAPPED)
# ==============================================================================
_LOG_BYTES_WRITTEN = 0

def debug_log(msg: str):
    """Log to stderr while strictly respecting the 64 KB engine cap."""
    global _LOG_BYTES_WRITTEN
    if not CONFIG["debug_stderr"]:
        return
    text = f"[poker_bot] {msg}\n"
    encoded_len = len(text.encode("utf-8"))
    if _LOG_BYTES_WRITTEN + encoded_len < CONFIG["max_stderr_bytes"]:
        sys.stderr.write(text)
        sys.stderr.flush()
        _LOG_BYTES_WRITTEN += encoded_len


# ==============================================================================
# POLICY MANAGER (MCCFR POLICY EMBEDDED IN THIS FILE - NO FILE I/O)
# ==============================================================================
EMBEDDED_POLICY_META = {"version": "3.1.0", "game": "3-card-discard-holdem", "iterations": 50000}
EMBEDDED_POLICY = {
    'FLOP:BIG_BLIND:EQ_HIGH_BROADWAY_OFFSUIT:CHECKED_TO': (0.0, 0.217, 0.783),
    'FLOP:BIG_BLIND:EQ_HIGH_BROADWAY_OFFSUIT:FACING_BET': (0.1653, 0.5005, 0.3341),
    'FLOP:BIG_BLIND:EQ_HIGH_BROADWAY_SUITED:CHECKED_TO': (0.0, 0.3145, 0.6855),
    'FLOP:BIG_BLIND:EQ_HIGH_BROADWAY_SUITED:FACING_BET': (0.1288, 0.5237, 0.3475),
    'FLOP:BIG_BLIND:EQ_HIGH_HIGH_OFFSUIT:CHECKED_TO': (0.0, 0.23, 0.77),
    'FLOP:BIG_BLIND:EQ_HIGH_HIGH_OFFSUIT:FACING_BET': (0.0456, 0.5894, 0.365),
    'FLOP:BIG_BLIND:EQ_HIGH_PAIR_HIGH:CHECKED_TO': (0.0, 0.1647, 0.8353),
    'FLOP:BIG_BLIND:EQ_HIGH_PAIR_HIGH:FACING_BET': (0.0937, 0.4629, 0.4435),
    'FLOP:BIG_BLIND:EQ_HIGH_PAIR_LOW:CHECKED_TO': (0.0, 0.3014, 0.6986),
    'FLOP:BIG_BLIND:EQ_HIGH_PAIR_LOW:FACING_BET': (0.1148, 0.7217, 0.1635),
    'FLOP:BIG_BLIND:EQ_HIGH_PAIR_MID:CHECKED_TO': (0.0, 0.5704, 0.4296),
    'FLOP:BIG_BLIND:EQ_HIGH_PAIR_MID:FACING_BET': (0.1143, 0.4893, 0.3963),
    'FLOP:BIG_BLIND:EQ_HIGH_SUITED_ACE:CHECKED_TO': (0.0, 0.2441, 0.7559),
    'FLOP:BIG_BLIND:EQ_HIGH_SUITED_ACE:FACING_BET': (0.0764, 0.5515, 0.3721),
    'FLOP:BIG_BLIND:EQ_HIGH_SUITED_CONNECTOR:CHECKED_TO': (0.0, 0.3016, 0.6984),
    'FLOP:BIG_BLIND:EQ_HIGH_SUITED_CONNECTOR:FACING_BET': (0.131, 0.5253, 0.3437),
    'FLOP:BIG_BLIND:EQ_HIGH_TRIPS:CHECKED_TO': (0.0, 0.7257, 0.2743),
    'FLOP:BIG_BLIND:EQ_HIGH_TRIPS:FACING_BET': (0.4492, 0.1596, 0.3912),
    'FLOP:BIG_BLIND:EQ_HIGH_WEAK_OFFSUIT:CHECKED_TO': (0.0, 0.1465, 0.8535),
    'FLOP:BIG_BLIND:EQ_HIGH_WEAK_OFFSUIT:FACING_BET': (0.1171, 0.7684, 0.1145),
    'FLOP:BIG_BLIND:EQ_LOW_BROADWAY_OFFSUIT:CHECKED_TO': (0.0, 0.6606, 0.3394),
    'FLOP:BIG_BLIND:EQ_LOW_BROADWAY_OFFSUIT:FACING_BET': (0.433, 0.3514, 0.2156),
    'FLOP:BIG_BLIND:EQ_LOW_BROADWAY_SUITED:CHECKED_TO': (0.0, 0.5614, 0.4386),
    'FLOP:BIG_BLIND:EQ_LOW_BROADWAY_SUITED:FACING_BET': (0.4405, 0.2748, 0.2847),
    'FLOP:BIG_BLIND:EQ_LOW_HIGH_OFFSUIT:CHECKED_TO': (0.0, 0.3295, 0.6705),
    'FLOP:BIG_BLIND:EQ_LOW_HIGH_OFFSUIT:FACING_BET': (0.1927, 0.7835, 0.0238),
    'FLOP:BIG_BLIND:EQ_LOW_PAIR_HIGH:CHECKED_TO': (0.0, 0.4727, 0.5273),
    'FLOP:BIG_BLIND:EQ_LOW_PAIR_HIGH:FACING_BET': (0.0044, 0.4343, 0.5614),
    'FLOP:BIG_BLIND:EQ_LOW_PAIR_LOW:CHECKED_TO': (0.0, 0.6224, 0.3776),
    'FLOP:BIG_BLIND:EQ_LOW_PAIR_LOW:FACING_BET': (0.3462, 0.5975, 0.0563),
    'FLOP:BIG_BLIND:EQ_LOW_PAIR_MID:CHECKED_TO': (0.0, 0.4892, 0.5108),
    'FLOP:BIG_BLIND:EQ_LOW_PAIR_MID:FACING_BET': (0.3817, 0.4556, 0.1627),
    'FLOP:BIG_BLIND:EQ_LOW_SUITED_ACE:CHECKED_TO': (0.0, 0.2963, 0.7037),
    'FLOP:BIG_BLIND:EQ_LOW_SUITED_ACE:FACING_BET': (0.2432, 0.6838, 0.0729),
    'FLOP:BIG_BLIND:EQ_LOW_SUITED_CONNECTOR:CHECKED_TO': (0.0, 0.3938, 0.6062),
    'FLOP:BIG_BLIND:EQ_LOW_SUITED_CONNECTOR:FACING_BET': (0.2944, 0.6247, 0.0809),
    'FLOP:BIG_BLIND:EQ_LOW_TRIPS:CHECKED_TO': (0.0, 0.4254, 0.5746),
    'FLOP:BIG_BLIND:EQ_LOW_TRIPS:FACING_BET': (0.4415, 0.4524, 0.1062),
    'FLOP:BIG_BLIND:EQ_LOW_WEAK_OFFSUIT:CHECKED_TO': (0.0, 0.4986, 0.5014),
    'FLOP:BIG_BLIND:EQ_LOW_WEAK_OFFSUIT:FACING_BET': (0.1783, 0.7905, 0.0312),
    'FLOP:BIG_BLIND:EQ_MID_BROADWAY_OFFSUIT:CHECKED_TO': (0.0, 0.2802, 0.7198),
    'FLOP:BIG_BLIND:EQ_MID_BROADWAY_OFFSUIT:FACING_BET': (0.3462, 0.5234, 0.1304),
    'FLOP:BIG_BLIND:EQ_MID_BROADWAY_SUITED:CHECKED_TO': (0.0, 0.2756, 0.7244),
    'FLOP:BIG_BLIND:EQ_MID_BROADWAY_SUITED:FACING_BET': (0.2011, 0.6239, 0.175),
    'FLOP:BIG_BLIND:EQ_MID_HIGH_OFFSUIT:CHECKED_TO': (0.0, 0.2686, 0.7314),
    'FLOP:BIG_BLIND:EQ_MID_HIGH_OFFSUIT:FACING_BET': (0.0835, 0.8843, 0.0322),
    'FLOP:BIG_BLIND:EQ_MID_PAIR_HIGH:CHECKED_TO': (0.0, 0.1589, 0.8411),
    'FLOP:BIG_BLIND:EQ_MID_PAIR_HIGH:FACING_BET': (0.2061, 0.5104, 0.2835),
    'FLOP:BIG_BLIND:EQ_MID_PAIR_LOW:CHECKED_TO': (0.0, 0.5756, 0.4244),
    'FLOP:BIG_BLIND:EQ_MID_PAIR_LOW:FACING_BET': (0.1813, 0.694, 0.1247),
    'FLOP:BIG_BLIND:EQ_MID_PAIR_MID:CHECKED_TO': (0.0, 0.3371, 0.6629),
    'FLOP:BIG_BLIND:EQ_MID_PAIR_MID:FACING_BET': (0.1627, 0.7216, 0.1157),
    'FLOP:BIG_BLIND:EQ_MID_SUITED_ACE:CHECKED_TO': (0.0, 0.2951, 0.7049),
    'FLOP:BIG_BLIND:EQ_MID_SUITED_ACE:FACING_BET': (0.1622, 0.7833, 0.0544),
    'FLOP:BIG_BLIND:EQ_MID_SUITED_CONNECTOR:CHECKED_TO': (0.0, 0.6516, 0.3484),
    'FLOP:BIG_BLIND:EQ_MID_SUITED_CONNECTOR:FACING_BET': (0.1852, 0.7511, 0.0638),
    'FLOP:BIG_BLIND:EQ_MID_TRIPS:CHECKED_TO': (0.0, 0.7201, 0.2799),
    'FLOP:BIG_BLIND:EQ_MID_TRIPS:FACING_BET': (0.5121, 0.3039, 0.1841),
    'FLOP:BIG_BLIND:EQ_MID_WEAK_OFFSUIT:CHECKED_TO': (0.0, 0.2628, 0.7372),
    'FLOP:BIG_BLIND:EQ_MID_WEAK_OFFSUIT:FACING_BET': (0.0846, 0.8607, 0.0546),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_BROADWAY_OFFSUIT:CHECKED_TO': (0.0, 0.1639, 0.8361),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_BROADWAY_OFFSUIT:FACING_BET': (0.1027, 0.5544, 0.3429),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_BROADWAY_SUITED:CHECKED_TO': (0.0, 0.1717, 0.8283),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_BROADWAY_SUITED:FACING_BET': (0.0922, 0.4221, 0.4857),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_HIGH_OFFSUIT:CHECKED_TO': (0.0, 0.1374, 0.8626),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_HIGH_OFFSUIT:FACING_BET': (0.0826, 0.3319, 0.5856),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_PAIR_HIGH:CHECKED_TO': (0.0, 0.1487, 0.8513),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_PAIR_HIGH:FACING_BET': (0.0758, 0.4026, 0.5216),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_PAIR_LOW:CHECKED_TO': (0.0, 0.5315, 0.4685),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_PAIR_LOW:FACING_BET': (0.0847, 0.6533, 0.2619),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_PAIR_MID:CHECKED_TO': (0.0, 0.2823, 0.7177),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_PAIR_MID:FACING_BET': (0.0802, 0.3675, 0.5523),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_SUITED_ACE:CHECKED_TO': (0.0, 0.187, 0.813),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_SUITED_ACE:FACING_BET': (0.0612, 0.416, 0.5228),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_SUITED_CONNECTOR:CHECKED_TO': (0.0, 0.1934, 0.8066),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_SUITED_CONNECTOR:FACING_BET': (0.0821, 0.5498, 0.3681),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_TRIPS:CHECKED_TO': (0.0, 0.2676, 0.7324),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_TRIPS:FACING_BET': (0.1383, 0.5504, 0.3114),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_WEAK_OFFSUIT:CHECKED_TO': (0.0, 0.3008, 0.6992),
    'FLOP:BIG_BLIND:EQ_VERY_HIGH_WEAK_OFFSUIT:FACING_BET': (0.0848, 0.3179, 0.5973),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_BROADWAY_OFFSUIT:CHECKED_TO': (0.0, 0.3818, 0.6182),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_BROADWAY_OFFSUIT:FACING_BET': (0.7153, 0.0671, 0.2176),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_BROADWAY_SUITED:CHECKED_TO': (0.0, 0.7963, 0.2037),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_BROADWAY_SUITED:FACING_BET': (0.4765, 0.3527, 0.1708),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_HIGH_OFFSUIT:CHECKED_TO': (0.0, 0.624, 0.376),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_HIGH_OFFSUIT:FACING_BET': (0.3422, 0.61, 0.0478),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_PAIR_HIGH:CHECKED_TO': (0.0, 0.0571, 0.9429),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_PAIR_HIGH:FACING_BET': (0.3299, 0.331, 0.3391),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_PAIR_LOW:CHECKED_TO': (0.0, 0.4541, 0.5459),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_PAIR_LOW:FACING_BET': (0.4093, 0.5374, 0.0533),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_PAIR_MID:CHECKED_TO': (0.0, 0.3438, 0.6562),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_PAIR_MID:FACING_BET': (0.6622, 0.1478, 0.1899),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_SUITED_ACE:CHECKED_TO': (0.0, 0.3612, 0.6388),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_SUITED_ACE:FACING_BET': (0.5515, 0.2846, 0.1638),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_SUITED_CONNECTOR:CHECKED_TO': (0.0, 0.1797, 0.8203),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_SUITED_CONNECTOR:FACING_BET': (0.5505, 0.3646, 0.085),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_TRIPS:CHECKED_TO': (0.3333, 0.3333, 0.3333),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_TRIPS:FACING_BET': (0.3333, 0.3333, 0.3333),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_WEAK_OFFSUIT:CHECKED_TO': (0.0, 0.4402, 0.5598),
    'FLOP:BIG_BLIND:EQ_VERY_LOW_WEAK_OFFSUIT:FACING_BET': (0.7138, 0.2513, 0.0349),
    'FLOP:BUTTON:EQ_HIGH_BROADWAY_OFFSUIT:CHECKED_TO': (0.0, 0.306, 0.694),
    'FLOP:BUTTON:EQ_HIGH_BROADWAY_OFFSUIT:FACING_BET': (0.146, 0.2369, 0.6171),
    'FLOP:BUTTON:EQ_HIGH_BROADWAY_SUITED:CHECKED_TO': (0.0, 0.3644, 0.6356),
    'FLOP:BUTTON:EQ_HIGH_BROADWAY_SUITED:FACING_BET': (0.1079, 0.559, 0.3332),
    'FLOP:BUTTON:EQ_HIGH_HIGH_OFFSUIT:CHECKED_TO': (0.0, 0.4666, 0.5334),
    'FLOP:BUTTON:EQ_HIGH_HIGH_OFFSUIT:FACING_BET': (0.0399, 0.1599, 0.8002),
    'FLOP:BUTTON:EQ_HIGH_PAIR_HIGH:CHECKED_TO': (0.0, 0.2086, 0.7914),
    'FLOP:BUTTON:EQ_HIGH_PAIR_HIGH:FACING_BET': (0.0427, 0.15, 0.8073),
    'FLOP:BUTTON:EQ_HIGH_PAIR_LOW:CHECKED_TO': (0.0, 0.5739, 0.4261),
    'FLOP:BUTTON:EQ_HIGH_PAIR_LOW:FACING_BET': (0.1363, 0.3829, 0.4808),
    'FLOP:BUTTON:EQ_HIGH_PAIR_MID:CHECKED_TO': (0.0, 0.4023, 0.5977),
    'FLOP:BUTTON:EQ_HIGH_PAIR_MID:FACING_BET': (0.07, 0.2239, 0.7061),
    'FLOP:BUTTON:EQ_HIGH_SUITED_ACE:CHECKED_TO': (0.0, 0.229, 0.771),
    'FLOP:BUTTON:EQ_HIGH_SUITED_ACE:FACING_BET': (0.0457, 0.1482, 0.8061),
    'FLOP:BUTTON:EQ_HIGH_SUITED_CONNECTOR:CHECKED_TO': (0.0, 0.4635, 0.5365),
    'FLOP:BUTTON:EQ_HIGH_SUITED_CONNECTOR:FACING_BET': (0.0892, 0.1497, 0.7611),
    'FLOP:BUTTON:EQ_HIGH_TRIPS:CHECKED_TO': (0.0, 0.5654, 0.4346),
    'FLOP:BUTTON:EQ_HIGH_TRIPS:FACING_BET': (0.1931, 0.4362, 0.3707),
    'FLOP:BUTTON:EQ_HIGH_WEAK_OFFSUIT:CHECKED_TO': (0.0, 0.2877, 0.7123),
    'FLOP:BUTTON:EQ_HIGH_WEAK_OFFSUIT:FACING_BET': (0.0538, 0.1151, 0.8311),
    'FLOP:BUTTON:EQ_LOW_BROADWAY_OFFSUIT:CHECKED_TO': (0.0, 0.3115, 0.6885),
    'FLOP:BUTTON:EQ_LOW_BROADWAY_OFFSUIT:FACING_BET': (0.451, 0.1893, 0.3597),
    'FLOP:BUTTON:EQ_LOW_BROADWAY_SUITED:CHECKED_TO': (0.0, 0.5166, 0.4834),
    'FLOP:BUTTON:EQ_LOW_BROADWAY_SUITED:FACING_BET': (0.3198, 0.4945, 0.1857),
    'FLOP:BUTTON:EQ_LOW_HIGH_OFFSUIT:CHECKED_TO': (0.0, 0.2426, 0.7574),
    'FLOP:BUTTON:EQ_LOW_HIGH_OFFSUIT:FACING_BET': (0.0988, 0.8218, 0.0794),
    'FLOP:BUTTON:EQ_LOW_PAIR_HIGH:CHECKED_TO': (0.0, 0.2091, 0.7909),
    'FLOP:BUTTON:EQ_LOW_PAIR_HIGH:FACING_BET': (0.2183, 0.3563, 0.4254),
    'FLOP:BUTTON:EQ_LOW_PAIR_LOW:CHECKED_TO': (0.0, 0.2651, 0.7349),
    'FLOP:BUTTON:EQ_LOW_PAIR_LOW:FACING_BET': (0.1682, 0.6941, 0.1377),
    'FLOP:BUTTON:EQ_LOW_PAIR_MID:CHECKED_TO': (0.0, 0.1717, 0.8283),
    'FLOP:BUTTON:EQ_LOW_PAIR_MID:FACING_BET': (0.6988, 0.158, 0.1433),
    'FLOP:BUTTON:EQ_LOW_SUITED_ACE:CHECKED_TO': (0.0, 0.5723, 0.4277),
    'FLOP:BUTTON:EQ_LOW_SUITED_ACE:FACING_BET': (0.1391, 0.6144, 0.2466),
    'FLOP:BUTTON:EQ_LOW_SUITED_CONNECTOR:CHECKED_TO': (0.0, 0.3447, 0.6553),
    'FLOP:BUTTON:EQ_LOW_SUITED_CONNECTOR:FACING_BET': (0.2797, 0.5008, 0.2195),
    'FLOP:BUTTON:EQ_LOW_TRIPS:CHECKED_TO': (0.0, 0.106, 0.894),
    'FLOP:BUTTON:EQ_LOW_TRIPS:FACING_BET': (0.9733, 0.0159, 0.0108),
    'FLOP:BUTTON:EQ_LOW_WEAK_OFFSUIT:CHECKED_TO': (0.0, 0.5231, 0.4769),
    'FLOP:BUTTON:EQ_LOW_WEAK_OFFSUIT:FACING_BET': (0.1359, 0.7654, 0.0987),
    'FLOP:BUTTON:EQ_MID_BROADWAY_OFFSUIT:CHECKED_TO': (0.0, 0.4899, 0.5101),
    'FLOP:BUTTON:EQ_MID_BROADWAY_OFFSUIT:FACING_BET': (0.2086, 0.4671, 0.3243),
    'FLOP:BUTTON:EQ_MID_BROADWAY_SUITED:CHECKED_TO': (0.0, 0.3893, 0.6107),
    'FLOP:BUTTON:EQ_MID_BROADWAY_SUITED:FACING_BET': (0.2906, 0.3521, 0.3572),
    'FLOP:BUTTON:EQ_MID_HIGH_OFFSUIT:CHECKED_TO': (0.0, 0.3594, 0.6406),
    'FLOP:BUTTON:EQ_MID_HIGH_OFFSUIT:FACING_BET': (0.0454, 0.3444, 0.6102),
    'FLOP:BUTTON:EQ_MID_PAIR_HIGH:CHECKED_TO': (0.0, 0.4649, 0.5351),
    'FLOP:BUTTON:EQ_MID_PAIR_HIGH:FACING_BET': (0.0851, 0.353, 0.562),
    'FLOP:BUTTON:EQ_MID_PAIR_LOW:CHECKED_TO': (0.0, 0.4953, 0.5047),
    'FLOP:BUTTON:EQ_MID_PAIR_LOW:FACING_BET': (0.0744, 0.6466, 0.279),
    'FLOP:BUTTON:EQ_MID_PAIR_MID:CHECKED_TO': (0.0, 0.3356, 0.6644),
    'FLOP:BUTTON:EQ_MID_PAIR_MID:FACING_BET': (0.113, 0.4372, 0.4497),
    'FLOP:BUTTON:EQ_MID_SUITED_ACE:CHECKED_TO': (0.0, 0.4208, 0.5792),
    'FLOP:BUTTON:EQ_MID_SUITED_ACE:FACING_BET': (0.0705, 0.2961, 0.6334),
    'FLOP:BUTTON:EQ_MID_SUITED_CONNECTOR:CHECKED_TO': (0.0, 0.5749, 0.4251),
    'FLOP:BUTTON:EQ_MID_SUITED_CONNECTOR:FACING_BET': (0.0917, 0.4659, 0.4424),
    'FLOP:BUTTON:EQ_MID_TRIPS:CHECKED_TO': (0.0, 0.7579, 0.2421),
    'FLOP:BUTTON:EQ_MID_TRIPS:FACING_BET': (0.3314, 0.3365, 0.332),
    'FLOP:BUTTON:EQ_MID_WEAK_OFFSUIT:CHECKED_TO': (0.0, 0.3443, 0.6557),
    'FLOP:BUTTON:EQ_MID_WEAK_OFFSUIT:FACING_BET': (0.0578, 0.3165, 0.6257),
    'FLOP:BUTTON:EQ_VERY_HIGH_BROADWAY_OFFSUIT:CHECKED_TO': (0.0, 0.2327, 0.7673),
    'FLOP:BUTTON:EQ_VERY_HIGH_BROADWAY_OFFSUIT:FACING_BET': (0.0365, 0.3483, 0.6152),
    'FLOP:BUTTON:EQ_VERY_HIGH_BROADWAY_SUITED:CHECKED_TO': (0.0, 0.3843, 0.6157),
    'FLOP:BUTTON:EQ_VERY_HIGH_BROADWAY_SUITED:FACING_BET': (0.0411, 0.1684, 0.7905),
    'FLOP:BUTTON:EQ_VERY_HIGH_HIGH_OFFSUIT:CHECKED_TO': (0.0, 0.169, 0.831),
    'FLOP:BUTTON:EQ_VERY_HIGH_HIGH_OFFSUIT:FACING_BET': (0.0264, 0.0738, 0.8998),
    'FLOP:BUTTON:EQ_VERY_HIGH_PAIR_HIGH:CHECKED_TO': (0.0, 0.2013, 0.7987),
    'FLOP:BUTTON:EQ_VERY_HIGH_PAIR_HIGH:FACING_BET': (0.0255, 0.1153, 0.8593),
    'FLOP:BUTTON:EQ_VERY_HIGH_PAIR_LOW:CHECKED_TO': (0.0, 0.269, 0.731),
    'FLOP:BUTTON:EQ_VERY_HIGH_PAIR_LOW:FACING_BET': (0.0431, 0.3022, 0.6547),
    'FLOP:BUTTON:EQ_VERY_HIGH_PAIR_MID:CHECKED_TO': (0.0, 0.5096, 0.4904),
    'FLOP:BUTTON:EQ_VERY_HIGH_PAIR_MID:FACING_BET': (0.0327, 0.1319, 0.8354),
    'FLOP:BUTTON:EQ_VERY_HIGH_SUITED_ACE:CHECKED_TO': (0.0, 0.2049, 0.7951),
    'FLOP:BUTTON:EQ_VERY_HIGH_SUITED_ACE:FACING_BET': (0.0281, 0.1143, 0.8576),
    'FLOP:BUTTON:EQ_VERY_HIGH_SUITED_CONNECTOR:CHECKED_TO': (0.0, 0.5232, 0.4768),
    'FLOP:BUTTON:EQ_VERY_HIGH_SUITED_CONNECTOR:FACING_BET': (0.0427, 0.2182, 0.7391),
    'FLOP:BUTTON:EQ_VERY_HIGH_TRIPS:CHECKED_TO': (0.0, 0.3222, 0.6778),
    'FLOP:BUTTON:EQ_VERY_HIGH_TRIPS:FACING_BET': (0.3086, 0.3738, 0.3176),
    'FLOP:BUTTON:EQ_VERY_HIGH_WEAK_OFFSUIT:CHECKED_TO': (0.0, 0.4935, 0.5065),
    'FLOP:BUTTON:EQ_VERY_HIGH_WEAK_OFFSUIT:FACING_BET': (0.0425, 0.1675, 0.79),
    'FLOP:BUTTON:EQ_VERY_LOW_BROADWAY_OFFSUIT:CHECKED_TO': (0.0, 0.764, 0.236),
    'FLOP:BUTTON:EQ_VERY_LOW_BROADWAY_OFFSUIT:FACING_BET': (0.0059, 0.4014, 0.5927),
    'FLOP:BUTTON:EQ_VERY_LOW_BROADWAY_SUITED:CHECKED_TO': (0.0, 0.2395, 0.7605),
    'FLOP:BUTTON:EQ_VERY_LOW_BROADWAY_SUITED:FACING_BET': (0.7783, 0.072, 0.1497),
    'FLOP:BUTTON:EQ_VERY_LOW_HIGH_OFFSUIT:CHECKED_TO': (0.0, 0.5313, 0.4687),
    'FLOP:BUTTON:EQ_VERY_LOW_HIGH_OFFSUIT:FACING_BET': (0.2881, 0.5848, 0.1272),
    'FLOP:BUTTON:EQ_VERY_LOW_PAIR_HIGH:CHECKED_TO': (0.0, 0.9358, 0.0642),
    'FLOP:BUTTON:EQ_VERY_LOW_PAIR_HIGH:FACING_BET': (0.0024, 0.0152, 0.9824),
    'FLOP:BUTTON:EQ_VERY_LOW_PAIR_LOW:CHECKED_TO': (0.0, 0.2915, 0.7085),
    'FLOP:BUTTON:EQ_VERY_LOW_PAIR_LOW:FACING_BET': (0.3518, 0.4418, 0.2064),
    'FLOP:BUTTON:EQ_VERY_LOW_PAIR_MID:CHECKED_TO': (0.0, 0.6456, 0.3544),
    'FLOP:BUTTON:EQ_VERY_LOW_PAIR_MID:FACING_BET': (0.4419, 0.1014, 0.4567),
    'FLOP:BUTTON:EQ_VERY_LOW_SUITED_ACE:CHECKED_TO': (0.0, 0.3602, 0.6398),
    'FLOP:BUTTON:EQ_VERY_LOW_SUITED_ACE:FACING_BET': (0.3023, 0.3378, 0.3599),
    'FLOP:BUTTON:EQ_VERY_LOW_SUITED_CONNECTOR:CHECKED_TO': (0.0, 0.2861, 0.7139),
    'FLOP:BUTTON:EQ_VERY_LOW_SUITED_CONNECTOR:FACING_BET': (0.4612, 0.3071, 0.2317),
    'FLOP:BUTTON:EQ_VERY_LOW_TRIPS:CHECKED_TO': (0.0, 0.0, 1.0),
    'FLOP:BUTTON:EQ_VERY_LOW_TRIPS:FACING_BET': (0.0, 0.6153, 0.3847),
    'FLOP:BUTTON:EQ_VERY_LOW_WEAK_OFFSUIT:CHECKED_TO': (0.0, 0.3862, 0.6138),
    'FLOP:BUTTON:EQ_VERY_LOW_WEAK_OFFSUIT:FACING_BET': (0.2992, 0.5394, 0.1614),
    'PREFLOP:BIG_BLIND:BROADWAY_OFFSUIT:CHECKED_TO': (0.0, 0.1816, 0.8184),
    'PREFLOP:BIG_BLIND:BROADWAY_OFFSUIT:FACING_BET': (0.1523, 0.3492, 0.4985),
    'PREFLOP:BIG_BLIND:BROADWAY_SUITED:CHECKED_TO': (0.0, 0.2035, 0.7965),
    'PREFLOP:BIG_BLIND:BROADWAY_SUITED:FACING_BET': (0.0606, 0.1919, 0.7475),
    'PREFLOP:BIG_BLIND:HIGH_OFFSUIT:CHECKED_TO': (0.0, 0.1456, 0.8544),
    'PREFLOP:BIG_BLIND:HIGH_OFFSUIT:FACING_BET': (0.0435, 0.1393, 0.8173),
    'PREFLOP:BIG_BLIND:PAIR_HIGH:CHECKED_TO': (0.0, 0.1299, 0.8701),
    'PREFLOP:BIG_BLIND:PAIR_HIGH:FACING_BET': (0.0355, 0.1137, 0.8508),
    'PREFLOP:BIG_BLIND:PAIR_LOW:CHECKED_TO': (0.0, 0.2295, 0.7705),
    'PREFLOP:BIG_BLIND:PAIR_LOW:FACING_BET': (0.1038, 0.506, 0.3902),
    'PREFLOP:BIG_BLIND:PAIR_MID:CHECKED_TO': (0.0, 0.136, 0.864),
    'PREFLOP:BIG_BLIND:PAIR_MID:FACING_BET': (0.0603, 0.1235, 0.8162),
    'PREFLOP:BIG_BLIND:SUITED_ACE:CHECKED_TO': (0.0, 0.2549, 0.7451),
    'PREFLOP:BIG_BLIND:SUITED_ACE:FACING_BET': (0.0547, 0.1095, 0.8358),
    'PREFLOP:BIG_BLIND:SUITED_CONNECTOR:CHECKED_TO': (0.0, 0.5994, 0.4006),
    'PREFLOP:BIG_BLIND:SUITED_CONNECTOR:FACING_BET': (0.1369, 0.2534, 0.6097),
    'PREFLOP:BIG_BLIND:TRIPS:CHECKED_TO': (0.0, 0.4319, 0.5681),
    'PREFLOP:BIG_BLIND:TRIPS:FACING_BET': (0.181, 0.5271, 0.2919),
    'PREFLOP:BIG_BLIND:WEAK_OFFSUIT:CHECKED_TO': (0.0, 0.5479, 0.4521),
    'PREFLOP:BIG_BLIND:WEAK_OFFSUIT:FACING_BET': (0.0831, 0.34, 0.5769),
    'PREFLOP:BUTTON:BROADWAY_OFFSUIT:FACING_BET': (0.0721, 0.2654, 0.6625),
    'PREFLOP:BUTTON:BROADWAY_SUITED:FACING_BET': (0.0806, 0.2277, 0.6916),
    'PREFLOP:BUTTON:HIGH_OFFSUIT:FACING_BET': (0.0496, 0.2751, 0.6753),
    'PREFLOP:BUTTON:PAIR_HIGH:FACING_BET': (0.0608, 0.1867, 0.7524),
    'PREFLOP:BUTTON:PAIR_LOW:FACING_BET': (0.0695, 0.4552, 0.4754),
    'PREFLOP:BUTTON:PAIR_MID:FACING_BET': (0.0619, 0.2353, 0.7028),
    'PREFLOP:BUTTON:SUITED_ACE:FACING_BET': (0.0569, 0.2458, 0.6973),
    'PREFLOP:BUTTON:SUITED_CONNECTOR:FACING_BET': (0.0386, 0.4466, 0.5147),
    'PREFLOP:BUTTON:TRIPS:FACING_BET': (0.4567, 0.4551, 0.0882),
    'PREFLOP:BUTTON:WEAK_OFFSUIT:FACING_BET': (0.048, 0.6131, 0.339),
    'RIVER:BIG_BLIND:EQ_HIGH:CHECKED_TO': (0.0, 0.8643, 0.1357),
    'RIVER:BIG_BLIND:EQ_HIGH:FACING_BET': (0.0894, 0.7215, 0.1891),
    'RIVER:BIG_BLIND:EQ_LOW:CHECKED_TO': (0.0, 0.4602, 0.5398),
    'RIVER:BIG_BLIND:EQ_LOW:FACING_BET': (0.6695, 0.2365, 0.094),
    'RIVER:BIG_BLIND:EQ_MID:CHECKED_TO': (0.0, 0.9319, 0.0681),
    'RIVER:BIG_BLIND:EQ_MID:FACING_BET': (0.2289, 0.691, 0.0802),
    'RIVER:BIG_BLIND:EQ_VERY_HIGH:CHECKED_TO': (0.0, 0.3771, 0.6229),
    'RIVER:BIG_BLIND:EQ_VERY_HIGH:FACING_BET': (0.087, 0.2298, 0.6832),
    'RIVER:BIG_BLIND:EQ_VERY_LOW:CHECKED_TO': (0.0, 0.1756, 0.8244),
    'RIVER:BIG_BLIND:EQ_VERY_LOW:FACING_BET': (0.9113, 0.0395, 0.0492),
    'RIVER:BUTTON:EQ_HIGH:CHECKED_TO': (0.0, 0.6962, 0.3038),
    'RIVER:BUTTON:EQ_HIGH:FACING_BET': (0.0443, 0.481, 0.4746),
    'RIVER:BUTTON:EQ_LOW:CHECKED_TO': (0.0, 0.8464, 0.1536),
    'RIVER:BUTTON:EQ_LOW:FACING_BET': (0.418, 0.4895, 0.0925),
    'RIVER:BUTTON:EQ_MID:CHECKED_TO': (0.0, 0.8863, 0.1137),
    'RIVER:BUTTON:EQ_MID:FACING_BET': (0.0835, 0.8427, 0.0738),
    'RIVER:BUTTON:EQ_VERY_HIGH:CHECKED_TO': (0.0, 0.0653, 0.9347),
    'RIVER:BUTTON:EQ_VERY_HIGH:FACING_BET': (0.0582, 0.1287, 0.8131),
    'RIVER:BUTTON:EQ_VERY_LOW:CHECKED_TO': (0.0, 0.1694, 0.8306),
    'RIVER:BUTTON:EQ_VERY_LOW:FACING_BET': (0.8837, 0.0478, 0.0686),
    'TURN:BIG_BLIND:EQ_HIGH_NO_DRAW:CHECKED_TO': (0.0, 0.5605, 0.4395),
    'TURN:BIG_BLIND:EQ_HIGH_NO_DRAW:FACING_BET': (0.0659, 0.796, 0.1381),
    'TURN:BIG_BLIND:EQ_HIGH_STRONG_DRAW:CHECKED_TO': (0.0, 0.4218, 0.5782),
    'TURN:BIG_BLIND:EQ_HIGH_STRONG_DRAW:FACING_BET': (0.1092, 0.5782, 0.3126),
    'TURN:BIG_BLIND:EQ_HIGH_WEAK_DRAW:CHECKED_TO': (0.0, 0.5066, 0.4934),
    'TURN:BIG_BLIND:EQ_HIGH_WEAK_DRAW:FACING_BET': (0.15, 0.561, 0.289),
    'TURN:BIG_BLIND:EQ_LOW_NO_DRAW:CHECKED_TO': (0.0, 0.2358, 0.7642),
    'TURN:BIG_BLIND:EQ_LOW_NO_DRAW:FACING_BET': (0.6991, 0.2639, 0.0369),
    'TURN:BIG_BLIND:EQ_LOW_STRONG_DRAW:CHECKED_TO': (0.0, 0.6588, 0.3412),
    'TURN:BIG_BLIND:EQ_LOW_STRONG_DRAW:FACING_BET': (0.221, 0.7084, 0.0706),
    'TURN:BIG_BLIND:EQ_LOW_WEAK_DRAW:CHECKED_TO': (0.0, 0.3, 0.7),
    'TURN:BIG_BLIND:EQ_LOW_WEAK_DRAW:FACING_BET': (0.5071, 0.4317, 0.0613),
    'TURN:BIG_BLIND:EQ_MID_NO_DRAW:CHECKED_TO': (0.0, 0.7448, 0.2552),
    'TURN:BIG_BLIND:EQ_MID_NO_DRAW:FACING_BET': (0.23, 0.7312, 0.0387),
    'TURN:BIG_BLIND:EQ_MID_STRONG_DRAW:CHECKED_TO': (0.0, 0.3691, 0.6309),
    'TURN:BIG_BLIND:EQ_MID_STRONG_DRAW:FACING_BET': (0.128, 0.7605, 0.1115),
    'TURN:BIG_BLIND:EQ_MID_WEAK_DRAW:CHECKED_TO': (0.0, 0.6515, 0.3485),
    'TURN:BIG_BLIND:EQ_MID_WEAK_DRAW:FACING_BET': (0.2027, 0.6975, 0.0998),
    'TURN:BIG_BLIND:EQ_VERY_HIGH_NO_DRAW:CHECKED_TO': (0.0, 0.2762, 0.7238),
    'TURN:BIG_BLIND:EQ_VERY_HIGH_NO_DRAW:FACING_BET': (0.0933, 0.2471, 0.6596),
    'TURN:BIG_BLIND:EQ_VERY_HIGH_STRONG_DRAW:CHECKED_TO': (0.0, 0.2192, 0.7808),
    'TURN:BIG_BLIND:EQ_VERY_HIGH_STRONG_DRAW:FACING_BET': (0.096, 0.3314, 0.5725),
    'TURN:BIG_BLIND:EQ_VERY_HIGH_WEAK_DRAW:CHECKED_TO': (0.0, 0.3016, 0.6984),
    'TURN:BIG_BLIND:EQ_VERY_HIGH_WEAK_DRAW:FACING_BET': (0.1171, 0.3925, 0.4905),
    'TURN:BIG_BLIND:EQ_VERY_LOW_NO_DRAW:CHECKED_TO': (0.0, 0.0869, 0.9131),
    'TURN:BIG_BLIND:EQ_VERY_LOW_NO_DRAW:FACING_BET': (0.8899, 0.0775, 0.0326),
    'TURN:BIG_BLIND:EQ_VERY_LOW_STRONG_DRAW:CHECKED_TO': (0.0, 0.5359, 0.4641),
    'TURN:BIG_BLIND:EQ_VERY_LOW_STRONG_DRAW:FACING_BET': (0.3201, 0.5587, 0.1212),
    'TURN:BIG_BLIND:EQ_VERY_LOW_WEAK_DRAW:CHECKED_TO': (0.0, 0.2516, 0.7484),
    'TURN:BIG_BLIND:EQ_VERY_LOW_WEAK_DRAW:FACING_BET': (0.4278, 0.4889, 0.0833),
    'TURN:BUTTON:EQ_HIGH_NO_DRAW:CHECKED_TO': (0.0, 0.6283, 0.3717),
    'TURN:BUTTON:EQ_HIGH_NO_DRAW:FACING_BET': (0.048, 0.1232, 0.8287),
    'TURN:BUTTON:EQ_HIGH_STRONG_DRAW:CHECKED_TO': (0.0, 0.2803, 0.7197),
    'TURN:BUTTON:EQ_HIGH_STRONG_DRAW:FACING_BET': (0.0711, 0.1829, 0.746),
    'TURN:BUTTON:EQ_HIGH_WEAK_DRAW:CHECKED_TO': (0.0, 0.3964, 0.6036),
    'TURN:BUTTON:EQ_HIGH_WEAK_DRAW:FACING_BET': (0.0963, 0.1626, 0.7411),
    'TURN:BUTTON:EQ_LOW_NO_DRAW:CHECKED_TO': (0.0, 0.2086, 0.7914),
    'TURN:BUTTON:EQ_LOW_NO_DRAW:FACING_BET': (0.4684, 0.4383, 0.0933),
    'TURN:BUTTON:EQ_LOW_STRONG_DRAW:CHECKED_TO': (0.0, 0.6853, 0.3147),
    'TURN:BUTTON:EQ_LOW_STRONG_DRAW:FACING_BET': (0.1013, 0.3519, 0.5468),
    'TURN:BUTTON:EQ_LOW_WEAK_DRAW:CHECKED_TO': (0.0, 0.5312, 0.4688),
    'TURN:BUTTON:EQ_LOW_WEAK_DRAW:FACING_BET': (0.3618, 0.4468, 0.1914),
    'TURN:BUTTON:EQ_MID_NO_DRAW:CHECKED_TO': (0.0, 0.7709, 0.2291),
    'TURN:BUTTON:EQ_MID_NO_DRAW:FACING_BET': (0.0592, 0.7952, 0.1456),
    'TURN:BUTTON:EQ_MID_STRONG_DRAW:CHECKED_TO': (0.0, 0.7327, 0.2673),
    'TURN:BUTTON:EQ_MID_STRONG_DRAW:FACING_BET': (0.0769, 0.4444, 0.4787),
    'TURN:BUTTON:EQ_MID_WEAK_DRAW:CHECKED_TO': (0.0, 0.2001, 0.7999),
    'TURN:BUTTON:EQ_MID_WEAK_DRAW:FACING_BET': (0.1243, 0.6361, 0.2395),
    'TURN:BUTTON:EQ_VERY_HIGH_NO_DRAW:CHECKED_TO': (0.0, 0.129, 0.871),
    'TURN:BUTTON:EQ_VERY_HIGH_NO_DRAW:FACING_BET': (0.0261, 0.0802, 0.8937),
    'TURN:BUTTON:EQ_VERY_HIGH_STRONG_DRAW:CHECKED_TO': (0.0, 0.2183, 0.7817),
    'TURN:BUTTON:EQ_VERY_HIGH_STRONG_DRAW:FACING_BET': (0.0233, 0.1323, 0.8445),
    'TURN:BUTTON:EQ_VERY_HIGH_WEAK_DRAW:CHECKED_TO': (0.0, 0.2691, 0.7309),
    'TURN:BUTTON:EQ_VERY_HIGH_WEAK_DRAW:FACING_BET': (0.067, 0.1555, 0.7774),
    'TURN:BUTTON:EQ_VERY_LOW_NO_DRAW:CHECKED_TO': (0.0, 0.0931, 0.9069),
    'TURN:BUTTON:EQ_VERY_LOW_NO_DRAW:FACING_BET': (0.8821, 0.0444, 0.0735),
    'TURN:BUTTON:EQ_VERY_LOW_STRONG_DRAW:CHECKED_TO': (0.0, 0.3876, 0.6124),
    'TURN:BUTTON:EQ_VERY_LOW_STRONG_DRAW:FACING_BET': (0.1997, 0.5269, 0.2734),
    'TURN:BUTTON:EQ_VERY_LOW_WEAK_DRAW:CHECKED_TO': (0.0, 0.4212, 0.5788),
    'TURN:BUTTON:EQ_VERY_LOW_WEAK_DRAW:FACING_BET': (0.3909, 0.4038, 0.2053),
}


class PolicyManager:
    """Query interface for MCCFR policy; loads from mccfr_policy.json if present, with embedded fallback."""
    def __init__(self, policy_path="mccfr_policy.json"):
        self.strategy = {
            k: {"fold": t[0], "check_call": t[1], "bet_raise": t[2]}
            for k, t in EMBEDDED_POLICY.items()
        }
        self.metadata = EMBEDDED_POLICY_META
        try:
            p = Path(policy_path)
            if p.exists():
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if "strategy" in data:
                    self.strategy.update(data["strategy"])
                    self.metadata = {
                        "version": data.get("version"),
                        "game": data.get("game"),
                        "iterations": data.get("iterations"),
                    }
                    debug_log(f"Loaded {len(data['strategy'])} infosets from {policy_path}")
        except Exception as e:
            debug_log(f"Error loading {policy_path}: {e}")
        self.is_loaded = bool(self.strategy)

    def query(self, infoset_key: str):
        probs = self.strategy.get(infoset_key) if self.is_loaded else None
        if not probs:
            return None
        # A uniform row contains no useful strategic information.
        vals = tuple(probs.get(k, 0.0) for k in ACTIONS)
        if max(vals) - min(vals) < 0.025:
            return None
        total = sum(vals)
        if total <= 0:
            return None
        return {k: max(0.0, probs.get(k, 0.0)) / total for k in ACTIONS}


POLICY_MANAGER = PolicyManager(CONFIG.get("policy_file", "mccfr_policy.json"))


# ==============================================================================
# FAST HAND EVALUATOR
# ==============================================================================
class FastHandEvaluator:
    """Table-driven 5-card ranking and 7-card evaluator matching engine.py."""
    def __init__(self):
        t0 = time.perf_counter()
        self.table_nonflush = {}
        self.table_flush = {}
        self.combos_7_5 = list(combinations(range(7), 5))
        self._build_tables()
        self.build_time_ms = (time.perf_counter() - t0) * 1000.0

    def _compute_score(self, values, flush: bool) -> int:
        uniq = sorted(set(values), reverse=True)
        straight_high = 0
        if len(uniq) == 5:
            if uniq[0] - uniq[4] == 4:
                straight_high = uniq[0]
            elif uniq == [14, 5, 4, 3, 2]:
                straight_high = 5

        groups = sorted(Counter(values).items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
        shape = [n for _, n in groups]
        by_group = tuple(v for v, _ in groups)

        if straight_high and flush:
            cat = 8
            tie = (straight_high, 0, 0, 0, 0)
        elif shape == [4, 1]:
            cat = 7
            tie = by_group + (0, 0, 0)
        elif shape == [3, 2]:
            cat = 6
            tie = by_group + (0, 0, 0)
        elif flush:
            cat = 5
            tie = tuple(values)
        elif straight_high:
            cat = 4
            tie = (straight_high, 0, 0, 0, 0)
        elif shape == [3, 1, 1]:
            cat = 3
            tie = by_group + (0, 0)
        elif shape == [2, 2, 1]:
            cat = 2
            tie = by_group + (0, 0)
        elif shape == [2, 1, 1, 1]:
            cat = 1
            tie = by_group + (0,)
        else:
            cat = 0
            tie = tuple(values)

        score = cat
        for v in tie:
            score = score * 15 + v
        return score

    def _build_tables(self):
        ranks = list(range(2, 15))
        for combo in combinations_with_replacement(ranks, 5):
            key = tuple(sorted(combo, reverse=True))
            self.table_nonflush[key] = self._compute_score(key, False)
        for combo in combinations(ranks, 5):
            key = tuple(sorted(combo, reverse=True))
            self.table_flush[key] = self._compute_score(key, True)

    def evaluate_7(self, cards_7) -> int:
        s = sorted(cards_7, key=lambda c: c[0], reverse=True)
        s0 = s1 = s2 = s3 = 0
        for _, su in s:
            if su == 0: s0 += 1
            elif su == 1: s1 += 1
            elif su == 2: s2 += 1
            else: s3 += 1

        flush_suit = -1
        if s0 >= 5: flush_suit = 0
        elif s1 >= 5: flush_suit = 1
        elif s2 >= 5: flush_suit = 2
        elif s3 >= 5: flush_suit = 3

        best = -1
        combos = self.combos_7_5
        tbl_nf = self.table_nonflush
        tbl_f = self.table_flush

        if flush_suit == -1:
            for i0, i1, i2, i3, i4 in combos:
                sc = tbl_nf[(s[i0][0], s[i1][0], s[i2][0], s[i3][0], s[i4][0])]
                if sc > best:
                    best = sc
        else:
            for i0, i1, i2, i3, i4 in combos:
                c0, c1, c2, c3, c4 = s[i0], s[i1], s[i2], s[i3], s[i4]
                rk = (c0[0], c1[0], c2[0], c3[0], c4[0])
                if c0[1] == c1[1] == c2[1] == c3[1] == c4[1] == flush_suit:
                    sc = tbl_f[rk]
                else:
                    sc = tbl_nf[rk]
                if sc > best:
                    best = sc
        return best

    def evaluate_5(self, cards_5) -> int:
        """Exact five-card score; matches the opponent bot's evaluate(cards) proxy."""
        if len(cards_5) != 5:
            raise ValueError("evaluate_5 requires exactly five cards")
        ranks = tuple(sorted((c[0] for c in cards_5), reverse=True))
        flush = all(c[1] == cards_5[0][1] for c in cards_5)
        return (self.table_flush if flush else self.table_nonflush)[ranks]

    def evaluate_best(self, cards) -> int:
        """Best five-card score from any 5-7 cards (also supports partial 5/6-card states)."""
        if len(cards) < 5 or len(cards) > 7:
            raise ValueError("evaluate_best requires 5 to 7 cards")
        if len(cards) == 5:
            return self.evaluate_5(cards)
        return max(self.evaluate_5(combo) for combo in combinations(cards, 5))


EVALUATOR = FastHandEvaluator()


# ==============================================================================
# OPPONENT MODEL (BAYESIAN STATISTICAL ESTIMATION)
# ==============================================================================
class OpponentModel:
    """Bayesian opponent model with preflop ranges and bet-size/showdown strength tables."""
    CLASS_BASE = (0.55, 0.20, 0.15, 0.07, 0.03)
    SMALL_PRIOR = [1.23, 1.58, 1.87, 0.92, 0.39]
    BIG_PRIOR = [1.10, 1.34, 1.88, 1.17, 0.50]
    RAISE_PRIOR = [0.74, 0.54, 1.41, 1.50, 0.81]

    def __init__(self):
        self.stats = {
            "post_actions": 0.0, "post_raises": 0.0, "post_calls": 0.0, "post_checks": 0.0,
            "my_post_bets": 0.0, "opp_folds_to_my_post_bet": 0.0,
            "my_pre_raises": 0.0, "opp_folds_to_my_pre_raise": 0.0,
            "opp_pre_allins": 0.0, "showdowns_seen": 0.0,
            "opp_pf_open_opps": 0.0, "opp_pf_opens": 0.0,
            "opp_pf_3bet_opps": 0.0, "opp_pf_3bets": 0.0,
            "opp_pf_calls": 0.0,
        }
        self.sd_small = list(self.SMALL_PRIOR)
        self.sd_big = list(self.BIG_PRIOR)
        self.sd_raise = list(self.RAISE_PRIOR)
        self.sd_weight = 1.6
        self.decay = 0.995

    def decay_stats(self):
        for k in self.stats:
            self.stats[k] *= self.decay
        for arr, prior in ((self.sd_small, self.SMALL_PRIOR),
                           (self.sd_big, self.BIG_PRIOR),
                           (self.sd_raise, self.RAISE_PRIOR)):
            for i in range(5):
                arr[i] = prior[i] + (arr[i] - prior[i]) * 0.997

    def aggression_frequency(self) -> float:
        s = self.stats
        return (s["post_raises"] + 3.0) / (s["post_actions"] + 8.0)

    def fold_to_bet_rate(self) -> float:
        s = self.stats
        return (s["opp_folds_to_my_post_bet"] + 2.0) / (s["my_post_bets"] + 5.0)

    def preflop_fold_rate(self) -> float:
        s = self.stats
        return (s["opp_folds_to_my_pre_raise"] + 2.0) / (s["my_pre_raises"] + 5.0)

    def preflop_open_rate(self) -> float:
        s = self.stats
        return (s["opp_pf_opens"] + 3.0) / (s["opp_pf_open_opps"] + 5.0)

    def preflop_3bet_rate(self) -> float:
        s = self.stats
        return (s["opp_pf_3bets"] + 1.0) / (s["opp_pf_3bet_opps"] + 6.0)

    @staticmethod
    def strength_class(score: int, board_score: int, board_top: int) -> int:
        """0=board/no pair, 1=weak pair, 2=top pair/two-pair, 3=trips/two-pair+, 4=straight+."""
        unit = 15 ** 5
        cat = score // unit
        bcat = board_score // unit
        imp = cat - bcat
        if imp <= 0:
            if cat >= 4 and score > board_score:
                return 3
            return 0
        if cat >= 4:
            return 4
        if imp >= 2 or cat >= 3:
            return 3
        if cat == 1:
            pair_rank = (score // (15 ** 4)) % 15
            return 2 if pair_rank >= board_top else 1
        if cat == 2:
            return 2
        return 1

    def accept_table(self, kind="all"):
        if kind == "small":
            counts = self.sd_small
        elif kind == "big":
            counts = self.sd_big
        elif kind == "raise":
            counts = self.sd_raise
        else:
            counts = [a + b - p for a, b, p in zip(self.sd_small, self.sd_big, self.BIG_PRIOR)]
        total = sum(counts)
        if total <= 0:
            return [1.0] * 5
        likelihood = [counts[i] / total / self.CLASS_BASE[i] for i in range(5)]
        top = max(likelihood) or 1.0
        table = [max(0.03, x / top) for x in likelihood]
        aggr = self.aggression_frequency()
        table[0] = min(0.8, max(table[0], 1.1 * (aggr - 0.3) * (0.5 if kind == "raise" else 1.0)))
        return table

    @staticmethod
    def last_opp_bet_ratio(history):
        """Estimate last turn/river opponent bet as a fraction of pot-before-bet."""
        levels = {"preflop": 0, "flop": 0, "turn": 0, "river": 0}
        levels["preflop"] = 2
        for h in history:
            if h.get("action") in ("call", "raise") and h.get("street") in levels:
                levels[h["street"]] = max(levels[h["street"]], int(h.get("amount", 0) or 0))
        ratio = 0.0
        for i, street in enumerate(("turn", "river"), start=2):
            pot_start = 2 * sum(levels[x] for x in ("preflop", "flop", "turn", "river")[:i])
            bets = {"me": 0, "opp": 0}
            for h in history:
                if h.get("street") != street:
                    continue
                action = h.get("action")
                if action == "raise" and h.get("actor") == "opp":
                    pot_before = pot_start + bets["me"] + bets["opp"]
                    ratio = (int(h.get("amount", 0) or 0) - bets["me"]) / max(1, pot_before)
                if action in ("call", "raise"):
                    bets[h.get("actor", "me")] = int(h.get("amount", 0) or 0)
        return max(0.0, ratio)

    def update_from_history(self, history: list, opp_hole=None, board=None,
                            opponent_is_button=False, showdown=False):
        if not history:
            return
        self.decay_stats()
        st = self.stats
        # Preflop opportunities distinguish an open from a re-raise against our raise.
        opp_pf = [e for e in history if e.get("street") == "preflop" and e.get("actor") == "opp"]
        me_pf_raises = [e for e in history if e.get("street") == "preflop" and e.get("actor") == "me" and e.get("action") == "raise"]
        if opp_pf and opponent_is_button:
            st["opp_pf_open_opps"] += 1.0
            if opp_pf[0].get("action") == "raise":
                st["opp_pf_opens"] += 1.0
        if me_pf_raises and opp_pf:
            st["opp_pf_3bet_opps"] += 1.0
            if any(e.get("action") == "raise" for e in opp_pf):
                st["opp_pf_3bets"] += 1.0
            if any(e.get("action") == "call" for e in opp_pf):
                st["opp_pf_calls"] += 1.0
        if any(e.get("actor") == "opp" and e.get("street") == "preflop"
               and e.get("action") == "raise" and int(e.get("amount", 0) or 0) >= 150 for e in history):
            st["opp_pre_allins"] += 1.0

        # General action/fold statistics.
        for i, e in enumerate(history):
            actor, street, action = e.get("actor"), e.get("street"), e.get("action")
            if actor == "opp" and street != "preflop":
                st["post_actions"] += 1.0
                if action == "raise": st["post_raises"] += 1.0
                elif action == "call": st["post_calls"] += 1.0
                elif action == "check": st["post_checks"] += 1.0
            if actor == "me" and action == "raise":
                response = None
                for e2 in history[i + 1:]:
                    if e2.get("street") != street:
                        break
                    if e2.get("actor") == "opp":
                        response = e2
                        break
                if response is not None:
                    if street == "preflop":
                        st["my_pre_raises"] += 1.0
                        if response.get("action") == "fold": st["opp_folds_to_my_pre_raise"] += 1.0
                    else:
                        st["my_post_bets"] += 1.0
                        if response.get("action") == "fold": st["opp_folds_to_my_post_bet"] += 1.0

        # Learn which hand strengths Ansh shows after small bets, big bets and raises.
        if showdown and opp_hole and board and len(board) == 5:
            try:
                opp_cards = [CARD_TO_INT[c] for c in opp_hole]
                board_cards = [CARD_TO_INT[c] for c in board]
                if len(opp_cards) >= 2:
                    score = EVALUATOR.evaluate_best(opp_cards[:2] + board_cards)
                    board_score = EVALUATOR.evaluate_5(board_cards)
                    cls = self.strength_class(score, board_score, max(c[0] for c in board_cards))
                    opp_turn_river_raises = [e for e in history if e.get("actor") == "opp"
                                              and e.get("action") == "raise" and e.get("street") in ("turn", "river")]
                    if opp_turn_river_raises:
                        opp_reraised = False
                        for idx, event in enumerate(history):
                            if event.get("actor") == "opp" and event.get("action") == "raise" and event.get("street") in ("turn", "river"):
                                if any(prev.get("actor") == "me" and prev.get("action") == "raise"
                                       and prev.get("street") == event.get("street")
                                       for prev in history[:idx]):
                                    opp_reraised = True
                                    break
                        kind = "raise" if opp_reraised else (
                            "big" if self.last_opp_bet_ratio(history) >= 0.60 else "small")
                        target = self.sd_raise if kind == "raise" else (self.sd_big if kind == "big" else self.sd_small)
                        target[cls] += self.sd_weight
                        st["showdowns_seen"] += 1.0
            except (KeyError, ValueError, TypeError):
                pass


# ==============================================================================
# DISCARD MODEL (BAYESIAN MIXTURE POSTERIOR)
# ==============================================================================
class DiscardModel:
    """Bayesian mixture model; initialized for the known opponent's optimal proxy discard."""
    def __init__(self):
        p_opt = CONFIG["opponent_optimal_discard_prior"]
        # Keep a small amount of uncertainty so a revealed different style can be learned.
        self.alpha = [max(0.05, (1.0 - p_opt) * 10.0), p_opt * 20.0,
                      max(0.05, (1.0 - p_opt) * 10.0)]

    @property
    def posterior(self):
        total = sum(self.alpha)
        return tuple(x / total for x in self.alpha)

    @staticmethod
    def get_lowest_discard(cards_3):
        return min(cards_3, key=lambda c: (c[0], c[1]))

    @staticmethod
    def get_optimal_discard(cards_3, flop_3):
        """Exact tie-breaking equivalent of Ansh's proxy_keep(): discard index 0 first on ties."""
        best_score = -1
        best_drop = cards_3[0]
        for drop_idx in range(3):
            kept = [cards_3[j] for j in range(3) if j != drop_idx]
            score = EVALUATOR.evaluate_5(kept + flop_3)
            if score > best_score:
                best_score = score
                best_drop = cards_3[drop_idx]
        return best_drop

    def update_from_showdown(self, kept_2, discarded_1, flop_3):
        all_3 = kept_2 + [discarded_1]
        d_low = self.get_lowest_discard(all_3)
        d_opt = self.get_optimal_discard(all_3, flop_3)
        eps = 0.02
        likelihoods = (
            1.0 - eps if discarded_1 == d_low else eps / 2.0,
            1.0 - eps if discarded_1 == d_opt else eps / 2.0,
            1.0 / 3.0,
        )
        posterior = [p * l for p, l in zip(self.posterior, likelihoods)]
        z = sum(posterior)
        if z > 0:
            # Bounded posterior concentration prevents one showdown from making the model absolute.
            self.alpha = [max(0.25, x / z * 40.0) for x in posterior]

    def weight_hand_given_discard(self, kept_2, discarded_1, flop_3):
        all_3 = kept_2 + [discarded_1]
        p_low, p_opt, p_rand = self.posterior
        d_low = self.get_lowest_discard(all_3)
        d_opt = self.get_optimal_discard(all_3, flop_3)
        l_low = 1.0 if discarded_1 == d_low else 0.01
        l_opt = 1.0 if discarded_1 == d_opt else 0.01
        return p_low * l_low + p_opt * l_opt + p_rand / 3.0


# ==============================================================================
# RANGE SHAPING & EQUITY ENGINE
# ==============================================================================
def range_weights(opp_scores, gamma):
    """
    Shapes sampled opponent range by hand strength percentile:
      gamma > 0 : opponent showed strength (bet/raise)
      gamma < 0 : opponent showed weakness (check)
    """
    n = len(opp_scores)
    if n == 0 or abs(gamma) < 1e-9:
        return [1.0] * n
    order = sorted(range(n), key=opp_scores.__getitem__)
    pct = [0.0] * n
    denom = float(max(1, n - 1))
    i = 0
    while i < n:
        j = i
        si = opp_scores[order[i]]
        while j + 1 < n and opp_scores[order[j + 1]] == si:
            j += 1
        mid = (i + j) / 2.0 / denom
        for k in range(i, j + 1):
            pct[order[k]] = mid
        i = j + 1
    if gamma > 0:
        return [(0.05 + p) ** gamma for p in pct]
    g = -gamma
    return [(1.05 - p) ** g for p in pct]


def opponent_preflop_range(history, opponent_model):
    """Ansh-style percentile weighting from observed open/3-bet/call/limp actions."""
    hist = history or []
    opp_actions = [h.get("action") for h in hist if h.get("street") == "preflop" and h.get("actor") == "opp"]
    my_raises = sum(1 for h in hist if h.get("street") == "preflop" and h.get("actor") == "me" and h.get("action") == "raise")
    if not opp_actions:
        return None  # Opponent has not acted yet; do not invent a range.
    opp_raises = sum(1 for a in opp_actions if a == "raise")
    if opp_raises == 0:
        if my_raises == 0:
            return (0.0, 1.0, 0.80, 0.50)  # limp/check-back range: top hands more likely raised
        return (0.20, 0.45, 0.92, 0.60)     # called our raise: remove some weakest and strongest
    if opp_raises == 1:
        rate = opponent_model.preflop_3bet_rate() if my_raises else opponent_model.preflop_open_rate()
        threshold = max(0.10, min(0.90, 1.0 - rate))
        return (threshold, 0.20, 2.0, 1.0)
    rate = opponent_model.preflop_3bet_rate()
    threshold = max(0.60, min(0.95, 1.0 - 0.5 * rate))
    return (threshold, 0.08, 2.0, 1.0)


def preflop_range_weight(pfw, opp_3):
    if pfw is None:
        return 1.0
    threshold, low_weight, cap_threshold, cap_weight = pfw
    pct = PREFLOP_TABLE.get_percentile(opp_3)
    if pct < threshold:
        return low_weight
    if pct > cap_threshold:
        return cap_weight
    return 1.0


TIER2 = (0.60, 0.50, 0.75, 0.90, 1.00)
TIER3 = (0.30, 0.17, 0.42, 0.65, 1.00)


def opponent_strength_class(score, board):
    """Classify the opponent's made hand using only their cards and the visible board."""
    unit = 15 ** 5
    cat = score // unit
    board_top = max((c[0] for c in board), default=14)
    if len(board) == 5:
        board_score = EVALUATOR.evaluate_5(board)
        return OpponentModel.strength_class(score, board_score, board_top)
    if cat >= 4:
        return 4
    if cat >= 3:
        return 3
    if cat == 2:
        return 2
    if cat == 1:
        pair_rank = (score // (15 ** 4)) % 15
        return 2 if pair_rank >= board_top else 1
    return 0


def accept_prob(cls, aggression, table):
    """Likelihood multiplier for a hand class given observed betting aggression."""
    if table is None or aggression <= 0:
        return 1.0
    if aggression < 1.5:
        return table[cls]
    if aggression < 2.5:
        return table[cls] * TIER2[cls]
    return table[cls] * TIER3[cls]


def opponent_aggression_level(history, street, req):
    """Ansh-style action-count and sizing signal for the current opponent range."""
    hist = history or []
    current_raises = [e for e in hist if e.get("street") == street and e.get("actor") == "opp" and e.get("action") == "raise"]
    previous_raises = {e.get("street") for e in hist if e.get("actor") == "opp" and e.get("action") == "raise"
                        and e.get("street") not in ("preflop", street)}
    level = len(current_raises) + 0.5 * len(previous_raises)
    if current_raises and int(req.get("to_call", 0)) >= 0.75 * max(1, int(req.get("pot", 0)) - int(req.get("to_call", 0))):
        level += 0.5
    reraised = False
    for i, event in enumerate(hist):
        if event.get("street") == street and event.get("actor") == "opp" and event.get("action") == "raise":
            if any(prev.get("street") == street and prev.get("actor") == "me" and prev.get("action") == "raise"
                   for prev in hist[:i]):
                reraised = True
                break
    return level, reraised


def proxy_optimal_discard(cards_3, flop_3):
    """Returns the index discarded using the exact target-opponent five-card evaluator."""
    scores = []
    for drop in range(3):
        kept = [cards_3[j] for j in range(3) if j != drop]
        scores.append(EVALUATOR.evaluate_5(kept + flop_3))
    return max(range(3), key=lambda i: (scores[i], -i))


def preflop_equity_mc(hole_3, pfw=None, deadline=None, samples=None):
    """Estimate 3-card equity against an action-conditioned opponent range."""
    samples = samples or CONFIG["preflop_mc_samples"]
    deck = [c for c in ALL_CARDS_INT if c not in set(hole_3)]
    weighted_wins = 0.0
    weight_total = 0.0
    tries = 0
    while tries < samples:
        if deadline is not None and tries >= CONFIG["min_adaptive_samples"] and (tries & 15) == 0 and time.perf_counter() >= deadline:
            break
        tries += 1
        draw = random.sample(deck, 8)
        opp_3, flop, runout = draw[:3], draw[3:6], draw[6:8]
        weight = preflop_range_weight(pfw, opp_3)
        if weight <= 0:
            continue
        my_drop = proxy_optimal_discard(hole_3, flop)
        opp_drop = proxy_optimal_discard(opp_3, flop)
        my_kept = [hole_3[i] for i in range(3) if i != my_drop]
        opp_kept = [opp_3[i] for i in range(3) if i != opp_drop]
        full_board = flop + runout
        my_score = EVALUATOR.evaluate_7(my_kept + full_board)
        opp_score = EVALUATOR.evaluate_7(opp_kept + full_board)
        result = 1.0 if my_score > opp_score else (0.5 if my_score == opp_score else 0.0)
        weighted_wins += weight * result
        weight_total += weight
    return weighted_wins / weight_total if weight_total else 0.5


class EquityEngine:
    """Range-aware equity: future cards determine showdown, current cards determine betting range."""
    def __init__(self, evaluator):
        self.evaluator = evaluator

    def equity(self, my_hole, board, opp_discard=None, my_discard=None,
               discard_model=None, gamma=0.0, samples=350, pfw=None,
               deadline=None, min_samples=80, action_tab=None, aggression=0.0) -> float:
        ev = self.evaluator.evaluate_7
        dead = set(my_hole) | set(board)
        if my_discard is not None: dead.add(my_discard)
        if opp_discard is not None: dead.add(opp_discard)
        unseen = [c for c in ALL_CARDS_INT if c not in dead]
        flop3 = list(board[:3])
        use_disc = (opp_discard is not None) and (discard_model is not None) and len(flop3) == 3
        need = 5 - len(board)
        weighted_wins = 0.0
        weight_total = 0.0
        current_scores = []
        outcome_rows = []

        if need == 0:
            # River: enumerate every remaining opponent combination exactly.
            my_score = self.evaluator.evaluate_best(list(my_hole) + list(board))
            for c0, c1 in combinations(unseen, 2):
                opp = [c0, c1]
                current_score = self.evaluator.evaluate_best(opp + list(board))
                final_score = current_score
                result = 1.0 if my_score > final_score else (0.5 if my_score == final_score else 0.0)
                d_weight = discard_model.weight_hand_given_discard(opp, opp_discard, flop3) if use_disc else 1.0
                p_weight = preflop_range_weight(pfw, opp + [opp_discard]) if opp_discard is not None else 1.0
                strength = opponent_strength_class(current_score, list(board))
                action_weight = accept_prob(strength, aggression, action_tab)
                outcome_rows.append((result, current_score, d_weight * p_weight * action_weight))
        else:
            tries = 0
            while tries < samples:
                if deadline is not None and tries >= min_samples and (tries & 15) == 0 and time.perf_counter() >= deadline:
                    break
                tries += 1
                draw = random.sample(unseen, 2 + need)
                opp = draw[:2]
                full_board = list(board) + draw[2:]
                # Critical: use only cards available when the opponent acted for range shaping.
                current_score = self.evaluator.evaluate_best(opp + list(board))
                my_score = ev(list(my_hole) + full_board)
                opp_score = ev(opp + full_board)
                result = 1.0 if my_score > opp_score else (0.5 if my_score == opp_score else 0.0)
                d_weight = discard_model.weight_hand_given_discard(opp, opp_discard, flop3) if use_disc else 1.0
                p_weight = preflop_range_weight(pfw, opp + [opp_discard]) if opp_discard is not None else 1.0
                strength = opponent_strength_class(current_score, list(board))
                action_weight = accept_prob(strength, aggression, action_tab)
                outcome_rows.append((result, current_score, d_weight * p_weight * action_weight))

        if not outcome_rows:
            return 0.5
        range_mult = range_weights([row[1] for row in outcome_rows], gamma)
        for (result, _score, base_weight), range_weight in zip(outcome_rows, range_mult):
            weight = base_weight * range_weight
            weighted_wins += result * weight
            weight_total += weight
        return weighted_wins / weight_total if weight_total > 0 else 0.5




EQUITY_ENGINE = EquityEngine(EVALUATOR)


# ==============================================================================
# DISCARD OPTIMIZATION (CRN ACROSS ALL 3 CANDIDATES)
# ==============================================================================
def fast_heuristic_discard(hole_3, flop_3) -> str:
    """Exact current-flop proxy fallback, matching Ansh's deterministic tie-breaking."""
    drop_idx = proxy_optimal_discard(hole_3, flop_3)
    return INT_TO_CARD[hole_3[drop_idx]]




def crn_candidate_equities(hole_3_str, flop_3_str, discard_model, gamma=0.0,
                           samples=300, pfw=None, deadline=None,
                           action_tab=None, aggression=0.0):
    """CRN discard evaluation; range weights use flop-time opponent strength, not future cards."""
    hole_3 = [CARD_TO_INT[c] for c in hole_3_str]
    flop_3 = [CARD_TO_INT[c] for c in flop_3_str]
    dead = set(hole_3 + flop_3)
    unseen = [c for c in ALL_CARDS_INT if c not in dead]
    ev5 = EVALUATOR.evaluate_5
    ev7 = EVALUATOR.evaluate_7
    p_low, p_opt, p_rand = discard_model.posterior
    scenarios = []
    tries = 0
    min_samples = min(CONFIG["min_adaptive_samples"], samples)
    while tries < samples:
        if deadline is not None and tries >= min_samples and (tries & 15) == 0 and time.perf_counter() >= deadline:
            break
        tries += 1
        sampled = random.sample(unseen, 5)
        opp_3 = sampled[:3]
        full_board = flop_3 + sampled[3:]
        roll = random.random()
        if roll < p_low:
            opp_discard = DiscardModel.get_lowest_discard(opp_3)
        elif roll < p_low + p_opt:
            opp_discard = DiscardModel.get_optimal_discard(opp_3, flop_3)
        else:
            opp_discard = random.choice(opp_3)
        opp_kept = [c for c in opp_3 if c != opp_discard]
        # This is the opponent's hand strength at the time of a flop betting decision.
        current_score = ev5(opp_kept + flop_3)
        final_score = ev7(opp_kept + full_board)
        pf_weight = preflop_range_weight(pfw, opp_3)
        strength = opponent_strength_class(current_score, flop_3)
        action_weight = accept_prob(strength, aggression, action_tab)
        scenarios.append((full_board, current_score, final_score, pf_weight * action_weight))

    if not scenarios:
        return [(0.5, c) for c in hole_3_str]
    range_mult = range_weights([sc[1] for sc in scenarios], gamma)
    scenario_weights = [sc[3] * rw for sc, rw in zip(scenarios, range_mult)]
    total_weight = sum(scenario_weights) or 1.0
    candidates = []
    for drop_idx in range(3):
        kept = [hole_3[j] for j in range(3) if j != drop_idx]
        wins = 0.0
        for (full_board, _current_score, opp_final, _pf), weight in zip(scenarios, scenario_weights):
            my_final = ev7(kept + full_board)
            if my_final > opp_final:
                wins += weight
            elif my_final == opp_final:
                wins += 0.5 * weight
        candidates.append((wins / total_weight, hole_3_str[drop_idx]))
    return candidates


def decision_deadline(time_left_ms=None, max_ms=None):
    """Hard per-decision budget, bounded by remaining match bank."""
    remaining = max(1, STATE.total_hands - STATE.hands_played)
    bank = float(STATE.time_left_ms if time_left_ms is None else time_left_ms)
    allowance = bank / remaining
    budget = min(float(max_ms or CONFIG["max_decision_time_ms"]), max(5.0, allowance * 0.5))
    if bank < CONFIG["time_bank_cushion_ms"]:
        budget = min(budget, 12.0)
    return time.perf_counter() + budget / 1000.0


def choose_best_discard_crn(hole_3_str: list, flop_3_str: list, time_left_ms: float,
                            discard_model: DiscardModel, gamma: float = 0.0,
                            pfw=None, deadline=None, action_tab=None, aggression=0.0) -> str:
    """Choose discard maximizing range-aware expected showdown equity."""
    hole = [CARD_TO_INT[c] for c in hole_3_str]
    flop = [CARD_TO_INT[c] for c in flop_3_str]
    if time_left_ms < CONFIG["time_bank_cushion_ms"]:
        return fast_heuristic_discard(hole, flop)
    if deadline is None:
        deadline = decision_deadline(time_left_ms, 60.0)
    scale = max(1.0, min(2.0, STATE.sample_scale()))
    samples = int(CONFIG["discard_mc_samples"] * scale)
    candidates = crn_candidate_equities(hole_3_str, flop_3_str, discard_model, gamma,
                                        samples, pfw=pfw, deadline=deadline,
                                        action_tab=action_tab, aggression=aggression)
    best = max(c[0] for c in candidates)
    pool = [c[1] for c in candidates if c[0] >= best - CONFIG["discard_tie_margin"]]
    return random.choice(pool)




# ==============================================================================
# STATE TRACKER
# ==============================================================================
class MatchState:
    """Tracks match, session, and hand parameters across engine protocol messages."""
    def __init__(self):
        self.protocol_version = "1.0"
        self.total_hands = 400
        self.starting_stack = 200
        self.small_blind = 1
        self.big_blind = 2
        self.time_bank_ms = 60000.0
        self.time_left_ms = 60000.0
        self.per_response_ms = 5000.0

        self.hands_played = 0
        self.running_net = 0
        self.net_history = []

        self.hand_id = 0
        self.seat = None
        self.hole_cards = []
        self.my_discard = None
        self.opp_discard = None
        self.my_discard_int = None
        self.opp_discard_int = None
        self.board = []
        self.last_req = None

        self.discard_model = DiscardModel()
        self.opp_model = OpponentModel()

    def sample_scale(self) -> float:
        remaining = max(1, self.total_hands - self.hands_played)
        allowance_ms = self.time_left_ms / remaining
        return max(1.0, min(3.0, 0.25 * allowance_ms / 11.0))

    def max_future_loss(self) -> int:
        remaining = self.total_hands - self.hands_played
        if remaining <= 0: return 0
        is_button = (self.seat == "button") if self.seat else True
        loss = 0
        for _ in range(remaining):
            loss += 1 if is_button else 2
            is_button = not is_button
        return loss

    def is_locked(self) -> bool:
        if not CONFIG["lock_mode_enabled"]: return False
        cap = max(1, self.total_hands)
        return (self.running_net - self.max_future_loss()) >= cap

    def win_probability(self) -> float:
        remaining = self.total_hands - self.hands_played
        if remaining <= 0:
            return 1.0 if self.running_net > 0 else (0.5 if self.running_net == 0 else 0.0)
        sigma = CONFIG["default_sigma"]
        if len(self.net_history) >= 20:
            mean = sum(self.net_history) / len(self.net_history)
            var = sum((x - mean) ** 2 for x in self.net_history) / (len(self.net_history) - 1)
            sigma = max(10.0, min(50.0, math.sqrt(var)))
        z = self.running_net / (sigma * math.sqrt(remaining))
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2)))

    def on_init(self, msg: dict):
        self.protocol_version = msg.get("protocol_version", "1.0")
        self.total_hands = msg.get("total_hands", self.total_hands)
        self.starting_stack = msg.get("starting_stack", 200)
        self.small_blind = msg.get("small_blind", 1)
        self.big_blind = msg.get("big_blind", 2)
        self.time_bank_ms = float(msg.get("time_bank_ms", self.time_bank_ms))
        self.time_left_ms = self.time_bank_ms
        self.per_response_ms = float(msg.get("per_response_ms", 5000.0))

    def on_new_hand(self, msg: dict):
        self.hand_id = msg.get("hand_id", self.hands_played + 1)
        self.seat = msg.get("seat")
        self.hole_cards = list(msg.get("hole_cards", []))
        self.my_discard = None
        self.opp_discard = None
        self.my_discard_int = None
        self.opp_discard_int = None
        self.board = []
        self.last_req = None

    def on_discard_result(self, msg: dict):
        self.my_discard = msg.get("my_discard")
        self.opp_discard = msg.get("opp_discard")
        self.my_discard_int = CARD_TO_INT.get(self.my_discard)
        self.opp_discard_int = CARD_TO_INT.get(self.opp_discard)
        if "hole_cards" in msg:
            self.hole_cards = list(msg["hole_cards"])
        elif self.my_discard and self.my_discard in self.hole_cards:
            self.hole_cards.remove(self.my_discard)

    def on_hand_result(self, msg: dict):
        self.hands_played += 1
        net = msg.get("net", 0)
        self.running_net += net
        self.net_history.append(net)

        hist = msg.get("history", []) or []
        opp_hole = msg.get("opp_hole_cards")
        opp_discard = msg.get("opp_discard")
        board = msg.get("board", [])
        self.opp_model.update_from_history(
            hist, opp_hole=opp_hole, board=board,
            opponent_is_button=(self.seat == "big_blind"),
            showdown=(msg.get("result") == "showdown"))
        if msg.get("result") == "showdown" and opp_hole and opp_discard and len(board) >= 3:
            opp_kept = [CARD_TO_INT[c] for c in opp_hole]
            opp_disc = CARD_TO_INT[opp_discard]
            flop_3 = [CARD_TO_INT[c] for c in board[:3]]
            self.discard_model.update_from_showdown(opp_kept, opp_disc, flop_3)


STATE = MatchState()


# ==============================================================================
# PROTOCOL SAFETY & SANITIZATION
# ==============================================================================
def default_safe_discard(hole_cards: list) -> str:
    """Engine-identical default discard (lowest rank; tie: s, h, d, c)."""
    if not hole_cards: return "2c"
    return min(hole_cards, key=lambda c: (RANK_VALUE.get(c[0], 0), SUIT_ORDER.get(c[1], 3)))


def safe_fallback_action(legal_actions: list) -> dict:
    if "check" in legal_actions:
        return {"type": "action", "action": "check"}
    return {"type": "action", "action": "fold"}


def sanitize_action_reply(reply: dict, req: dict) -> dict:
    """Clamps outgoing action reply strictly within legal bounds, guaranteeing 0 notices."""
    legal = req.get("legal_actions", ["check"])
    act = reply.get("action")
    if act not in legal:
        act = "check" if "check" in legal else "fold"
        reply = {"type": "action", "action": act}
    if act == "raise":
        min_r = req.get("min_raise", req.get("opp_bet", 0) + 2)
        max_r = req.get("max_raise", req.get("my_stack", 200))
        amt = reply.get("amount")
        if not isinstance(amt, int) or amt is None:
            amt = min_r
        amt = max(min_r, min(max_r, int(amt)))
        reply["amount"] = amt
    return reply


def has_blocker(hole_cards, blocker_ranks=(14, 13)) -> bool:
    return any(c[0] in blocker_ranks for c in hole_cards)


def count_outs(kept_2, board, dead_cards=None) -> int:
    """Count unseen river cards that improve the made-hand category; handles wheel draws."""
    if len(board) != 4 or len(kept_2) != 2:
        return 0
    known = set(kept_2) | set(board) | set(dead_cards or [])
    current = EVALUATOR.evaluate_best(kept_2 + board)
    current_cat = current // (15 ** 5)
    outs = 0
    for card in ALL_CARDS_INT:
        if card in known:
            continue
        new_score = EVALUATOR.evaluate_7(kept_2 + board + [card])
        if new_score // (15 ** 5) > current_cat:
            outs += 1
    return outs




def opp_range_gamma(history, street, req) -> float:
    """Computes range strength shift gamma based on opponent action history."""
    hist = history or []
    cur = [e for e in hist if e.get("street") == street and e.get("actor") == "opp"]
    prev_streets = {e.get("street") for e in hist
                    if e.get("actor") == "opp" and e.get("action") == "raise"
                    and e.get("street") not in ("preflop", street)}
    n_prev = len(prev_streets)
    factor = 1.0
    if STATE.opp_model.stats["post_actions"] >= 20:
        agg = STATE.opp_model.aggression_frequency()
        if agg > 0.55: factor = 0.6
        elif agg > 0.45: factor = 0.8
        elif agg < 0.15: factor = 1.5
        elif agg < 0.25: factor = 1.3

    raised = any(e.get("action") == "raise" for e in cur)
    checked = (not raised) and any(e.get("action") == "check" for e in cur)
    if raised:
        opp_bet = req.get("opp_bet", 0)
        my_bet = req.get("my_bet", 0)
        pre_pot = max(2.0, req.get("pot", 0) - opp_bet - my_bet)
        ratio = max(0.0, (opp_bet - my_bet) / pre_pot)
        g = 0.45 + 0.85 * min(1.5, ratio) + 0.2 * min(2, n_prev)
        return min(2.0, g * factor)
    if checked:
        return -0.35 / factor
    if n_prev > 0:
        return 0.3 * min(2, n_prev) * factor
    return 0.0


# ==============================================================================
# STRATEGY & DECISION ENGINE
# ==============================================================================
def fallback_probabilities(equity: float, pot_odds: float, street: str, is_button: bool,
                           spr: float, opp_model: OpponentModel) -> dict:
    """
    Computes game-theoretic mixed strategy probabilities over (fold, call, raise)
    when no policy match is present or as an equity-based baseline.
    """
    margin = CONFIG["pot_odds_margin_river"] if street == "river" else (
        CONFIG["pot_odds_margin_ip"] if is_button else CONFIG["pot_odds_margin_oop"]
    )
    req_equity = pot_odds + margin
    fold_rate = opp_model.fold_to_bet_rate()

    # Value thresholds
    if equity >= 0.80:
        return {"fold": 0.0, "check_call": 0.20, "bet_raise": 0.80}
    elif equity >= 0.65:
        return {"fold": 0.0, "check_call": 0.50, "bet_raise": 0.50}
    elif equity >= req_equity:
        call_weight = 0.75
        raise_weight = 0.25 if fold_rate > 0.40 else 0.10
        return {"fold": 0.0, "check_call": call_weight, "bet_raise": raise_weight}
    else:
        bluff_freq = 0.15 if (fold_rate > 0.45 and equity >= req_equity - 0.08) else 0.0
        return {"fold": 1.0 - bluff_freq, "check_call": 0.0, "bet_raise": bluff_freq}


def choose_bot_action(req: dict, hole_int: list, board_int: list, street: str) -> dict:
    """Postflop controller using action-time opponent ranges, EV gates and a usable CFR prior."""
    legal = req.get("legal_actions", ["check"])
    to_call = int(req.get("to_call", 0))
    pot = int(req.get("pot", 0))
    opp_bet = int(req.get("opp_bet", 0))
    my_bet = int(req.get("my_bet", 0))
    my_stack = int(req.get("my_stack", 0))
    raises_left = int(req.get("raises_left", 4))
    min_raise = int(req.get("min_raise", opp_bet + 2))
    max_raise = int(req.get("max_raise", my_stack + my_bet))
    is_button = STATE.seat == "button"
    time_left = float(req.get("time_left_ms", STATE.time_left_ms))
    deadline = decision_deadline(time_left)
    hist = req.get("history", []) or []
    gamma = opp_range_gamma(hist, street, req)
    pfw = opponent_preflop_range(hist, STATE.opp_model)
    aggression, is_reraise = opponent_aggression_level(hist, street, req)
    if to_call > 0:
        if is_reraise:
            action_tab = STATE.opp_model.accept_table("raise")
        else:
            pre_bet_pot = max(1, pot - to_call)
            action_tab = STATE.opp_model.accept_table("big" if to_call >= 0.60 * pre_bet_pot else "small")
    else:
        action_tab = STATE.opp_model.accept_table("all")

    # Estimate showdown equity. For three-card flop state, jointly compare all discards.
    outs = 0
    if len(hole_int) == 3 and street == "flop":
        flop_str = [INT_TO_CARD[c] for c in board_int[:3]]
        cands = crn_candidate_equities(
            list(STATE.hole_cards), flop_str, STATE.discard_model, gamma,
            samples=int(CONFIG["discard_mc_samples"] * min(1.5, STATE.sample_scale())),
            pfw=pfw, deadline=deadline, action_tab=action_tab,
            aggression=aggression if to_call > 0 else 0.0)
        equity = max(c[0] for c in cands)
    else:
        samples = int(CONFIG["postflop_mc_samples"] * min(1.5, STATE.sample_scale()))
        equity = EQUITY_ENGINE.equity(
            hole_int, board_int, STATE.opp_discard_int, STATE.my_discard_int,
            STATE.discard_model, gamma, samples, pfw=pfw, deadline=deadline,
            min_samples=CONFIG["min_adaptive_samples"],
            action_tab=action_tab, aggression=aggression if to_call > 0 else 0.0)
        if street == "turn":
            dead = [c for c in (STATE.my_discard_int, STATE.opp_discard_int) if c is not None]
            outs = count_outs(hole_int, board_int, dead)

    pot_odds = to_call / float(pot + to_call) if pot + to_call > 0 else 0.0
    spr = my_stack / max(1, pot)
    can_raise = "raise" in legal and raises_left > 0
    fold_rate = STATE.opp_model.fold_to_bet_rate()
    agg = STATE.opp_model.aggression_frequency()

    # Policy keys now match the actual stored MCCFR information-set schema.
    seat_name = "BUTTON" if is_button else "BIG_BLIND"
    eq_bucket = bucket_equity(equity)
    action_state = "FACING_BET" if to_call > 0 else "CHECKED_TO"
    key = None
    if street == "flop" and len(hole_int) == 3:
        key = f"FLOP:{seat_name}:{eq_bucket}_{classify_preflop_3card(hole_int)}:{action_state}"
    elif street == "turn":
        key = f"TURN:{seat_name}:{eq_bucket}_{bucket_draw(outs)}:{action_state}"
    elif street == "river":
        key = f"RIVER:{seat_name}:{eq_bucket}:{action_state}"
    policy = POLICY_MANAGER.query(key) if key else None
    baseline = fallback_probabilities(equity, pot_odds, street, is_button, spr, STATE.opp_model)
    if policy:
        blend = CONFIG["policy_blend"]
        policy_probs = {a: (1.0 - blend) * baseline[a] + blend * policy[a] for a in ACTIONS}
        z = sum(policy_probs.values()) or 1.0
        policy_probs = {a: p / z for a, p in policy_probs.items()}
    else:
        policy_probs = baseline
    p_raise_policy = policy_probs["bet_raise"]
    p_call_policy = policy_probs["check_call"]

    def raise_to_fraction(fraction, facing=False):
        # Same size mixture for value bets and bluffs avoids a simple sizing tell.
        if fold_rate < 0.22:  # calling station: maximize value, reduce bluffing elsewhere
            fraction = max(fraction, 1.0)
        target_base = (opp_bet if facing else my_bet)
        pot_base = (pot + to_call) if facing else pot
        return max(min_raise, min(max_raise, int(target_base + pot_base * fraction)))

    size_mix = CONFIG["bet_size_mix"]

    # Facing a bet/raise.
    if to_call > 0:
        margin = CONFIG["pot_odds_margin_river"] if street == "river" else (
            CONFIG["pot_odds_margin_ip"] if is_button else CONFIG["pot_odds_margin_oop"])
        required = pot_odds + margin
        # Short-stack value commitment: do not leave a tiny stack behind with a strong hand.
        if can_raise and spr < 1.5 and equity >= max(0.62, required + 0.08):
            return {"type": "action", "action": "raise", "amount": max_raise}
        # Respect EV before using policy probabilities: a policy cannot force a negative-EV call.
        if can_raise and equity >= max(0.70, required + 0.16):
            # Mix a few calls with strong hands to protect the calling range.
            if random.random() < max(0.55, p_raise_policy):
                fraction = random.choice(size_mix)
                return {"type": "action", "action": "raise", "amount": raise_to_fraction(fraction, True)}
        if can_raise and street != "river" and outs >= 8 and equity >= required - 0.06:
            semi_freq = min(0.35, max(0.08, p_raise_policy * 0.55))
            if random.random() < semi_freq:
                return {"type": "action", "action": "raise", "amount": raise_to_fraction(random.choice(size_mix), True)}
        if "call" in legal and equity >= required:
            # Strong made hands occasionally slow-play; policy informs the mix, EV remains the gate.
            if equity >= 0.82 and can_raise and random.random() < 0.12:
                return {"type": "action", "action": "raise", "amount": raise_to_fraction(random.choice(size_mix), True)}
            return {"type": "action", "action": "call"}
        if "call" in legal and equity >= pot_odds and equity >= required - 0.025 and p_call_policy > policy_probs["fold"]:
            return {"type": "action", "action": "call"}
        # Bluff-raises only with credible blockers and an opponent who demonstrably over-folds.
        if can_raise and fold_rate > 0.58 and equity < 0.28 and has_blocker(hole_int, (14, 13)):
            if random.random() < min(0.10, 0.04 + (fold_rate - 0.58) * 0.20):
                return {"type": "action", "action": "raise", "amount": raise_to_fraction(0.75, True)}
        return {"type": "action", "action": "fold"} if "fold" in legal else {"type": "action", "action": "check"}

    # Checked to us / first to act.
    if not can_raise:
        return {"type": "action", "action": "check"}
    is_wet = False
    if len(board_int) >= 3:
        suit_counts = Counter(c[1] for c in board_int)
        is_wet = max(suit_counts.values(), default=0) >= 3

    # Betting frequency uses both hand EV and the policy's raise mass.
    bet = False
    if equity >= 0.80:
        bet = random.random() < max(0.72, p_raise_policy)
    elif equity >= 0.66:
        bet = random.random() < max(0.58, p_raise_policy)
    elif equity >= 0.54:
        value_freq = 0.55 if fold_rate < 0.22 else 0.42
        bet = random.random() < max(value_freq, min(0.75, p_raise_policy))
    elif street != "river" and outs >= 8:
        bet = random.random() < max(0.25, min(0.55, p_raise_policy + 0.15))
    elif is_button and equity >= 0.46 and fold_rate > 0.35:
        bet = random.random() < min(0.35, 0.12 + p_raise_policy * 0.25)
    elif equity < 0.25 and fold_rate > 0.58 and street == "river":
        bet = random.random() < min(0.12, 0.03 + (fold_rate - 0.58) * 0.20)

    if bet:
        fraction = random.choice(size_mix)
        # Against a station use larger value bets, but never increase bluff frequency for it.
        if fold_rate < 0.22 and equity >= 0.66:
            fraction = random.choice((0.75, 1.0, 1.0))
        return {"type": "action", "action": "raise", "amount": raise_to_fraction(fraction, False)}
    return {"type": "action", "action": "check"}




def classify_preflop_3card(cards_3) -> str:
    """Helper to classify preflop 3-card hand into canonical cluster name."""
    ranks = sorted([c[0] for c in cards_3], reverse=True)
    suits = [c[1] for c in cards_3]
    suit_counts = Counter(suits).values()
    max_suit = max(suit_counts)
    r_counts = Counter(ranks)

    if 3 in r_counts.values(): return "TRIPS"
    if 2 in r_counts.values():
        paired_rank = max(r for r, cnt in r_counts.items() if cnt == 2)
        if paired_rank >= 10: return "PAIR_HIGH"
        elif paired_rank >= 6: return "PAIR_MID"
        return "PAIR_LOW"
    if all(r >= 10 for r in ranks):
        return "BROADWAY_SUITED" if max_suit >= 2 else "BROADWAY_OFFSUIT"
    if ranks[0] == 14 and max_suit >= 2: return "SUITED_ACE"
    if (ranks[0] - ranks[1] <= 2) and (ranks[1] - ranks[2] <= 2) and max_suit >= 2:
        return "SUITED_CONNECTOR"
    if ranks[0] >= 11: return "HIGH_OFFSUIT"
    return "WEAK_OFFSUIT"


def bucket_equity(eq: float) -> str:
    if eq >= 0.80: return "EQ_VERY_HIGH"
    if eq >= 0.65: return "EQ_HIGH"
    if eq >= 0.48: return "EQ_MID"
    if eq >= 0.32: return "EQ_LOW"
    return "EQ_VERY_LOW"


def bucket_draw(outs: int) -> str:
    if outs >= 8: return "STRONG_DRAW"
    if outs >= 4: return "WEAK_DRAW"
    return "NO_DRAW"


def choose_preflop_action(req: dict, hole_3_int: list, seat: str, percentile: float,
                          equity: float, policy_probs=None) -> dict:
    """Preflop strategy based on simulated equity versus the opponent's action-conditioned range."""
    legal = req.get("legal_actions", ["check"])
    to_call = int(req.get("to_call", 0))
    pot = int(req.get("pot", 0))
    opp_bet = int(req.get("opp_bet", 0))
    my_bet = int(req.get("my_bet", 0))
    raises_left = int(req.get("raises_left", 4))
    min_raise = int(req.get("min_raise", opp_bet + 2))
    max_raise = int(req.get("max_raise", 200))
    has_ak = has_blocker(hole_3_int, (14, 13))
    pf = policy_probs or {"fold": 0.0, "check_call": 0.5, "bet_raise": 0.5}
    fold_rate = STATE.opp_model.preflop_fold_rate()
    open_floor = 0.08 if STATE.opp_model.stats["my_pre_raises"] >= 20 and fold_rate > 0.55 else CONFIG["preflop_open_min_p"]

    if seat == "button" and my_bet <= 1 and to_call <= 1:
        # Button opening: percentile protects against noisy equity estimates; equity confirms EV.
        if "raise" in legal and percentile >= open_floor and equity >= 0.50:
            amount = max(min_raise, min(max_raise, 5))
            return {"type": "action", "action": "raise", "amount": amount}
        if "call" in legal and equity >= max(0.30, to_call / max(1.0, pot + to_call) + 0.04):
            return {"type": "action", "action": "call"}
        return {"type": "action", "action": "fold" if "fold" in legal else "check"}

    if to_call == 0:
        if "raise" in legal and percentile >= 0.62 and equity >= 0.57 and random.random() < max(0.65, pf["bet_raise"]):
            return {"type": "action", "action": "raise", "amount": max(min_raise, min(max_raise, 6))}
        return {"type": "action", "action": "check" if "check" in legal else "call"}

    pot_odds = to_call / float(max(1, pot + to_call))
    margin = 0.035 if seat == "button" else 0.05
    required = pot_odds + margin
    # Premium re-raises; do not bluff 3-bet into an opponent whose range is already strong.
    if "raise" in legal and raises_left > 0 and percentile >= 0.94 and equity >= max(0.68, required + 0.18):
        size = max(min_raise, min(max_raise, max(opp_bet * 2 + 2, int(pot * 1.8))))
        return {"type": "action", "action": "raise", "amount": size}
    if "call" in legal and equity >= required:
        return {"type": "action", "action": "call"}
    # Very small price: allow a thin continue only when simulated equity is close and policy favours calling.
    if "call" in legal and to_call <= max(2, int(pot * 0.12)) and equity >= pot_odds and pf["check_call"] > pf["fold"]:
        return {"type": "action", "action": "call"}
    return {"type": "action", "action": "fold" if "fold" in legal else "check"}




def choose_action(req: dict) -> dict:
    """Action dispatcher with a hard decision budget and corrected street-specific policy keys."""
    try:
        STATE.last_req = req
        legal = req.get("legal_actions", ["check"])
        time_left = float(req.get("time_left_ms", STATE.time_left_ms))
        if STATE.is_locked() or time_left < CONFIG["panic_time_ms"]:
            return {"type": "action", "action": "check"} if "check" in legal else {"type": "action", "action": "fold"}

        street = req.get("street", "preflop")
        board_int = [CARD_TO_INT[c] for c in req.get("board", [])]
        hole_int = [CARD_TO_INT[c] for c in STATE.hole_cards]
        deadline = decision_deadline(time_left)
        req["_decision_deadline"] = deadline

        if street == "preflop":
            percentile = PREFLOP_TABLE.get_percentile(hole_int)
            pfw = opponent_preflop_range(req.get("history", []), STATE.opp_model)
            equity = preflop_equity_mc(
                hole_int, pfw=pfw, deadline=deadline,
                samples=CONFIG["preflop_mc_samples"])
            seat_name = "BUTTON" if STATE.seat == "button" else "BIG_BLIND"
            action_state = "FACING_BET" if int(req.get("to_call", 0)) > 0 else "CHECKED_TO"
            policy_key = f"PREFLOP:{seat_name}:{classify_preflop_3card(hole_int)}:{action_state}"
            policy = POLICY_MANAGER.query(policy_key)
            reply = choose_preflop_action(req, hole_int, STATE.seat, percentile, equity, policy)
        else:
            reply = choose_bot_action(req, hole_int, board_int, street)
        return sanitize_action_reply(reply, req)
    except Exception as e:
        debug_log(f"Error in choose_action: {e!r}")
        return safe_fallback_action(req.get("legal_actions", ["check"]))




def choose_discard(req: dict) -> dict:
    """Discard dispatcher with Ansh-specific opponent discard and preflop range models."""
    try:
        hole = req.get("hole_cards", STATE.hole_cards)
        board = req.get("board", [])
        time_left = float(req.get("time_left_ms", STATE.time_left_ms))
        if STATE.is_locked():
            return {"type": "discard", "card": default_safe_discard(hole)}
        if len(hole) == 3 and len(board) >= 3:
            last = STATE.last_req or {}
            hist = last.get("history", []) if last.get("hand_id") == req.get("hand_id") else []
            gamma = max(0.0, opp_range_gamma(hist, "flop", last)) if hist else 0.0
            pfw = opponent_preflop_range(hist, STATE.opp_model)
            aggr, _ = opponent_aggression_level(hist, "flop", last) if hist else (0.0, False)
            action_tab = STATE.opp_model.accept_table("all")
            deadline = decision_deadline(time_left, 60.0)
            card = choose_best_discard_crn(hole, board[:3], time_left,
                                           STATE.discard_model, gamma, pfw, deadline,
                                           action_tab, aggr)
        else:
            card = default_safe_discard(hole)
        return {"type": "discard", "card": card}
    except Exception as e:
        debug_log(f"Error in choose_discard: {e!r}")
        return {"type": "discard", "card": default_safe_discard(req.get("hole_cards", []))}




# ==============================================================================
# MAIN PROTOCOL LOOP
# ==============================================================================
def run_startup_self_test():
    """Runs fast self-tests on evaluator, discard model, and policy loading."""
    try:
        royal = [(14, 0), (13, 0), (12, 0), (11, 0), (10, 0), (2, 1), (3, 2)]
        sf = [(9, 0), (8, 0), (7, 0), (6, 0), (5, 0), (2, 1), (3, 2)]
        assert EVALUATOR.evaluate_7(royal) > EVALUATOR.evaluate_7(sf)

        test_hole = ["As", "Ks", "2c"]
        test_flop = ["Kd", "Qh", "Jc"]
        chosen = choose_best_discard_crn(test_hole, test_flop, 60000.0, STATE.discard_model)
        assert chosen in test_hole
        test5 = [(14, 0), (13, 0), (12, 0), (11, 0), (10, 0)]
        assert EVALUATOR.evaluate_5(test5) > EVALUATOR.evaluate_5([(9, 0), (8, 0), (7, 0), (6, 0), (5, 0)])
        assert DiscardModel.get_optimal_discard(
            [(14, 0), (13, 0), (2, 1)], [(13, 1), (12, 2), (11, 3)]) in [(14, 0), (13, 0), (2, 1)]
        debug_log(f"Startup self-test PASSED (sample discard: {chosen}, policy loaded={POLICY_MANAGER.is_loaded})")
    except Exception as ex:
        debug_log(f"Self-test error: {ex}")


def main():
    run_startup_self_test()

    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try:
            msg = json.loads(line)
        except Exception:
            continue

        msg_type = msg.get("type")
        if "time_left_ms" in msg:
            STATE.time_left_ms = float(msg["time_left_ms"])

        if msg_type == "init":
            STATE.on_init(msg)
            continue
        elif msg_type == "new_hand":
            STATE.on_new_hand(msg)
            continue
        elif msg_type == "discard_result":
            STATE.on_discard_result(msg)
            continue
        elif msg_type == "hand_result":
            STATE.on_hand_result(msg)
            continue
        elif msg_type == "notice":
            debug_log(f"ENGINE NOTICE: code={msg.get('code')}, applied={msg.get('applied')}")
            continue
        elif msg_type == "match_end":
            debug_log(f"Match ended. Final net: {STATE.running_net:+d}")
            break

        reply = None
        if msg_type == "action_request":
            reply = choose_action(msg)
        elif msg_type == "discard_request":
            reply = choose_discard(msg)
        else:
            continue

        if reply:
            sys.stdout.write(json.dumps(reply, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()