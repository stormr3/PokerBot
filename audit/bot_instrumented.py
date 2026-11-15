#!/usr/bin/env python3
# ==============================================================================
# bot_instrumented.py — Instrumented copy of src/bot.py for audit purposes.
# DECISION LOGIC IS IDENTICAL TO src/bot.py.
# Added: per-decision CSV logging to audit/decisions.csv
# AUDIT USE ONLY — do not submit this file.
# ==============================================================================

import csv
import json
import os
import sys
import time
from pathlib import Path

# --- path setup (identical to src/bot.py) ---
BOT_DIR = str(Path(__file__).resolve().parent.parent / "src")
if BOT_DIR not in sys.path:
    sys.path.insert(0, BOT_DIR)

import betting
import config
import discard
from evaluator import default_discard
from opponent_model import OpponentModel
from state import GameState

# --- CSV log setup ---
_CSV_PATH = os.path.join(os.path.dirname(__file__), "decisions.csv")
_CSV_FIELDS = [
    "hand_id", "seat", "street", "pot", "to_call",
    "my_equity_estimate", "action_taken", "amount",
    "time_ms", "hand_outcome_net"
]

_csv_file = open(_CSV_PATH, "w", newline="", encoding="utf-8")
_csv_writer = csv.DictWriter(_csv_file, fieldnames=_CSV_FIELDS)
_csv_writer.writeheader()

# Pending rows waiting for hand_outcome_net (filled in at hand_result)
_pending_rows: list[dict] = []

_CUMULATIVE_STDERR_BYTES = 0


def log_debug(message: str) -> None:
    global _CUMULATIVE_STDERR_BYTES
    if not config.DEBUG_LOGGING:
        return
    if _CUMULATIVE_STDERR_BYTES < config.MAX_STDERR_BYTES:
        msg = f"[DEBUG] {message}\n"
        enc = len(msg.encode("utf-8"))
        if _CUMULATIVE_STDERR_BYTES + enc <= config.MAX_STDERR_BYTES:
            sys.stderr.write(msg)
            sys.stderr.flush()
            _CUMULATIVE_STDERR_BYTES += enc


def handle_action_request(msg: dict, state: GameState, opp_model: OpponentModel) -> dict:
    legal_actions = msg.get("legal_actions", [])
    t0 = time.perf_counter()
    eq_estimate = None
    try:
        state.on_action_request(msg)
        # Capture equity estimate from modules (read state after decision for approximation)
        reply = betting.decide(msg, state, opp_model)
        if not isinstance(reply, dict) or reply.get("type") != "action":
            raise ValueError(f"Malformed reply: {reply}")
        action = reply.get("action")
        if action not in legal_actions:
            raise ValueError(f"Illegal action: {action}")
        if action == "raise":
            amt = reply.get("amount")
            min_r = msg.get("min_raise", 2)
            max_r = msg.get("max_raise", 200)
            if not isinstance(amt, int) or amt < min_r or amt > max_r:
                raise ValueError(f"Illegal raise amount: {amt}")
    except Exception as err:
        log_debug(f"Action fallback: {err}")
        action = "check" if "check" in legal_actions else "fold"
        reply = {"type": "action", "action": action}

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    row = {
        "hand_id": state.hand_id,
        "seat": state.seat,
        "street": msg.get("street", "?"),
        "pot": msg.get("pot", 0),
        "to_call": msg.get("to_call", 0),
        "my_equity_estimate": eq_estimate,
        "action_taken": reply.get("action"),
        "amount": reply.get("amount", ""),
        "time_ms": f"{elapsed_ms:.2f}",
        "hand_outcome_net": None,
    }
    _pending_rows.append(row)
    return reply


def handle_discard_request(msg: dict, state: GameState, opp_model: OpponentModel) -> dict:
    hole_cards = msg.get("hole_cards", [])
    t0 = time.perf_counter()
    try:
        state.on_discard_request(msg)
        reply = discard.choose(msg, state, opp_model)
        if not isinstance(reply, dict) or reply.get("type") != "discard":
            raise ValueError(f"Malformed discard: {reply}")
        card = reply.get("card")
        if card not in hole_cards:
            raise ValueError(f"Illegal discard: {card}")
    except Exception as err:
        log_debug(f"Discard fallback: {err}")
        fallback_card = default_discard(hole_cards)
        reply = {"type": "discard", "card": fallback_card}

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    row = {
        "hand_id": state.hand_id,
        "seat": state.seat,
        "street": "discard",
        "pot": msg.get("pot", 0),
        "to_call": 0,
        "my_equity_estimate": None,
        "action_taken": f"discard:{reply.get('card')}",
        "amount": "",
        "time_ms": f"{elapsed_ms:.2f}",
        "hand_outcome_net": None,
    }
    _pending_rows.append(row)
    return reply


def flush_pending(net: int) -> None:
    for row in _pending_rows:
        row["hand_outcome_net"] = net
        _csv_writer.writerow(row)
    _csv_file.flush()
    _pending_rows.clear()


def run_bot() -> None:
    state = GameState()
    opp_model = OpponentModel()

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception as err:
            log_debug(f"JSON decode error: {err}")
            continue

        msg_type = msg.get("type")
        reply = None

        if msg_type == "action_request":
            reply = handle_action_request(msg, state, opp_model)
        elif msg_type == "discard_request":
            reply = handle_discard_request(msg, state, opp_model)
        elif msg_type == "init":
            state.on_init(msg)
        elif msg_type == "new_hand":
            state.on_new_hand(msg)
        elif msg_type == "discard_result":
            state.on_discard_result(msg, opp_model)
        elif msg_type == "hand_result":
            state.on_hand_result(msg, opp_model)
            flush_pending(msg.get("net", 0))
        elif msg_type == "notice":
            state.on_notice(msg)
            log_debug(f"Engine notice: {msg}")
        elif msg_type == "match_end":
            log_debug("Match end. Exiting.")
            break
        else:
            continue

        if reply is not None:
            print(json.dumps(reply, separators=(",", ":")), flush=True)


def main() -> None:
    try:
        run_bot()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        _csv_file.close()


if __name__ == "__main__":
    main()
