#!/usr/bin/env python3
"""A/B benchmark of bot variants against opponents, on the SAME seeds.

  python tools/ab_sweep.py single,fixed40,adapt always_raise,random_raiser 30 400

Prints net chips per hand (mean +- standard error over seeds) for each variant, and for
every variant after the first the PAIRED difference vs the first (same deals), which is
what tells you whether a change really helped. Notices/forfeits are shown in brackets.
"""
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def play(bot, opp, seed, hands):
    out = subprocess.run([sys.executable, str(ROOT / "engine.py"), bot, opp, "--hands", str(hands),
                          "--seed", str(seed), "--log-dir", ""], capture_output=True, text=True).stdout
    m = re.search(r"^\s*A\s+.*?net\s+([+-]?\d+).*?notices\s+(\d+)", out, re.M)
    forfeit = "forfeited" in out or not m
    return (int(m.group(1)), int(m.group(2)), forfeit) if m else (0, 0, True)


def mean_se(xs):
    n = len(xs)
    mu = sum(xs) / n
    var = sum((x - mu) ** 2 for x in xs) / max(1, n - 1)
    return mu, math.sqrt(var / n)


def main():
    variants = sys.argv[1].split(",")
    opps = sys.argv[2].split(",")
    n = int(sys.argv[3])
    hands = int(sys.argv[4]) if len(sys.argv) > 4 else 400
    print(f"net chips per hand, {n} matches x {hands} hands per cell (mean +- SE); [notices/forfeits]")
    for opp in opps:
        res = {}
        flags = {}
        for v in variants:
            nets, notes, ff = [], 0, 0
            for seed in range(1, n + 1):
                net, nt, f = play(f"variants/{v}/bot.py", f"opponents/{opp}.py", 1000 + seed, hands)
                nets.append(net / hands)
                notes += nt
                ff += f
            res[v], flags[v] = nets, (notes, ff)
        print(f"\nvs {opp}")
        base = res[variants[0]]
        for v in variants:
            mu, se = mean_se(res[v])
            line = f"  {v:<10} {mu:+.3f} +- {se:.3f}  [{flags[v][0]}/{flags[v][1]}]"
            if v != variants[0]:
                dmu, dse = mean_se([a - b for a, b in zip(res[v], base)])
                verdict = "better" if dmu - 2 * dse > 0 else ("worse" if dmu + 2 * dse < 0 else "no clear difference")
                line += f"   vs {variants[0]}: {dmu:+.3f} +- {dse:.3f} ({verdict})"
            print(line)
        sys.stdout.flush()


main()
