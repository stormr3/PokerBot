"""Comprehensive Fuzz & Fix Verification Harness for Check 8."""
import json
import os
import subprocess
import sys
from pathlib import Path

BOT_PATH = Path(os.environ["TEMP"]) / "pb_ship_extract" / "bot.py"
PY311 = r"C:\Users\Deep\AppData\Local\Programs\Python\Python311\python.exe"
VALID_CARDS = {r + s for r in "23456789TJQKA" for s in "shdc"}


def run_sequence(name: str, items: list[tuple[str, bool, str | None]]):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.Popen(
        [PY311, "-B", str(BOT_PATH)],
        cwd=str(BOT_PATH.parent),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )

    replies = []
    for idx, (raw_line, expects_reply, exp_type) in enumerate(items):
        assert proc.poll() is None, f"[{name}] Bot exited early before item {idx}: {raw_line}"
        proc.stdin.write(raw_line + "\n")
        proc.stdin.flush()
        if expects_reply:
            out_line = proc.stdout.readline()
            assert out_line, f"[{name}] EOF waiting for reply at item {idx}: {raw_line}"
            out_s = out_line.rstrip("\r\n")
            msg = json.loads(out_s)
            assert isinstance(msg, dict), f"[{name}] Non-dict JSON reply: {out_s}"
            assert msg.get("type") == exp_type, f"[{name}] Wrong type {msg} expected {exp_type}"
            if exp_type == "action":
                req = json.loads(raw_line)
                legal = req.get("legal_actions")
                act = msg.get("action")
                if isinstance(legal, list) and legal:
                    assert act in legal, f"[{name}] Illegal action {act} not in {legal} (req={raw_line})"
                else:
                    assert act in ("check", "fold"), f"[{name}] Bad fallback action {msg}"
                if act == "raise":
                    amt = msg.get("amount")
                    min_r = req.get("min_raise")
                    max_r = req.get("max_raise")
                    assert isinstance(amt, int) and not isinstance(amt, bool), f"[{name}] Bad amt {amt}"
                    assert min_r <= amt <= max_r, f"[{name}] Raise {amt} out of [{min_r}, {max_r}]"
            elif exp_type == "discard":
                card = msg.get("card")
                assert isinstance(card, str) and card in VALID_CARDS, f"[{name}] Invalid discard card {card!r}"
                req = json.loads(raw_line)
                hc = req.get("hole_cards")
                if isinstance(hc, list) and any(isinstance(c, str) and c in VALID_CARDS for c in hc):
                    assert card in hc, f"[{name}] Discard {card} not in valid hole_cards {hc}"
            replies.append((idx, out_s))

    proc.stdin.write(json.dumps({"type": "match_end", "reason": "complete"}) + "\n")
    proc.stdin.flush()
    leftover_out, err = proc.communicate(timeout=5)
    assert proc.returncode == 0, f"[{name}] Non-zero exit {proc.returncode}; stderr={err}"
    assert leftover_out.strip() == "", f"[{name}] Extra stdout noise detected: {leftover_out!r}"
    print(f"[PASS] {name}: {len(items)} inputs, {len(replies)} valid replies, 0 extra stdout lines, exit=0")
    return replies, err


def test_fix_a_and_b_unit():
    sys.path.insert(0, str(BOT_PATH.parent))
    import bot
    import postflop
    from state import GameState
    from opponent_model import OpponentModel

    req_no_raise = {
        "legal_actions": ["check"],
        "pot": 10, "to_call": 0, "my_stack": 100, "my_bet": 0,
        "opp_bet": 0, "history": [], "raises_left": 4,
        "min_raise": 2, "max_raise": 100,
    }
    st = GameState()
    opp = OpponentModel()
    opp.faced_bets = 20
    opp.faced_folds = 18
    for _ in range(200):
        r = postflop._choose(0.05, req_no_raise, "flop", st, opp, False)
        assert r == {"type": "action", "action": "check"}, f"Fix (a) failed: {r}"

    for bad_hc in ([], None, 123, ["XX"], ["XX", "YY"], ["bad", "As", "3h"], [None, 42], ["AsXYZ"]):
        r = bot.handle_discard_request({"type": "discard_request", "hole_cards": bad_hc}, st, opp)
        assert r["type"] == "discard" and r["card"] in VALID_CARDS, f"Fix (b) failed on {bad_hc}: {r}"
        if bad_hc == ["bad", "As", "3h"]:
            assert r["card"] == "3h", f"Expected lowest valid card '3h', got {r}"
    print("[PASS] unit_fix_a_and_b: Fix (a) canr bluff guard & Fix (b) empty/malformed discard fallback verified")


def main():
    test_fix_a_and_b_unit()

    items = [
        (json.dumps({"type": "init", "protocol_version": "1.0", "total_hands": 10, "time_bank_ms": 30000}), False, None),
        ("{not valid json", False, None),
        ('{"type": "action_request", "incomplete": ', False, None),
        ("   ", False, None),
        ("garbage", False, None),
        (json.dumps({"type": "ping", "seq": 1}), False, None),
        (json.dumps({"type": "future_protocol_v2", "payload": [1, 2, 3]}), False, None),
        (json.dumps({}), False, None),
        (json.dumps({"type": "new_hand", "hand_id": 1, "seat": "button", "hole_cards": ["As", "Ad", "Ah", "Ac"], "stack": 200, "opp_stack": 200}), False, None),
        (json.dumps({"type": "action_request", "hand_id": 1, "street": "preflop", "board": [], "pot": 3, "my_bet": 1, "opp_bet": 2, "to_call": 1, "my_stack": 199, "opp_stack": 198, "legal_actions": ["fold", "call", "raise"], "min_raise": 4, "max_raise": 200, "raises_left": 3, "history": [], "time_left_ms": 29900}), True, "action"),
        (json.dumps({"type": "notice", "code": "illegal_action", "applied": "check"}), False, None),
        (json.dumps({"type": "action_request", "hand_id": 1, "street": "flop", "board": ["Ks", "Kd", "Kh"], "pot": 10, "my_bet": 0, "opp_bet": 0, "to_call": 0, "my_stack": 195, "opp_stack": 195, "legal_actions": ["check", "raise"], "min_raise": 100, "max_raise": 20, "raises_left": 4, "history": [], "time_left_ms": 29800}), True, "action"),
        (json.dumps({"type": "action_request", "hand_id": 1, "street": "flop", "board": ["Ks", "Kd", "Kh"], "pot": 20, "my_bet": 0, "opp_bet": 10, "to_call": 10, "my_stack": 195, "opp_stack": 185, "legal_actions": ["fold", "call", "raise"], "min_raise": 50, "max_raise": 20, "raises_left": 3, "history": [], "time_left_ms": 29750}), True, "action"),
        (json.dumps({"type": "discard_request", "hand_id": 1, "hole_cards": ["As", "Ad", "Ah", "Ac"], "board": ["Ks", "Kd", "Kh"], "pot": 30, "my_stack": 185, "opp_stack": 185, "time_left_ms": 29700}), True, "discard"),
        (json.dumps({"type": "action_request", "hand_id": 1, "street": "turn", "board": ["Ks", "Kd", "Kh", "2c"], "pot": 30, "my_bet": 0, "opp_bet": 0, "to_call": 0, "my_stack": 185, "opp_stack": 185, "legal_actions": ["check", "raise"], "min_raise": 2, "max_raise": 185, "raises_left": 4, "history": [], "time_left_ms": 29600}), True, "action"),
        (json.dumps({"type": "action_request", "hand_id": 1, "street": "river", "board": ["Ks", "Kd", "Kh", "2c", "7d"], "pot": 30, "my_bet": 0, "opp_bet": 0, "to_call": 0, "my_stack": 185, "opp_stack": 185, "legal_actions": ["check", "raise"], "min_raise": 2, "max_raise": 185, "raises_left": 4, "history": [], "time_left_ms": 29500}), True, "action"),
        (json.dumps({"type": "discard_request", "hand_id": 1, "hole_cards": [], "board": ["2c", "7d", "9h"], "pot": 10}), True, "discard"),
        (json.dumps({"type": "discard_request", "hand_id": 1, "hole_cards": None, "board": ["2c", "7d", "9h"]}), True, "discard"),
        (json.dumps({"type": "discard_request", "hand_id": 1, "hole_cards": ["XX", "YY", "ZZ"], "board": ["2c", "7d", "9h"]}), True, "discard"),
        (json.dumps({"type": "discard_request", "hand_id": 1, "hole_cards": ["bad", "As", "3h"], "board": ["2c", "7d", "9h"]}), True, "discard"),
        (json.dumps({"type": "discard_request", "hand_id": 1, "hole_cards": 12345}), True, "discard"),
        (json.dumps({"type": "discard_request"}), True, "discard"),
        (json.dumps({"type": "action_request", "legal_actions": ["check"]}), True, "action"),
        (json.dumps({"type": "action_request", "street": "turn", "legal_actions": ["fold", "call"]}), True, "action"),
        (json.dumps({"type": "action_request", "street": "river", "board": ["2c", "7d", "9h", "Ts", "Ac"], "legal_actions": ["fold", "call", "raise"], "min_raise": 10, "max_raise": 10, "history": []}), True, "action"),
        (json.dumps({"type": "action_request"}), True, "action"),
        (json.dumps({"type": "discard_result", "my_discard": "Qd", "opp_discard": "3s", "hole_cards": ["As", "Kh"]}), False, None),
        (json.dumps({"type": "hand_result", "hand_id": 1, "result": "fold", "net": -5}), False, None),
        (json.dumps({"type": "new_hand", "hand_id": 2, "seat": "big_blind", "hole_cards": ["Ac", "Ad", "Ks"], "stack": 200, "opp_stack": 200}), False, None),
        (json.dumps({"type": "action_request", "hand_id": 2, "street": "preflop", "board": [], "pot": 6, "my_bet": 2, "opp_bet": 4, "to_call": 2, "my_stack": 198, "opp_stack": 196, "legal_actions": ["fold", "call", "raise"], "min_raise": 6, "max_raise": 200, "raises_left": 2, "history": [], "time_left_ms": 29500}), True, "action"),
        (json.dumps({"type": "notice", "code": "illegal_action", "applied": "call"}), False, None),
        (json.dumps({"type": "action_request", "hand_id": 2, "street": "flop", "board": ["Ah", "7c", "2d"], "pot": 12, "my_bet": 0, "opp_bet": 0, "to_call": 0, "my_stack": 194, "opp_stack": 194, "legal_actions": ["check", "raise"], "min_raise": 2, "max_raise": 194, "raises_left": 4, "history": [], "time_left_ms": 29400}), True, "action"),
    ]
    run_sequence("fuzz_main_battery", items)


if __name__ == "__main__":
    main()
