#!/usr/bin/env python3
# ==============================================================================
# bot.py — Main Entry Point & IPC Event Loop
# Owner: Shared (Person A & Person B)
#
# Official Specifications:
# - Python 3.11 program reading UTF-8 JSON lines from sys.stdin.
# - Output on sys.stdout must contain ONLY protocol JSON replies, flushed immediately.
# - Debug output goes strictly to sys.stderr (capped at 64 KB per match).
# - Replies sent ONLY to 'action_request' and 'discard_request'.
# - Exits cleanly upon receiving 'match_end'.
# ==============================================================================

import json
from pathlib import Path
import sys

# Ensure this directory is at the front of sys.path for sibling imports
BOT_DIR = str(Path(__file__).resolve().parent)
if BOT_DIR not in sys.path:
    sys.path.insert(0, BOT_DIR)

import betting
import config
import discard
from evaluator import default_discard
from opponent_model import OpponentModel
from state import GameState

# Cumulative stderr counter to stay well below the 64 KB tournament limit
_CUMULATIVE_STDERR_BYTES = 0


def log_debug(message: str) -> None:
    """Safely logs debug output to sys.stderr respecting the safety cap."""
    global _CUMULATIVE_STDERR_BYTES
    if not config.DEBUG_LOGGING:
        return
    if _CUMULATIVE_STDERR_BYTES < config.MAX_STDERR_BYTES:
        msg = f"[DEBUG] {message}\n"
        encoded_len = len(msg.encode("utf-8"))
        if _CUMULATIVE_STDERR_BYTES + encoded_len <= config.MAX_STDERR_BYTES:
            sys.stderr.write(msg)
            sys.stderr.flush()
            _CUMULATIVE_STDERR_BYTES += encoded_len


def handle_action_request(msg: dict, state: GameState, opp_model: OpponentModel) -> dict:
    """Dispatches action_request to betting.decide with legal fallback guarding."""
    legal_actions = msg.get("legal_actions", [])
    try:
        state.on_action_request(msg)
        reply = betting.decide(msg, state, opp_model)
        # Verify reply validity
        if not isinstance(reply, dict) or reply.get("type") != "action":
            raise ValueError(f"Malformed action reply: {reply}")
        action = reply.get("action")
        if action not in legal_actions:
            raise ValueError(f"Illegal action proposed: {action} not in {legal_actions}")
        if action == "raise":
            amt = reply.get("amount")
            min_r = msg.get("min_raise", 2)
            max_r = msg.get("max_raise", 200)
            if not isinstance(amt, int) or amt < min_r or amt > max_r:
                raise ValueError(f"Illegal raise amount: {amt} not in [{min_r}, {max_r}]")
        return reply
    except Exception as err:
        log_debug(f"Action fallback triggered: {err}")
        # Official fallback (Section 9.3): check if legal, otherwise fold
        fallback_action = "check" if "check" in legal_actions else "fold"
        return {"type": "action", "action": fallback_action}


def handle_discard_request(msg: dict, state: GameState, opp_model: OpponentModel) -> dict:
    """Dispatches discard_request to discard.choose with legal fallback guarding."""
    hole_cards = msg.get("hole_cards", [])
    try:
        state.on_discard_request(msg)
        reply = discard.choose(msg, state, opp_model)
        if not isinstance(reply, dict) or reply.get("type") != "discard":
            raise ValueError(f"Malformed discard reply: {reply}")
        card = reply.get("card")
        if card not in hole_cards:
            raise ValueError(f"Illegal discard card: {card} not in {hole_cards}")
        return reply
    except Exception as err:
        log_debug(f"Discard fallback triggered: {err}")
        # Official fallback (Section 9.4): lowest rank; tiebreak spades, hearts, diamonds, clubs
        # Guard against empty / malformed hole_cards — never call min() on an empty sequence.
        if hole_cards:
            fallback_card = default_discard(hole_cards)
        else:
            fallback_card = "2s"  # safe sentinel; engine will issue a notice and apply its own default
        return {"type": "discard", "card": fallback_card}


def run_bot() -> None:
    """Main protocol execution loop."""
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
        elif msg_type == "notice":
            state.on_notice(msg)
            log_debug(f"Engine notice received: {msg}")
        elif msg_type == "match_end":
            log_debug("Match end received. Exiting.")
            break
        else:
            # Ignore unrecognized forward-compatible message types (Section 2)
            continue

        if reply is not None:
            # Output MUST be strictly formatted JSON with immediate flush
            print(json.dumps(reply, separators=(",", ":")), flush=True)


def main() -> None:
    """Entry point with top-level crash prevention."""
    try:
        run_bot()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        print(f"[FATAL] Bot exception: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
