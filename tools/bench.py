#!/usr/bin/env python3
# ==============================================================================
# tools/bench.py — Multi-Match Benchmark Harness
# Owner: Shared (Person A & Person B)
#
# Responsibilities:
# - Run engine.py between two bots over N matches with varied seeds.
# - Support running bots from raw bot.py script or from submission .zip archives.
# - Report aggregate performance: net chips, win rate, notices, time used, crashes.
# ==============================================================================

import argparse
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import zipfile


def resolve_bot_path(bot_arg: str, temp_dirs: list[str]) -> str:
    """Resolves bot path. If a .zip file is given, unpacks it to a temp folder."""
    path = os.path.abspath(bot_arg)
    if not os.path.exists(path):
        # Convenient fallback: check inside src/ (e.g. if passing 'bot.py')
        root_dir = Path(__file__).resolve().parent.parent
        src_candidate = root_dir / "src" / bot_arg
        if src_candidate.is_file():
            path = str(src_candidate)
        else:
            sys.exit(f"Error: bot file not found: {path}")

    if path.endswith(".zip"):
        temp_dir = tempfile.mkdtemp(prefix="pokerbot_bench_")
        temp_dirs.append(temp_dir)
        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(temp_dir)
        bot_py = os.path.join(temp_dir, "bot.py")
        if not os.path.isfile(bot_py):
            sys.exit(f"Error: {path} does not contain bot.py at root level.")
        return bot_py
    return path


def parse_engine_summary(stdout_text: str) -> dict:
    """Extracts summary metrics from engine stdout."""
    res = {
        "net_a": 0,
        "net_b": 0,
        "time_a": 0.0,
        "time_b": 0.0,
        "notices_a": 0,
        "notices_b": 0,
        "winner": "draw",
        "forfeit": False,
        "forfeit_reason": "",
    }

    # Match A line: "  A  path  net   +10   time used   0.12 s of 60 s   notices 0"
    match_a = re.search(r"^\s*A\s+.*?\s+net\s+([+-]?\d+)\s+time used\s+([\d.]+)\s*s\s+of.*?notices\s+(\d+)", stdout_text, re.MULTILINE)
    if match_a:
        res["net_a"] = int(match_a.group(1))
        res["time_a"] = float(match_a.group(2))
        res["notices_a"] = int(match_a.group(3))

    match_b = re.search(r"^\s*B\s+.*?\s+net\s+([+-]?\d+)\s+time used\s+([\d.]+)\s*s\s+of.*?notices\s+(\d+)", stdout_text, re.MULTILINE)
    if match_b:
        res["net_b"] = int(match_b.group(1))
        res["time_b"] = float(match_b.group(2))
        res["notices_b"] = int(match_b.group(3))

    if "forfeited" in stdout_text:
        res["forfeit"] = True
        for line in stdout_text.splitlines():
            if "forfeited" in line:
                res["forfeit_reason"] = line.strip()

    if "Result: A wins" in stdout_text:
        res["winner"] = "A"
    elif "Result: B wins" in stdout_text:
        res["winner"] = "B"
    else:
        res["winner"] = "draw"

    return res


def run_benchmark(
    bot_a: str,
    bot_b: str,
    matches: int = 5,
    hands: int = 400,
    stage: int = 1,
    python_bin: str = sys.executable,
) -> None:
    """Executes N matches between bot_a and bot_b."""
    temp_dirs: list[str] = []
    root_dir = Path(__file__).resolve().parent.parent
    engine_path = str(root_dir / "engine.py")

    try:
        resolved_a = resolve_bot_path(bot_a, temp_dirs)
        resolved_b = resolve_bot_path(bot_b, temp_dirs)

        print("=" * 78)
        print(f"BENCHMARK: {Path(bot_a).name} (A) vs {Path(bot_b).name} (B)")
        print(f"Configuration: {matches} matches x {hands} hands (Stage {stage})")
        print("=" * 78)

        total_net_a = 0
        total_net_b = 0
        wins_a = 0
        wins_b = 0
        draws = 0
        total_time_a = 0.0
        total_time_b = 0.0
        total_notices_a = 0
        total_notices_b = 0
        forfeits = 0

        header = f"{'Match':<6} | {'Seed':<10} | {'Net A':>7} | {'Net B':>7} | {'Winner':<6} | {'Time A':>7} | {'Time B':>7} | {'Notices':>7}"
        print(header)
        print("-" * len(header))

        for i in range(1, matches + 1):
            seed = str(random.randint(100_000, 999_999))
            cmd = [
                python_bin,
                engine_path,
                resolved_a,
                resolved_b,
                "--stage", str(stage),
                "--hands", str(hands),
                "--seed", seed,
                "--log-dir", "",  # disable file log for speed
            ]

            proc = subprocess.run(cmd, capture_output=True, text=True)
            output = proc.stdout
            summary = parse_engine_summary(output)

            total_net_a += summary["net_a"]
            total_net_b += summary["net_b"]
            total_time_a += summary["time_a"]
            total_time_b += summary["time_b"]
            total_notices_a += summary["notices_a"]
            total_notices_b += summary["notices_b"]

            if summary["winner"] == "A":
                wins_a += 1
            elif summary["winner"] == "B":
                wins_b += 1
            else:
                draws += 1

            if summary["forfeit"]:
                forfeits += 1

            notice_str = f"{summary['notices_a']}/{summary['notices_b']}"
            print(
                f"{i:<6} | {seed:<10} | {summary['net_a']:+7d} | {summary['net_b']:+7d} | "
                f"{summary['winner']:<6} | {summary['time_a']:>6.2f}s | {summary['time_b']:>6.2f}s | "
                f"{notice_str:>7}"
            )

        print("=" * 78)
        print("AGGREGATE SUMMARY:")
        print(f"  Total Net Chips : Bot A {total_net_a:+d} | Bot B {total_net_b:+d}")
        print(f"  Match Score     : {wins_a} Wins, {wins_b} Losses, {draws} Draws ({wins_a / matches * 100:.1f}% win rate)")
        print(f"  Total Time Used : Bot A {total_time_a:.2f}s | Bot B {total_time_b:.2f}s")
        print(f"  Total Notices   : Bot A {total_notices_a} | Bot B {total_notices_b}")
        if forfeits > 0:
            print(f"  WARNING: {forfeits} matches had forfeits or crashes!")
        else:
            print("  Cleanliness     : 0 crashes, 0 forfeits.")
        print("=" * 78)

    finally:
        # Clean up temporary unpacked zip directories
        for td in temp_dirs:
            try:
                import shutil
                shutil.rmtree(td, ignore_errors=True)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Multi-match benchmark runner for Pokerbots")
    parser.add_argument("bot_a", help="Path to Bot A (bot.py or .zip)")
    parser.add_argument("bot_b", help="Path to Bot B (bot.py or .zip)")
    parser.add_argument("-n", "--matches", type=int, default=5, help="Number of matches to play (default: 5)")
    parser.add_argument("--hands", type=int, default=400, help="Hands per match, even number (default: 400)")
    parser.add_argument("--stage", type=int, choices=(1, 2), default=1, help="Stage rules to apply (default: 1)")
    args = parser.parse_args()

    run_benchmark(args.bot_a, args.bot_b, matches=args.matches, hands=args.hands, stage=args.stage)


if __name__ == "__main__":
    main()
