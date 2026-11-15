#!/usr/bin/env python3
"""Shared protocol loop, legality guards, equity helpers, and hand classifiers for ./zoo/."""

from __future__ import annotations

import json
from pathlib import Path
import random
import sys
from time import perf_counter as now
from typing import Any

# Ensure src/ is importable so zoo bots reuse the authoritative evaluator/equity/tables.
_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import equity as eq  # noqa: E402
from evaluator import CARD_INT, RANK_VALUE, SUIT_ORDER, VALID_CARDS, default_discard, eval_cards  # noqa: E402
import preflop_table as pt  # noqa: E402


def can_raise(req: dict[str, Any]) -> bool:
    min_r = req.get("min_raise")
    max_r = req.get("max_raise")
    return (
        "raise" in req.get("legal_actions", [])
        and min_r is not None
        and max_r is not None
        and max_r >= min_r
        and req.get("raises_left", 4) > 0
    )


def clamp_raise(req: dict[str, Any], target: int) -> int:
    lo = int(req["min_raise"])
    hi = int(req["max_raise"])
    return max(lo, min(hi, int(target)))


def raise_pot_frac(req: dict[str, Any], frac: float) -> dict[str, Any]:
    pot = int(req.get("pot", 0))
    opp_bet = int(req.get("opp_bet", 0))
    to_call = int(req.get("to_call", 0))
    target = opp_bet + int(frac * (pot + to_call))
    return {"type": "action", "action": "raise", "amount": clamp_raise(req, target)}


def simple_action(action: str) -> dict[str, Any]:
    return {"type": "action", "action": action}


def safe_action(req: dict[str, Any], reply: dict[str, Any]) -> dict[str, Any]:
    legal = req.get("legal_actions", [])
    act = reply.get("action")
    if act not in legal:
        if "check" in legal:
            return simple_action("check")
        if "call" in legal:
            return simple_action("call")
        return simple_action(legal[0] if legal else "fold")
    if act == "raise":
        if not can_raise(req):
            return simple_action("call" if "call" in legal else ("check" if "check" in legal else "fold"))
        amt = reply.get("amount")
        if not isinstance(amt, int) or isinstance(amt, bool):
            amt = int(req["min_raise"])
        return {"type": "action", "action": "raise", "amount": clamp_raise(req, amt)}
    return simple_action(act)


def count_street_raises(history: list[dict[str, Any]], street: str) -> int:
    return sum(1 for h in (history or []) if h.get("street") == street and h.get("action") == "raise")


def hand_percentile(hole: list[str]) -> float:
    return pt.get_percentile(hole)


def preflop_equity(hole: list[str], width: float = 100.0) -> float:
    return pt.equity_at_width(hole, width)


def is_top_pair_or_better(hole: list[str], board: list[str]) -> bool:
    """True if any 2-card subset of `hole` makes top pair, overpair, or two-pair+ on `board`."""
    if not board or len(hole) < 2:
        return False
    b_ints = [CARD_INT[c] for c in board]
    max_b = max(c >> 2 for c in b_ints)
    h_ints = [CARD_INT[c] for c in hole]
    pairs = (
        [(h_ints[0], h_ints[1])]
        if len(h_ints) == 2
        else [(h_ints[0], h_ints[1]), (h_ints[0], h_ints[2]), (h_ints[1], h_ints[2])]
    )
    for a, b in pairs:
        s = eval_cards([a, b] + b_ints)
        cat = s >> 20
        if cat >= 2:
            return True
        if cat == 1:
            pair_rank = (s >> 16) & 15
            if pair_rank in (a >> 2, b >> 2) and pair_rank >= max_b:
                return True
    return False


class BaseBot:
    """Base protocol state machine for zoo bots."""

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.hand_id: int = 0
        self.seat: str = "button"
        self.hole_cards: list[str] = []
        self.board: list[str] = []
        self.my_discard: str | None = None
        self.opp_discard: str | None = None
        self.time_left_ms: int = 60_000
        self._cache: dict[str, Any] = {"id": None, "rng": {}}

    def on_init(self, msg: dict[str, Any]) -> None:
        self.time_left_ms = int(msg.get("time_bank_ms", 60_000))

    def on_new_hand(self, msg: dict[str, Any]) -> None:
        self.hand_id = int(msg.get("hand_id", self.hand_id + 1))
        self.seat = msg.get("seat", "button")
        self.hole_cards = list(msg.get("hole_cards", []))
        self.board = []
        self.my_discard = None
        self.opp_discard = None
        self._cache = {"id": self.hand_id, "rng": {}}

    def on_discard_result(self, msg: dict[str, Any]) -> None:
        self.my_discard = msg.get("my_discard")
        self.opp_discard = msg.get("opp_discard")
        if "hole_cards" in msg:
            self.hole_cards = list(msg["hole_cards"])

    def on_hand_result(self, msg: dict[str, Any]) -> None:
        pass

    def _range(self, board_ints: list[int], hole_ints: list[int]):
        if self._cache.get("id") != self.hand_id:
            self._cache = {"id": self.hand_id, "rng": {}}
        key = tuple(board_ints)
        rng_map = self._cache["rng"]
        if key in rng_map:
            return rng_map[key]
        bset = set(board_ints)
        if "base" not in self._cache:
            dead = set(hole_ints) | bset
            if self.my_discard and self.my_discard in CARD_INT:
                dead.add(CARD_INT[self.my_discard])
            od = CARD_INT[self.opp_discard] if (self.opp_discard and self.opp_discard in CARD_INT) else None
            if od is not None:
                dead.add(od)
            self._cache["base"] = eq.build_base(board_ints[:3], dead, od, 0.8)
        pairs0, w0 = self._cache["base"]
        pairs, w = [], []
        for p, x in zip(pairs0, w0):
            if p[0] not in bset and p[1] not in bset:
                pairs.append(p)
                w.append(x)
        strs, pct = eq.street_data(pairs, w, board_ints)
        rng_map[key] = (pairs, w, strs, pct)
        return rng_map[key]

    def postflop_equity(
        self,
        req: dict[str, Any],
        flop_samples: int = 120,
        turn_samples: int = 150,
        budget_s: float = 0.035,
    ) -> float:
        board_s = req.get("board", [])
        if not board_s or not self.hole_cards:
            return 0.5
        if int(req.get("time_left_ms", self.time_left_ms)) < 1500:
            return 0.5
        board = [CARD_INT[c] for c in board_s]
        hole = [CARD_INT[c] for c in self.hole_cards]
        deadline = now() + budget_s
        if len(hole) == 3:
            return max(eq.keep_equities(hole, board[:3], 1, flop_samples, deadline, 0.8))
        pairs, w, strs, _ = self._range(board, hole)
        if len(board) >= 5:
            return eq.eq_river(eval_cards(hole + board), strs, w)
        known = set(hole) | set(board)
        for d in (self.my_discard, self.opp_discard):
            if d and d in CARD_INT:
                known.add(CARD_INT[d])
        return eq.eq_turn(hole, board, pairs, w, known, turn_samples, deadline)

    def discard_by_equity(self, req: dict[str, Any], samples: int = 160, budget_s: float = 0.04) -> str:
        hole_s = list(req.get("hole_cards", self.hole_cards))
        if len(hole_s) != 3 or int(req.get("time_left_ms", self.time_left_ms)) < 1500:
            valid = [c for c in hole_s if c in VALID_CARDS]
            return default_discard(valid) if valid else "2s"
        board_s = req.get("board", [])
        if len(board_s) < 3:
            return default_discard(hole_s)
        hole = [CARD_INT[c] for c in hole_s]
        flop = [CARD_INT[c] for c in board_s[:3]]
        eqs = eq.keep_equities(hole, flop, 1, samples, now() + budget_s, 0.8)
        best_i = max(range(3), key=eqs.__getitem__)
        return hole_s[best_i]

    def choose_action(self, req: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def choose_discard(self, req: dict[str, Any]) -> str:
        hole_s = list(req.get("hole_cards", self.hole_cards))
        valid = [c for c in hole_s if c in VALID_CARDS]
        return default_discard(valid) if valid else "2s"


def run_bot(bot: BaseBot) -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if not isinstance(msg, dict):
            continue
        t = msg.get("type")
        reply: dict[str, Any] | None = None
        if t == "init":
            bot.on_init(msg)
        elif t == "new_hand":
            bot.on_new_hand(msg)
        elif t == "action_request":
            bot.time_left_ms = int(msg.get("time_left_ms", bot.time_left_ms))
            if "board" in msg:
                bot.board = list(msg["board"])
            reply = safe_action(msg, bot.choose_action(msg))
        elif t == "discard_request":
            bot.time_left_ms = int(msg.get("time_left_ms", bot.time_left_ms))
            hole_s = list(msg.get("hole_cards", bot.hole_cards))
            card = bot.choose_discard(msg)
            if card not in hole_s or card not in VALID_CARDS:
                valid = [c for c in hole_s if c in VALID_CARDS]
                card = default_discard(valid) if valid else "2s"
            reply = {"type": "discard", "card": card}
        elif t == "discard_result":
            bot.on_discard_result(msg)
        elif t == "hand_result":
            bot.on_hand_result(msg)
        elif t == "match_end":
            break
        if reply is not None:
            print(json.dumps(reply, separators=(",", ":")), flush=True)
