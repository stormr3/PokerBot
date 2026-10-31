"""Main entry point and IPC event loop for the Discard Hold'em Pokerbot.

Official Specifications (Protocol Specification Section 2, 4–6, Rulebook Section 5):
- Python 3.11 bot fresh for every match; reads stdin, writes stdout.
- Matches are played over JSON lines; stdout must contain ONLY protocol JSON replies.
- Responses must be flushed immediately (flush=True).
- Replies sent ONLY to 'action_request' and 'discard_request'.
- 'discard_request' board contains exactly the 3 flop cards; discards are simultaneous.
- 'discard_result' reveals both discards and the 2 remaining hole cards.
- 'hand_result' reports net chips, showdown cards, and remaining hole cards
  (3 if hand ended before discard, 2 otherwise).
- 'notice' is informational only; no reply is expected.
- 'match_end' indicates the end of the match; bot should exit cleanly.

Implementation Choices (Not Official Rules):
- Routing structure, GameState tracking, OpponentModel integration, and safety wrapping.
- Exception handling to prevent any uncaught traceback from leaking to stdout.

Dependencies:
- Standard Library: sys, typing
- Core modules: core.protocol, core.state, core.safety
- Strategy modules: strategy.discard, strategy.betting, strategy.opponent
"""

import sys

from core.protocol import log_debug, read_message, send_reply
from core.safety import sanitize_action, sanitize_discard, get_default_action, get_default_discard
from core.state import GameState
from strategy.betting import decide_postflop_action, decide_preflop_action
from strategy.discard import choose_discard
from strategy.opponent import OpponentModel


def run_bot() -> None:
    """Executes the main protocol loop reading messages and sending replies.

    TODO:
        - Instantiate GameState and OpponentModel.
        - Loop over read_message() until EOF or match_end.
        - Dispatch:
          - 'init': state.update_init(msg)
          - 'new_hand': state.update_new_hand(msg)
          - 'action_request':
              try:
                  state.update_action_request(msg)
                  candidate = decide_preflop_action(state) if state.street == 'preflop' else decide_postflop_action(state, 0.5)
                  reply = sanitize_action(candidate, state.legal_actions, state.min_raise, state.max_raise, state.to_call)
              except Exception as e:
                  log_debug(f"Action exception: {e}")
                  reply = get_default_action(state.legal_actions, state.to_call)
              send_reply(reply)
          - 'discard_request':
              try:
                  state.update_discard_request(msg)
                  candidate = choose_discard(state.hole_cards, state.board, opp_model, state.time_left_ms)
                  reply = sanitize_discard(candidate, state.hole_cards)
              except Exception as e:
                  log_debug(f"Discard exception: {e}")
                  reply = get_default_discard(state.hole_cards)
              send_reply(reply)
          - 'discard_result': state.update_discard_result(msg)
          - 'hand_result':
              state.update_hand_result(msg)
              opp_model.record_hand_history(state.history, state.opp_discard, msg.get("opp_hole_cards"))
          - 'notice': state.update_notice(msg)  # No reply sent
          - 'match_end': break
    """
    raise NotImplementedError("run_bot event loop is not yet implemented.")


def main() -> None:
    """Program entry point."""
    try:
        run_bot()
    except NotImplementedError:
        # Expected during initial scaffold phase
        sys.exit(0)
    except Exception as exc:
        log_debug(f"Fatal bot crash: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
