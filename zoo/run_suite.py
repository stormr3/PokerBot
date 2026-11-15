#!/usr/bin/env python3
"""Parallel evaluation suite: candidate vs all zoo & trivial opponents across >=20 seeds.

Computes net bb/100 with SE via bootstrap over duplicate PAIRS (hands 2k+1, 2k+2),
match win-rate across seeds (win=1, draw=0.5, loss=0), notices, and time used.
Saves JSON results and compares against a saved baseline, flagging >2 SE regressions.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT_DIR = Path(__file__).resolve().parent.parent
ZOO_DIR = Path(__file__).resolve().parent
ENGINE_PATH = ROOT_DIR / "engine.py"
DEFAULT_PY311 = Path(r"C:\Users\Deep\AppData\Local\Programs\Python\Python311\python.exe")

BIG_BLIND = 2

OPPONENTS: list[tuple[str, Path]] = [
    # Parameterised ./zoo/ opponents
    ("zoo/eq_bot", ZOO_DIR / "eq_bot.py"),
    ("zoo/eq_bot_eps10", ZOO_DIR / "eq_bot_eps10.py"),
    ("zoo/eq_bot_eps20", ZOO_DIR / "eq_bot_eps20.py"),
    ("zoo/shove_bot_15", ZOO_DIR / "shove_bot_15.py"),
    ("zoo/shove_bot_30", ZOO_DIR / "shove_bot_30.py"),
    ("zoo/trap_bot", ZOO_DIR / "trap_bot.py"),
    ("zoo/fold_to_big_bot", ZOO_DIR / "fold_to_big_bot.py"),
    ("zoo/limp_bot", ZOO_DIR / "limp_bot.py"),
    ("zoo/minraise_bot", ZOO_DIR / "minraise_bot.py"),
    ("zoo/tag_bot", ZOO_DIR / "tag_bot.py"),
    ("zoo/bot_v_prev", ZOO_DIR / "bot_v_prev" / "bot.py"),
    ("zoo/bot_selfplay", ZOO_DIR / "bot_selfplay.py"),
    # Legacy trivial/baseline opponents from ./opponents/
    ("opp/always_call", ROOT_DIR / "opponents" / "always_call.py"),
    ("opp/always_raise", ROOT_DIR / "opponents" / "always_raise.py"),
    ("opp/maniac", ROOT_DIR / "opponents" / "maniac.py"),
    ("opp/nit", ROOT_DIR / "opponents" / "nit.py"),
    ("opp/random_bot", ROOT_DIR / "opponents" / "random_bot.py"),
    ("opp/random_raiser", ROOT_DIR / "opponents" / "random_raiser.py"),
    ("opp/station", ROOT_DIR / "opponents" / "station.py"),
    ("opp/tight_folder", ROOT_DIR / "opponents" / "tight_folder.py"),
    ("opp/tight_raiser", ROOT_DIR / "opponents" / "tight_raiser.py"),
]

_HAND_ID_RE = re.compile(r"^#(\d+)\s+button\s+[AB]\s+")
_TAIL_NET_A_RE = re.compile(r"\bA\s+([+-]?\d+)\b")


def resolve_candidate(cand_arg: str, temp_dirs: list[str]) -> Path:
    p = Path(cand_arg)
    if not p.is_file():
        p = ROOT_DIR / cand_arg
    if not p.is_file():
        sys.exit(f"Candidate bot not found: {cand_arg}")
    p = p.resolve()
    if p.suffix.lower() == ".zip":
        td = tempfile.mkdtemp(prefix="zoo_cand_")
        temp_dirs.append(td)
        with zipfile.ZipFile(p, "r") as zf:
            zf.extractall(td)
        bot_py = Path(td) / "bot.py"
        if not bot_py.is_file():
            sys.exit(f"Zip archive missing top-level bot.py: {p}")
        return bot_py
    return p


def parse_summary(stdout_text: str) -> dict:
    res = {
        "played": 0,
        "net_a": 0,
        "net_b": 0,
        "time_a": 0.0,
        "time_b": 0.0,
        "notices_a": 0,
        "notices_b": 0,
        "winner": "draw",
        "forfeit": False,
        "forfeit_bot": None,
        "forfeit_reason": "",
    }
    m_played = re.search(r"(\d+)\s+of\s+(\d+)\s+hands\s+played", stdout_text)
    if m_played:
        res["played"] = int(m_played.group(1))
    m_a = re.search(r"^\s*A\s+.*?\s+net\s+([+-]?\d+)\s+time used\s+([\d.]+)\s*s\s+of.*?notices\s+(\d+)", stdout_text, re.M)
    if m_a:
        res["net_a"] = int(m_a.group(1))
        res["time_a"] = float(m_a.group(2))
        res["notices_a"] = int(m_a.group(3))
    m_b = re.search(r"^\s*B\s+.*?\s+net\s+([+-]?\d+)\s+time used\s+([\d.]+)\s*s\s+of.*?notices\s+(\d+)", stdout_text, re.M)
    if m_b:
        res["net_b"] = int(m_b.group(1))
        res["time_b"] = float(m_b.group(2))
        res["notices_b"] = int(m_b.group(3))

    for line in stdout_text.splitlines():
        if "forfeited" in line:
            res["forfeit"] = True
            res["forfeit_reason"] = line.strip()
            if line.strip().startswith("A forfeited"):
                res["forfeit_bot"] = "A"
            elif line.strip().startswith("B forfeited"):
                res["forfeit_bot"] = "B"

    if "Result: A wins" in stdout_text:
        res["winner"] = "A"
    elif "Result: B wins" in stdout_text:
        res["winner"] = "B"
    else:
        res["winner"] = "draw"
    return res


def parse_pair_nets(match_log: Path) -> list[int]:
    """Parse per-hand net chips for A and sum into duplicate pairs (hands 2k+1, 2k+2)."""
    hand_nets: dict[int, int] = {}
    with match_log.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("#"):
                continue
            hm = _HAND_ID_RE.match(line)
            if not hm:
                continue
            tail = line.rsplit("|", 1)[-1]
            nm = _TAIL_NET_A_RE.search(tail)
            if nm:
                hand_nets[int(hm.group(1))] = int(nm.group(1))
    pairs: list[int] = []
    if not hand_nets:
        return pairs
    max_hid = max(hand_nets)
    for odd_id in range(1, max_hid + 1, 2):
        even_id = odd_id + 1
        if odd_id in hand_nets and even_id in hand_nets:
            pairs.append(hand_nets[odd_id] + hand_nets[even_id])
    return pairs


def run_single_match(
    cand_path: Path,
    opp_name: str,
    opp_path: Path,
    seed: int,
    hands: int,
    stage: int,
    python_bin: str,
    enforce_time_limits: bool,
) -> dict:
    log_dir = Path(tempfile.mkdtemp(prefix="zoo_log_"))
    try:
        cmd = [
            python_bin,
            str(ENGINE_PATH),
            str(cand_path),
            str(opp_path),
            "--stage", str(stage),
            "--hands", str(hands),
            "--seed", str(seed),
            "--log-dir", str(log_dir),
            "--python", python_bin,
        ]
        if not enforce_time_limits:
            cmd.append("--no-time-limits")

        env = os.environ.copy()
        # Give self-play copy a reproducible seed distinct per match seed.
        env["ZOO_SELFPLAY_SEED"] = str(seed + 987_654_321)

        proc = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True, env=env)
        summary = parse_summary(proc.stdout)
        match_log = log_dir / "match.log"
        pair_nets = parse_pair_nets(match_log) if match_log.is_file() else []
        if not summary["forfeit"] and summary["played"] > 0:
            if len(pair_nets) != summary["played"] // 2 or sum(pair_nets) != summary["net_a"]:
                raise RuntimeError(
                    f"Pair parse mismatch for {opp_name} seed {seed}: "
                    f"pairs={len(pair_nets)} played={summary['played']} "
                    f"sum_pairs={sum(pair_nets)} net_a={summary['net_a']}"
                )

        if proc.returncode != 0:
            summary["forfeit"] = True
            summary["forfeit_reason"] = f"engine rc={proc.returncode}: {proc.stderr.strip()}"

        return {
            "opp_name": opp_name,
            "seed": seed,
            "pair_nets": pair_nets,
            **summary,
        }
    finally:
        shutil.rmtree(log_dir, ignore_errors=True)


def bootstrap_bb100_se(pair_nets: list[int], n_boot: int = 2000, rng_seed: int = 42) -> tuple[float, float]:
    """Return (mean_bb100, bootstrap_se_bb100) over duplicate pairs (2 hands = 4 chips/BB-pair)."""
    m = len(pair_nets)
    if m == 0:
        return 0.0, 0.0
    scale = 100.0 / (2.0 * BIG_BLIND)  # 25.0 when BIG_BLIND == 2
    mean_bb100 = (sum(pair_nets) / m) * scale
    if m == 1 or n_boot <= 0:
        return mean_bb100, 0.0
    rng = random.Random(rng_seed)
    boot_vals = [(sum(rng.choices(pair_nets, k=m)) / m) * scale for _ in range(n_boot)]
    se = statistics.stdev(boot_vals)
    return mean_bb100, se


def aggregate_opponent(opp_name: str, runs: list[dict], n_boot: int) -> dict:
    runs_sorted = sorted(runs, key=lambda r: r["seed"])
    all_pairs: list[int] = []
    wins = losses = draws = 0
    notices_a = notices_b = forfeits = 0
    times_a: list[float] = []
    times_b: list[float] = []
    total_net_a = 0
    total_hands = 0

    for r in runs_sorted:
        all_pairs.extend(r["pair_nets"])
        total_net_a += r["net_a"]
        total_hands += r["played"]
        notices_a += r["notices_a"]
        notices_b += r["notices_b"]
        times_a.append(r["time_a"])
        times_b.append(r["time_b"])
        if r["forfeit"]:
            forfeits += 1
        if r["winner"] == "A":
            wins += 1
        elif r["winner"] == "B":
            losses += 1
        else:
            draws += 1

    bb100, se_bb100 = bootstrap_bb100_se(all_pairs, n_boot=n_boot)
    n_matches = len(runs_sorted)
    win_rate = (wins + 0.5 * draws) / n_matches if n_matches else 0.0

    return {
        "opponent": opp_name,
        "matches": n_matches,
        "hands_played": total_hands,
        "pairs": len(all_pairs),
        "net_chips": total_net_a,
        "bb100": round(bb100, 2),
        "se_bb100": round(se_bb100, 2),
        "win_rate": round(win_rate, 4),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "notices_a": notices_a,
        "notices_b": notices_b,
        "forfeits": forfeits,
        "time_a_mean_s": round(statistics.mean(times_a), 2) if times_a else 0.0,
        "time_a_max_s": round(max(times_a), 2) if times_a else 0.0,
        "time_a_total_s": round(sum(times_a), 2),
        "time_b_total_s": round(sum(times_b), 2),
        "seed_results": [
            {
                "seed": r["seed"],
                "played": r["played"],
                "net_a": r["net_a"],
                "winner": r["winner"],
                "time_a": r["time_a"],
                "time_b": r["time_b"],
                "notices_a": r["notices_a"],
                "notices_b": r["notices_b"],
                "forfeit": r["forfeit"],
            }
            for r in runs_sorted
        ],
    }


def print_table(results: list[dict], baseline_map: dict[str, dict] | None) -> list[dict]:
    has_base = bool(baseline_map)
    regressions: list[dict] = []

    hdr = (
        f"{'Opponent':<20} | {'bb/100':>8} | {'SE':>6} | {'WinRate':>7} | {'W-L-D':>7} | "
        f"{'Not(A/B)':>8} | {'TimeA(avg/max)':>14}"
    )
    if has_base:
        hdr += f" | {'Base':>8} | {'Delta':>8} | {'z':>6} | {'Flag'}"
    print("=" * len(hdr))
    print(hdr)
    print("-" * len(hdr))

    for row in results:
        opp = row["opponent"]
        wld = f"{row['wins']}-{row['losses']}-{row['draws']}"
        not_s = f"{row['notices_a']}/{row['notices_b']}"
        t_s = f"{row['time_a_mean_s']:5.1f}s/{row['time_a_max_s']:5.1f}s"
        line = (
            f"{opp:<20} | {row['bb100']:+8.1f} | {row['se_bb100']:6.1f} | "
            f"{row['win_rate']*100:6.1f}% | {wld:>7} | {not_s:>8} | {t_s:>14}"
        )
        if has_base:
            base = baseline_map.get(opp)
            if base is not None:
                delta = row["bb100"] - base["bb100"]
                comb_se = math.sqrt(row["se_bb100"] ** 2 + base["se_bb100"] ** 2)
                z = delta / comb_se if comb_se > 1e-9 else 0.0
                flag = ""
                if delta < -2.0 * comb_se and comb_se > 0:
                    flag = "REGRESS >2SE"
                    regressions.append({"opponent": opp, "delta": delta, "comb_se": comb_se, "z": z})
                elif delta > 2.0 * comb_se and comb_se > 0:
                    flag = "IMPROVE >2SE"
                line += f" | {base['bb100']:+8.1f} | {delta:+8.1f} | {z:+6.2f} | {flag}"
            else:
                line += f" | {'N/A':>8} | {'N/A':>8} | {'N/A':>6} | NEW"
        print(line)

    print("=" * len(hdr))
    if has_base:
        if regressions:
            print(f"REGRESSION WARNING: {len(regressions)} opponent(s) regressed by > 2 SE:")
            for reg in regressions:
                print(
                    f"  - {reg['opponent']}: {reg['delta']:+.1f} bb/100 "
                    f"(comb SE {reg['comb_se']:.1f}, z = {reg['z']:+.2f})"
                )
        else:
            print("BASELINE COMPARISON: 0 regressions > 2 SE.")
    return regressions


def main() -> None:
    default_py = str(DEFAULT_PY311) if DEFAULT_PY311.is_file() else sys.executable
    p = argparse.ArgumentParser(description="Run full Zoo evaluation suite against a candidate bot.")
    p.add_argument("candidate", nargs="?", default="src/bot.py", help="Candidate bot .py or .zip (default: src/bot.py)")
    p.add_argument("--seeds", type=int, default=20, help="Number of seeds per opponent (>=20 recommended, default: 20)")
    p.add_argument("--base-seed", type=int, default=1001, help="First seed integer (default: 1001)")
    p.add_argument("--hands", type=int, default=400, help="Even hands per match (default: 400)")
    p.add_argument("--stage", type=int, choices=(1, 2), default=1, help="Engine stage (default: 1)")
    p.add_argument("--workers", type=int, default=8, help="Parallel match workers (default: 8)")
    p.add_argument("--bootstrap", type=int, default=2000, help="Bootstrap resamples for pair SE (default: 2000)")
    p.add_argument("--python", default=default_py, help="Python interpreter for engine & bots")
    p.add_argument("--enforce-time-limits", action="store_true", help="Enforce strict time bank / 5s limit during parallel runs")
    p.add_argument("--out", default=str(ZOO_DIR / "results.json"), help="Output JSON path")
    p.add_argument("--baseline", default=str(ZOO_DIR / "baseline.json"), help="Baseline JSON path to compare against")
    p.add_argument("--save-baseline", action="store_true", help="Also write results to --baseline")
    p.add_argument("--opponents", nargs="*", help="Optional substring filter for opponent names")
    args = p.parse_args()

    if args.hands <= 0 or args.hands % 2:
        sys.exit("--hands must be a positive even integer")

    selected = OPPONENTS
    if args.opponents:
        pats = [s.lower() for s in args.opponents]
        selected = [(n, path) for n, path in OPPONENTS if any(pat in n.lower() for pat in pats)]
        if not selected:
            sys.exit(f"No opponents matched filter: {args.opponents}")

    seeds = [args.base_seed + i for i in range(args.seeds)]
    temp_dirs: list[str] = []
    t_start = time.perf_counter()

    try:
        cand_path = resolve_candidate(args.candidate, temp_dirs)
        total_jobs = len(selected) * len(seeds)
        print(
            f"Running suite: candidate={args.candidate} | opponents={len(selected)} | "
            f"seeds={len(seeds)} ({seeds[0]}..{seeds[-1]}) | hands={args.hands} | "
            f"workers={args.workers} | time_limits={'ON' if args.enforce_time_limits else 'OFF'} | "
            f"python={args.python}",
            flush=True,
        )

        by_opp: dict[str, list[dict]] = {name: [] for name, _ in selected}
        done_count = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = [
                pool.submit(
                    run_single_match,
                    cand_path,
                    opp_name,
                    opp_path,
                    seed,
                    args.hands,
                    args.stage,
                    args.python,
                    args.enforce_time_limits,
                )
                for opp_name, opp_path in selected
                for seed in seeds
            ]
            for fut in as_completed(futs):
                res = fut.result()
                by_opp[res["opp_name"]].append(res)
                done_count += 1
                if done_count % 20 == 0 or done_count == total_jobs:
                    elapsed = time.perf_counter() - t_start
                    print(f"  Progress: {done_count}/{total_jobs} matches ({elapsed:.1f}s)", flush=True)

        results = [aggregate_opponent(opp_name, by_opp[opp_name], args.bootstrap) for opp_name, _ in selected]

        baseline_map: dict[str, dict] | None = None
        base_path = Path(args.baseline)
        if not args.save_baseline and base_path.is_file():
            base_data = json.loads(base_path.read_text(encoding="utf-8"))
            baseline_map = {r["opponent"]: r for r in base_data.get("results", [])}

        print()
        regressions = print_table(results, baseline_map)

        payload = {
            "candidate": args.candidate,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "python": args.python,
            "stage": args.stage,
            "hands_per_match": args.hands,
            "seeds": seeds,
            "bootstrap_iters": args.bootstrap,
            "enforce_time_limits": args.enforce_time_limits,
            "wallclock_s": round(time.perf_counter() - t_start, 2),
            "regressions_gt_2se": regressions,
            "results": results,
        }

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nSaved results JSON: {out_path}")

        if args.save_baseline:
            base_path.parent.mkdir(parents=True, exist_ok=True)
            base_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"Saved baseline JSON: {base_path}")
    finally:
        for td in temp_dirs:
            shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    main()
