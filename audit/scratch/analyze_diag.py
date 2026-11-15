"""Diagnostic analyzer for items 1-7 from audit/diag_logs/ JSONL files."""
from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(r"c:\VSC_Projects\PokerBots")
sys.path.insert(0, str(ROOT / "src"))
from evaluator import compare_hands  # noqa: E402

LOG_BASE = ROOT / "audit" / "diag_logs"

TRUE_PARAMS = {
    "opp_nit": "fold>4 (to_call<=4 call, >4 fold), agg=0.00, bet_val=N/A, vpip~1.00(limp), width=0% open (never raises)",
    "opp_tight_raiser": "fold_to_bet=0.00 postflop, agg=0.00 postflop, vpip>=0.50, width=15% (RAISE_PCT>=0.85, CALL_PCT>=0.50)",
    "zoo_eq_bot": "call eq>odds+0.03, raise eq>0.62 (66% pot), bluff=8% (opp_agg~raise_freq), discard=eq",
    "zoo_tag_bot": "open=top 28% (pct>=0.72), 3bet=top 12% (>=0.88), flop c-bet~70%, value eq>=0.62, call eq>odds+0.03",
    "zoo_trap_bot": "checks when free (trap eq>=0.68 -> check-raise 85% pot), call eq>odds+0.03, never opens preflop",
    "zoo_shove_bot_15": "preflop jams top 15% (pct>=0.85), folds/checks bottom 85% (postflop checks/calls if top 15%)",
    "zoo_shove_bot_30": "preflop jams top 30% (pct>=0.70), folds/checks bottom 70% (postflop checks/calls if top 30%)",
}


def load_tag(tag: str):
    hands = []
    snaps = defaultdict(list)
    tag_dir = LOG_BASE / tag
    if not tag_dir.is_dir():
        return hands, snaps
    for fp in sorted(tag_dir.glob("diag_*.jsonl")):
        with fp.open("r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("record") == "hand":
                    rec["_tag"] = tag
                    hands.append(rec)
                elif rec.get("record") == "opp_snapshot":
                    snaps[rec["hands_observed"]].append(rec)
    return hands, snaps


def item1_opp_model():
    print("\n" + "=" * 100)
    print("ITEM 1: OpponentModel Learned Values at Hands 50 / 100 / 200 / 400 vs True Code Parameters")
    print("=" * 100)
    tags = [
        "opp_nit", "opp_tight_raiser", "zoo_eq_bot", "zoo_tag_bot",
        "zoo_trap_bot", "zoo_shove_bot_15", "zoo_shove_bot_30",
    ]
    for tag in tags:
        _, snaps = load_tag(tag)
        print(f"\n--- {tag} | TRUE: {TRUE_PARAMS[tag]} ---")
        print(f"{'Hand':>5} | {'N':>3} | {'fold_to_bet':>11} | {'agg_freq':>9} | {'bet_val_rt':>10} | {'vpip':>7} | {'open_w%':>8} | {'w1%':>6} | {'w2%':>6} | {'style'}")
        for h in (50, 100, 200, 400):
            rows = snaps.get(h, [])
            if not rows:
                continue
            def avg(k):
                return statistics.mean(r[k] for r in rows)
            styles = defaultdict(int)
            for r in rows:
                styles[r["style"]] += 1
            top_style = ", ".join(f"{k}:{v}" for k, v in sorted(styles.items(), key=lambda kv: -kv[1])[:2])
            print(
                f"{h:>5} | {len(rows):>3} | {avg('fold_to_bet'):>11.3f} | {avg('agg_freq'):>9.3f} | "
                f"{avg('bet_value_rate'):>10.3f} | {avg('vpip'):>7.3f} | {avg('open_width'):>7.1f}% | "
                f"{avg('width_1'):>5.1f}% | {avg('width_2'):>5.1f}% | {top_style}"
            )


def item2_street_last_bettor(all_hands):
    print("\n" + "=" * 100)
    print("ITEM 2: Chips Won/Lost by (End Street x Last Bettor x Showdown/Fold)")
    print("=" * 100)
    buckets = defaultdict(lambda: [0, 0])  # [hands, net_chips]
    for h in all_hands:
        hist = h.get("history") or []
        end_st = hist[-1]["street"] if hist else "preflop"
        last_bettor = "none"
        for e in reversed(hist):
            if e.get("action") == "raise":
                last_bettor = e.get("actor")
                break
        res = h.get("result")
        key = (end_st, last_bettor, res)
        buckets[key][0] += 1
        buckets[key][1] += int(h["net"])

    total_h = len(all_hands)
    total_net = sum(v[1] for v in buckets.values())
    print(f"Pooled across {total_h:,} hands | Total Net: {total_net:+,d} chips ({total_net / (total_h * 2 / 100):+.1f} bb/100)")
    print(f"{'EndStreet':<10} | {'LastBettor':<10} | {'Result':<9} | {'Hands':>7} | {'NetChips':>11} | {'Avg BB/hd':>10}")
    print("-" * 72)
    order_st = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}
    for (st, lb, res), (n, net) in sorted(buckets.items(), key=lambda kv: (order_st.get(kv[0][0], 9), kv[0][1], kv[0][2])):
        print(f"{st:<10} | {lb:<10} | {res:<9} | {n:>7,} | {net:>+11,d} | {net / (2.0 * n):>+10.3f}")


def item3_decision_ev(all_hands):
    print("\n" + "=" * 100)
    print("ITEM 3: EV per Decision Class, Split by Seat (BB/decision from decision point & Full-Hand Net)")
    print("=" * 100)
    # Map detailed decision_class -> requested categories (and also show sub-classes)
    stats = defaultdict(list)  # (class, seat) -> list of (inc_ev_bb, full_net_bb)
    for h in all_hands:
        net = int(h["net"])
        for d in h.get("decisions", []):
            dc = d.get("decision_class") or "unknown"
            seat = d.get("seat") or h.get("seat")
            comm = int(d.get("my_committed", 0))
            inc_bb = (net + comm) / 2.0
            full_bb = net / 2.0
            # Map postflop check_back / trap_check / etc.
            if dc in ("trap_check_back", "check_back"):
                stats[(f"{d['street']}:check_back", seat)].append((inc_bb, full_bb))
                stats[("postflop:check_back", seat)].append((inc_bb, full_bb))
            elif dc in ("trap_check_oop", "oop_check"):
                stats[("postflop:oop_check", seat)].append((inc_bb, full_bb))
            elif dc in ("value_bet", "bluff", "call", "fold", "check_raise", "raise_vs_bet"):
                stats[(f"postflop:{dc}", seat)].append((inc_bb, full_bb))
            else:
                stats[(dc, seat)].append((inc_bb, full_bb))

    print(f"{'DecisionClass':<24} | {'Seat':<10} | {'N':>7} | {'IncEV(BB)':>10} | {'SE':>6} | {'HandNet(BB)':>11}")
    print("-" * 80)
    for (dc, seat), vals in sorted(stats.items()):
        n = len(vals)
        inc_list = [v[0] for v in vals]
        full_list = [v[1] for v in vals]
        inc_m = statistics.mean(inc_list)
        inc_se = (statistics.stdev(inc_list) / math.sqrt(n)) if n > 1 else 0.0
        full_m = statistics.mean(full_list)
        print(f"{dc:<24} | {seat:<10} | {n:>7,} | {inc_m:>+10.3f} | {inc_se:>6.3f} | {full_m:>+11.3f}")


def item4_calibration(all_hands):
    print("\n" + "=" * 100)
    print("ITEM 4: Equity Calibration (Turn/River, and Separately Facing Opponent Bet)")
    print("=" * 100)

    def report_cal(label: str, rows: list[tuple[float, float]]):
        if not rows:
            print(f"\n--- {label}: 0 samples ---")
            return
        mean_p = statistics.mean(p for p, _ in rows)
        mean_y = statistics.mean(y for _, y in rows)
        bias = mean_p - mean_y
        brier = statistics.mean((p - y) ** 2 for p, y in rows)
        print(f"\n--- {label} (N={len(rows):,}) | Overall Pred={mean_p:.4f} Realised={mean_y:.4f} Bias={bias:+.4f} Brier={brier:.4f} ---")
        print(f"{'Bucket':<10} | {'N':>6} | {'PredEq':>8} | {'Realised':>8} | {'Bias(P-R)':>10}")
        print("-" * 52)
        for b in range(10):
            lo, hi = b * 0.1, (b + 1) * 0.1
            sub = [(p, y) for p, y in rows if (lo <= p < hi or (b == 9 and p == 1.0))]
            if not sub:
                continue
            mp = statistics.mean(p for p, _ in sub)
            my = statistics.mean(y for _, y in sub)
            print(f"[{lo:.1f},{hi:.1f}{']' if b==9 else ')'}  | {len(sub):>6,} | {mp:>8.4f} | {my:>8.4f} | {mp - my:>+10.4f}")

    all_tr = []
    turn_only = []
    river_only = []
    facing_bet_tr = []
    facing_bet_turn = []
    facing_bet_river = []

    for h in all_hands:
        if h.get("result") != "showdown":
            continue
        my_hc = h.get("my_hole_cards")
        opp_hc = h.get("opp_hole_cards")
        board = h.get("board")
        if not my_hc or not opp_hc or not board or len(board) < 5:
            continue
        cmp = compare_hands(my_hc, opp_hc, board)
        realised = 1.0 if cmp > 0 else (0.5 if cmp == 0 else 0.0)
        for d in h.get("decisions", []):
            st = d.get("street")
            eq_v = d.get("equity")
            if st not in ("turn", "river") or eq_v is None:
                continue
            all_tr.append((eq_v, realised))
            if st == "turn":
                turn_only.append((eq_v, realised))
            else:
                river_only.append((eq_v, realised))
            if int(d.get("to_call", 0)) > 0:
                facing_bet_tr.append((eq_v, realised))
                if st == "turn":
                    facing_bet_turn.append((eq_v, realised))
                else:
                    facing_bet_river.append((eq_v, realised))

    report_cal("Turn + River (All Decisions Reaching Showdown)", all_tr)
    report_cal("Turn Only (Reaching Showdown)", turn_only)
    report_cal("River Only (Reaching Showdown)", river_only)
    report_cal("Turn + River Facing Opponent Bet (to_call > 0)", facing_bet_tr)
    report_cal("Turn Facing Opponent Bet (to_call > 0)", facing_bet_turn)
    report_cal("River Facing Opponent Bet (to_call > 0)", facing_bet_river)


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = sum((x - mx) ** 2 for x in xs)
    den_y = sum((y - my) ** 2 for y in ys)
    if den_x <= 0 or den_y <= 0:
        return 0.0
    return num / math.sqrt(den_x * den_y)


def item5_sizing(all_hands):
    print("\n" + "=" * 100)
    print("ITEM 5: Sizing Leak (Bet Size % of Pot BEFORE Bet vs Realised Showdown Equity)")
    print("=" * 100)

    open_bets = []   # (frac, realised_sd_or_None, pred_eq, net_bb)
    all_bets = []    # (frac_before_pot, realised_sd_or_None, pred_eq, net_bb)

    for h in all_hands:
        net_bb = int(h["net"]) / 2.0
        realised = None
        if h.get("result") == "showdown" and h.get("my_hole_cards") and h.get("opp_hole_cards") and len(h.get("board") or []) >= 5:
            cmp = compare_hands(h["my_hole_cards"], h["opp_hole_cards"], h["board"])
            realised = 1.0 if cmp > 0 else (0.5 if cmp == 0 else 0.0)
        for d in h.get("decisions", []):
            if d.get("street") == "preflop" or d.get("action") != "raise":
                continue
            pf = d.get("pot_frac_before")
            if pf is None:
                continue
            eq_v = d.get("equity")
            all_bets.append((pf, realised, eq_v, net_bb))
            if int(d.get("to_call", 0)) == 0:
                open_bets.append((pf, realised, eq_v, net_bb))

    def show_group(label: str, items: list[tuple[float, float | None, float | None, float]]):
        sd_items = [(pf, r) for pf, r, _, _ in items if r is not None]
        eq_items = [(pf, e) for pf, _, e, _ in items if e is not None]
        r_sd = pearson([x[0] for x in sd_items], [x[1] for x in sd_items])
        r_eq = pearson([x[0] for x in eq_items], [x[1] for x in eq_items])
        print(f"\n--- {label} (N={len(items):,}, SD={len(sd_items):,}) ---")
        print(f"  Pearson corr(pot_frac_before, realised_sd_win) = {r_sd:+.4f}")
        print(f"  Pearson corr(pot_frac_before, pred_equity)     = {r_eq:+.4f}")
        buckets = [
            ("<30%", 0.0, 0.30),
            ("30-45%", 0.30, 0.45),
            ("45-60%", 0.45, 0.60),
            ("60-80%", 0.60, 0.80),
            ("80-100%", 0.80, 1.00),
            ("100-200%", 1.00, 2.00),
            (">=200%", 2.00, 1e9),
        ]
        print(f"  {'SizeBucket':<10} | {'Count':>7} | {'Share':>6} | {'MeanPredEq':>10} | {'RealisedSD':>10} | {'MeanHandBB':>10}")
        print("  " + "-" * 68)
        for name, lo, hi in buckets:
            sub = [x for x in items if lo <= x[0] < hi]
            if not sub:
                continue
            sd_sub = [x[1] for x in sub if x[1] is not None]
            eq_sub = [x[2] for x in sub if x[2] is not None]
            print(
                f"  {name:<10} | {len(sub):>7,} | {100*len(sub)/len(items):5.1f}% | "
                f"{(f'{statistics.mean(eq_sub):.3f}' if eq_sub else 'N/A'):>10} | "
                f"{(f'{statistics.mean(sd_sub):.3f}' if sd_sub else 'N/A'):>10} | "
                f"{statistics.mean(x[3] for x in sub):>+10.2f}"
            )

    show_group("Postflop Open Bets (to_call == 0; pot == pot BEFORE bet)", open_bets)
    show_group("All Postflop Bets & Raises (bet_added / req.pot)", all_bets)


def item7_top_losses(tag: str, limit: int = 20):
    print("\n" + "=" * 100)
    print(f"ITEM 7: Top {limit} Biggest Pots Lost vs {tag}")
    print("=" * 100)
    hands, _ = load_tag(tag)
    losses = sorted([h for h in hands if int(h["net"]) < 0], key=lambda h: (int(h["net"]), int(h["hand_id"])))[:limit]
    for rank, h in enumerate(losses, 1):
        acts = []
        cur_st = None
        for e in h.get("history") or []:
            st = e.get("street")
            if st != cur_st:
                acts.append(f"{st}:")
                cur_st = st
            a = e.get("action")[0] if e.get("action") != "check" else "x"
            amt = "" if e.get("amount") is None else str(e["amount"])
            who = "M" if e.get("actor") == "me" else "O"
            acts.append(f"{who}{a}{amt}")
        dec_str = " | ".join(
            f"{d['street']}:{d['decision_class']}(eq={d['equity']:.2f})" if d.get("equity") is not None
            else f"{d['street']}:{d['decision_class']}(pct={d['pct']:.2f})" if d.get("pct") is not None
            else f"{d['street']}:{d['decision_class']}"
            for d in h.get("decisions", [])
        )
        print(
            f"#{rank:<2} net={h['net']:+4d} seat={h['seat']:<9} dealt={h.get('dealt_hole')} "
            f"kept={h.get('my_hole_cards')} opp={h.get('opp_hole_cards')} disc={h.get('opp_discard')} "
            f"board={h.get('board')} ({h.get('result')})"
        )
        print(f"    Line: {' '.join(acts)}")
        print(f"    Decs: {dec_str}")


def main():
    tags = [p.name for p in sorted(LOG_BASE.iterdir()) if p.is_dir()]
    all_hands = []
    for t in tags:
        hs, _ = load_tag(t)
        all_hands.extend(hs)
    print(f"Loaded {len(all_hands):,} total hands across {len(tags)} opponents: {tags}")

    item1_opp_model()
    item2_street_last_bettor(all_hands)
    item3_decision_ev(all_hands)
    item4_calibration(all_hands)
    item5_sizing(all_hands)
    item7_top_losses("zoo_eq_bot", 20)
    item7_top_losses("zoo_tag_bot", 20)


if __name__ == "__main__":
    main()
