"""Collect diagnostic JSONL logs for audit/diag_bot/bot.py via zoo/run_suite.py."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(r"c:\VSC_Projects\PokerBots")
PY311 = r"C:\Users\Deep\AppData\Local\Programs\Python\Python311\python.exe"
SUITE = ROOT / "zoo" / "run_suite.py"
CAND = ROOT / "audit" / "diag_bot" / "bot.py"
BASE_LOG_DIR = ROOT / "audit" / "diag_logs"

TARGETS = [
    ("opp_nit", "opp/nit"),
    ("opp_tight_raiser", "opp/tight_raiser"),
    ("zoo_eq_bot", "zoo/eq_bot"),
    ("zoo_tag_bot", "zoo/tag_bot"),
    ("zoo_trap_bot", "zoo/trap_bot"),
    ("zoo_shove_bot_15", "zoo/shove_bot_15"),
    ("zoo_shove_bot_30", "zoo/shove_bot_30"),
    ("zoo_fold_to_big_bot", "zoo/fold_to_big_bot"),
    ("zoo_limp_bot", "zoo/limp_bot"),
    ("opp_always_call", "opp/always_call"),
    ("opp_always_raise", "opp/always_raise"),
]


def main():
    if BASE_LOG_DIR.exists():
        shutil.rmtree(BASE_LOG_DIR)
    BASE_LOG_DIR.mkdir(parents=True)

    for tag, opp_name in TARGETS:
        opp_dir = BASE_LOG_DIR / tag
        opp_dir.mkdir(parents=True, exist_ok=True)
        out_json = BASE_LOG_DIR / f"{tag}_suite.json"
        env = os.environ.copy()
        env["DIAG_LOG_DIR"] = str(opp_dir)
        print(f"\n=== Running diag_bot vs {opp_name} (20 seeds x 400 hands) ===", flush=True)
        cmd = [
            PY311, "-u", str(SUITE), str(CAND),
            "--opponents", opp_name,
            "--seeds", "20",
            "--hands", "400",
            "--workers", "10",
            "--python", PY311,
            "--out", str(out_json),
        ]
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env, text=True)
        if proc.returncode != 0:
            sys.exit(f"Failed on {opp_name} with rc={proc.returncode}")


if __name__ == "__main__":
    main()
