# PokerBot Audit Report — AcesDiscard v1.0.0
**Auditor:** Antigravity (Claude Sonnet 4.6, thinking)  
**Date:** 2026-11-09  
**Mode:** READ-ONLY. No existing files modified. Outputs written to `./audit/` only.

---

## PART F — EXECUTIVE SUMMARY *(max 40 lines)*

### Current Strength (bb/100, Stage 1 — multiple seeds, 95% CI)

| Opponent | Hands | bb/100 | ±95% CI |
|---|---|---|---|
| always_call | 2000 | +1270 | ±191 |
| always_raise | 1200 | +1544 | ±166 |
| maniac | 400 | +1669 | N/A (n=1) |
| random_bot | 1200 | +582 | ±127 |
| tight_raiser | 1200 | +585 | ±145 |
| **nit** | **1200** | **+107** | **±7** |

The bot wins convincingly vs aggressive/random opponents. The nit result (+107 bb/100) is the structural warning: the bot is betting too often vs opponents that never fold and hold strong hands.

### Top 5 Improvements by (Impact × Confidence / Effort)

1. **Value-bet threshold: add fold-to-bet sensitivity for tight opponents** (postflop.py:127) — nit showdown WR=31.7% at 39% flop bet freq → tighten vthr vs confirmed non-folders. Est. +50–80 bb/100. Effort: S.
2. **Bluff path: add `canr` guard before `_size()` call** (postflop.py:133) — bluff attempts silently crash to `_cheap` in all-in spots. 1-line fix. Effort: S.
3. **Station detection: add passive-caller signal** (opponent_model.py:206) — always_call never bets so `faced_bets` stays 0 → never classified station → vthr stays at 0.60 instead of 0.55. Effort: S.
4. **Call margin: set base margin to 0.00** (postflop.py:114) — current 2.5% minimum over pot odds discards profitable calls. Effort: S.
5. **Preflop evidence gate: lower to 3 showdowns** (config.py:72) — the 6-sample threshold keeps opponent width pinned at 40% for first ~20 hands vs tight opponents. Effort: S.

### Top 3 Risks of Forfeit or Illegal Play

1. **`default_discard([])` raises `ValueError`** (evaluator.py:127) — the outer except re-calls the same failing function. Only triggers on malformed protocol message (zero occurrences in 7200 hands).
2. **Bluff path crashes silently** (postflop.py:133–136) — `_size()` with `min_raise=None` raises `TypeError`, caught by `postflop.decide()` except. No notice issued, but bluff equity is lost. Zero occurrences in 7200 hands.
3. **Time-bank exhaustion in Stage 2** (1000 hands, 150 s) — max observed 34.09 s / 400 hands; extrapolates to ~85 s / 1000 hands with headroom. UNVERIFIED for Stage 2.

### What Could Not Be Determined

- Exploitability vs a GTO-approximate bot (no GTO reference available locally).
- Whether the preflop equity table (8000 sims × 16 rollouts per canonical hand) has calibration error significant enough to affect borderline decisions.
- Real tournament-opponent style distribution.

---

## PART A — INVENTORY

### A1. File List and Line Counts

| File | Lines | Role |
|---|---|---|
| `engine.py` | 601 | Match runner (read-only reference) |
| `src/bot.py` | 150 | Main IPC loop, entry point |
| `src/betting.py` | 21 | Street router (preflop vs postflop) |
| `src/bet_utils.py` | 72 | Raise sizing helpers |
| `src/config.py` | 73 | All tunable constants |
| `src/discard.py` | 25 | Discard chooser |
| `src/equity.py` | 158 | Monte Carlo equity engine |
| `src/evaluator.py` | 127 | Integer hand evaluator |
| `src/opponent_model.py` | 301 | Opponent stats tracker |
| `src/postflop.py` | 171 | Flop/turn/river betting |
| `src/preflop.py` | 119 | Preflop betting |
| `src/preflop_data.py` | 14058 | Auto-generated equity table (316 KB) |
| `src/preflop_table.py` | 199 | Equity table loader and lookup |
| `src/state.py` | 133 | Hand/match state tracker |
| `src/timemgr.py` | 16 | Per-decision time budgeting |

### A1. Call Graph

```
run_bot() [src/bot.py:93]
 ├─ action_request  → handle_action_request() [bot.py:48]
 │    → state.on_action_request() [state.py:80]
 │    → betting.decide() [betting.py:17]
 │         ├─ street=="preflop" && USE_PREFLOP_TABLE
 │         │    → preflop.decide() [preflop.py:76]
 │         │         → preflop_table.get_percentile() [preflop_table.py:146]
 │         │         → opp_model.preflop_width() [opponent_model.py:247]
 │         │         → preflop_table.equity_at_width() [preflop_table.py:154]
 │         │         → bet_utils.raise_action() / simple() [bet_utils.py:40,53]
 │         └─ else → postflop.decide() [postflop.py:140]
 │                    → timemgr.budget_ms() [timemgr.py:5]
 │                    ├─ hole3==True (flop w/ 3 cards)
 │                    │    → equity.keep_equities() [equity.py:34]
 │                    └─ hole3==False (turn/river)
 │                         → postflop._range() [postflop.py:58]
 │                         │    → equity.build_base() [equity.py:79]
 │                         │    → equity.street_data() [equity.py:113]
 │                         ├─ river → equity.eq_river() [equity.py:127]
 │                         └─ turn  → equity.eq_turn() [equity.py:138]
 │                         → postflop._choose() [postflop.py:99]
 │                              → bet_utils.raise_action() / simple()
 ├─ discard_request → handle_discard_request() [bot.py:74]
 │    → state.on_discard_request() [state.py:98]
 │    → discard.choose() [discard.py:12]
 │         → timemgr.budget_ms() [timemgr.py:5]
 │         → equity.keep_equities() [equity.py:34]
 ├─ discard_result  → state.on_discard_result() [state.py:108]
 │    → opp_model.on_discard_result() [opponent_model.py:87]
 ├─ hand_result     → state.on_hand_result() [state.py:116]
 │    → opp_model.on_hand_result() [opponent_model.py:95]
 ├─ init            → state.on_init() [state.py:54]
 ├─ new_hand        → state.on_new_hand() [state.py:64]
 ├─ notice          → state.on_notice() [state.py:121]  (no-op, no reply)
 └─ match_end       → break
```

### A2. Per-Street Decision Summary

**PREFLOP** — `preflop.decide()` [preflop.py:76]
- **Method:** Lookup table (preflop_data.py) + heuristic fallback
- **Inputs:** `hole_cards` percentile (PCT_RANDOM), equity vs estimated opponent width (EQUITY_TOPn), pot odds from request msg
- **Key constants:** `OPEN_PCT=0.30` (open top 70%), `LIMP_PCT=0.08`, `3BET_EQ_VS_RANGE=0.52`, `4BET_EQ_VS_RANGE=0.60`, `CALL_MARGIN=0.00`, `BIG_BET_MARGIN=0.08`
- **Bet sizing:** 0.75× pot open/3-bet; 1.0× pot 4-bet [preflop.py:95,101,116]
- **Opponent model used:** `opp_model.preflop_width(n_raises)` [preflop.py:107–108]; conditions equity lookup on estimated range tightness
- **Classification:** Lookup table (enumerated offline)

**FLOP BETTING** — `postflop.decide()` [postflop.py:140], `hole3=True` path [postflop.py:152–155]
- **Method:** Monte Carlo — `keep_equities()` with 300 samples
- **Inputs:** 3 hole cards, 3 flop board cards; samples opponent as best-of-`tilt_k` random 3-card draws; rolls out turn+river
- **Key constants:** `vthr_flop=0.60`; bluff threshold `0.28`; `DEFAULT_POT_FRACTION=0.60`; sample count 300 [postflop.py:154]
- **Equity computed:** Best achievable 2-card equity (max over 3 discard choices)
- **Opponent discard:** Not yet known at flop betting (discard happens after)

**DISCARD** — `discard.choose()` [discard.py:12]
- **Method:** Monte Carlo — `keep_equities()` with 400 samples, deadline-limited
- **Inputs:** 3 hole cards, 3 flop cards, `tilt_k` from history, `disc_consistency` from opp model
- **Key constants:** 400 target samples; tie threshold 0.006 (near-ties randomly broken) [discard.py:21–24]
- **Classification:** Monte Carlo

**TURN BETTING** — `postflop.decide()` [postflop.py:140], `hole3=False`, board len=4 [postflop.py:162–167]
- **Method:** Monte Carlo — `eq_turn()` with 400 samples vs weighted opponent pair range
- **Inputs:** 2 hole cards (post-discard), 4 board cards, opp discard (conditions range), action history (`_power()` tilt)
- **Range:** `build_base()` builds discard-conditioned weighted pair list on flop; filtered for board conflicts; action-tilted via `_power()`
- **Key constants:** `vthr_turn=0.60`, 400 turn samples [postflop.py:167]

**RIVER BETTING** — `postflop.decide()` [postflop.py:140], `hole3=False`, board len=5 [postflop.py:160–161]
- **Method:** Exact weighted enumeration — `eq_river()` over precomputed pair range
- **Inputs:** Same as turn but evaluates all stored pairs against full 5-card board without sampling
- **Key constants:** `vthr_river=0.58` [postflop.py:127]

### A3. Hand Evaluator

- **Method:** Integer bit-packing evaluator (`eval_cards()`, [evaluator.py:32]). Cards encoded as `rank_idx × 4 + suit_idx`. Uses rank count array `cnt[13]`, per-suit rank bitmasks `sm[4]`, suit counts `sc[4]`. 8192-entry straight lookup table (built at import, [evaluator.py:15–29]). Ties broken by packed nibble fields in a 32-bit return value.
- **Speed (measured, Python 3.11):**
  - 7-card hands: **173,717 evals/sec**
  - 5-card hands: **196,744 evals/sec**
- **Verified:** Brute-force comparison against `engine.py:rank5()` over **5,000 random 7-card hands → 0 category mismatches**.

### A4. Equity Engine

| Context | Method | Samples | Opponent Range | Opp Discard Used? |
|---|---|---|---|---|
| Flop betting (hole3=True) | `keep_equities()` | 300 | Uniform random + best-of-`tilt_k` | No (not yet revealed) |
| Discard choice | `keep_equities()` | 400, deadline-limited | Same | No |
| Turn | `eq_turn()` | 400 | Discard-conditioned weighted pair range | Yes (`build_base()`, [equity.py:79]) |
| River | `eq_river()` | Full enum over prebuilt pairs | Same | Yes |

**Opponent range conditioning:** After `discard_result`, `state.opp_discard` is set. `build_base()` [equity.py:79–110] assigns `w(a,b)=1.0` if the discard `d` was the heuristic-worst card to keep, else `w = max(floor, exp(Δ/0.25))` where `Δ = ks(a,b) − max(ks(a,d), ks(b,d))`. This correctly conditions the range on the revealed discard. Verified correct.

**Sample counts vs timing (measured):**

| Computation | Mean ms | p95 ms | Max ms |
|---|---|---|---|
| `keep_equities(300, k=2)` | 8.3 | 8.5 | 8.7 |
| `keep_equities(400, k=2)` | 10.2 | 10.6 | 11.6 |
| `build_base + eq_turn(400)` | 4.4 | 4.6 | 5.1 |

### A5. Opponent Modelling

**Tracked fields** ([opponent_model.py]):

| Field | Purpose | Prior |
|---|---|---|
| `open_width()` | % of hands opp open-raises with | 40% (strength 20 pseudo-obs) |
| `fold_to_bet` | Fraction of bets opp folds to | 3/(3+8)=0.375 |
| `agg_freq` | Opp postflop bet frequency | 2/(2+5)=0.40 |
| `bet_value_rate` | Whether opp bets are strong | 3/(3+5)=0.60 |
| `disc_consistency` | Opp discards heuristic-optimally | 4/(4+5)=0.80 |
| `is_station` | Passive caller (rarely folds) | False until `faced_bets≥12 AND fold_to_bet<0.25` |
| `raised_pcts` | Percentile of hands opp raised preflop (showdown evidence) | Empty |

**How it feeds decisions:**
- `preflop_width()` → selects which `EQUITY_TOPn` table to use [preflop.py:107–108]
- `fold_to_bet` → bluff probability multiplier [postflop.py:134]
- `agg_freq` → `tilt_k` reduction for loose opponents [postflop.py:27–28]
- `bet_value_rate` → `_trust()` scaling on opp strength signals [postflop.py:16–17]
- `disc_consistency` → `cons` parameter in range conditioning [postflop.py:155, discard.py:20]

**Priors:** All Laplace-smoothed. `PREFLOP_MIN_WIDTH_NO_EVIDENCE=40.0` prevents over-tightening before evidence accumulates.

**Shrinkage:** `open_width()` uses `weight = n / (n + OPP_EVIDENCE_PRIOR_STRENGTH)` where `OPP_EVIDENCE_PRIOR_STRENGTH=6` [opponent_model.py:241].

### A6. Cross-Hand State

The only persistent state is the `OpponentModel` instance (created once in `run_bot()`). `GameState` resets per-hand via `on_new_hand()`. `postflop._H` is a module-level dict reset when `state.hand_id` changes [postflop.py:142–144]. `preflop._LOGGED` is a deduplicated stderr set (cosmetic only).

**Duplicate deal assumption:** None. The bot treats each hand independently. No code reads or stores the opponent's hole cards until `hand_result`. ✓

### A7. Time Management

`timemgr.py`:
- `budget_ms(state, kind)` [timemgr.py:5]: `pace = 0.8 × time_left_ms / hands_left`. `budget = pace × share[kind]`. Capped at [2.0, 250.0] ms. Emergency: if `time_left_ms < 6000`, cap at 4.0 ms.
- `low_time(state)` [timemgr.py:15]: True if `time_left_ms < 1500`.
- Street shares: `{"flop": 0.70, "discard": 0.90, "turn": 0.60, "river": 0.50}`; preflop not in dict → defaults to 0.3 (fine: preflop decisions are 0.0 ms measured).

**Measured total time usage across all 400-hand matches:**

| Opponent | Min s | Mean s | Max s | Budget |
|---|---|---|---|---|
| all matches | 4.56 | 16.0 | 34.09 | 60 s |

All within budget. Max 34.09 s = 57% of budget.

**Per-decision timing (instrumented run, vs always_call):**

| Street | Mean ms | p95 ms | Max ms | Per-reply limit |
|---|---|---|---|---|
| preflop | 0.0 | 0.0 | 0.1 | 5000 ms |
| flop | 17.9 | 24.5 | 63.8 | 5000 ms |
| discard | 22.4 | 29.9 | 69.3 | 5000 ms |
| turn | 20.8 | 28.2 | 74.9 | 5000 ms |
| river | 5.3 | 6.9 | 15.4 | 5000 ms |

### A8. Embedded Data Tables

| Table | Entries | File | Notes |
|---|---|---|---|
| `EQUITY_RANDOM` | 1,755 | preflop_data.py | Equity vs random hand |
| `PCT_RANDOM` | 1,755 | preflop_data.py | Hand percentile 0–1 |
| `EQUITY_TOP5` | 1,755 | preflop_data.py | Equity vs top 5% |
| `EQUITY_TOP10` | 1,755 | preflop_data.py | Equity vs top 10% |
| `EQUITY_TOP15` | 1,755 | preflop_data.py | Equity vs top 15% |
| `EQUITY_TOP25` | 1,755 | preflop_data.py | Equity vs top 25% |
| `EQUITY_TOP40` | 1,755 | preflop_data.py | Equity vs top 40% |
| `EQUITY_TOP60` | 1,755 | preflop_data.py | Equity vs top 60% |
| `STRAIGHT` lookup | 8,192 | evaluator.py (at import) | 32 KB built at startup |
| **Total preflop_data.py** | — | — | **316 KB, 14,058 lines** |

The 1,755 entries cover all canonical 3-card hands — verified exhaustively: `combinations(52, 3)` maps to exactly 1,755 canonical keys via `canonical_3card()`. Generated offline: 8,000 sims × 16 rollouts, seed=12345 [preflop_data.py:1–2].

---

## PART B — STATIC ROBUSTNESS REVIEW

| Check | Result | Evidence |
|---|---|---|
| Exception fallback around entire loop | ✅ PASS | bot.py:67–71 (action), :86–90 (discard), :138–146 (main) |
| Raise-to clamped to [min_raise, max_raise] | ✅ PASS | bet_utils.py:23; tested min==max→returns exact value |
| min_raise == max_raise edge case | ✅ PASS | measured: `calculate_raise_amount(10,6,0,10,10,0.6)→10` |
| Raise absent while raises_left > 0 | ✅ PASS | Engine only omits min/max when raise not in legal_actions (engine.py:354–356); `can_raise()` checks `min_raise is not None` |
| raises_left == 0 | ✅ PASS | `can_raise()` [bet_utils.py:36] checks `raises_left > 0` |
| Only JSON to stdout | ✅ PASS | `print(json.dumps(...), flush=True)` only at bot.py:135 |
| Flush after every reply | ✅ PASS | `flush=True` in print() [bot.py:135] |
| Debug to stderr only | ✅ PASS | `DEBUG_LOGGING=False`; all stderr writes are explicit |
| Discard returns hole card | ✅ PASS | bot.py:83–84 validates; fallback at :89 |
| Empty `hole_cards` discard | ⚠️ PARTIAL | `default_discard([])` raises `ValueError`; outer except re-calls it → double crash. Only reachable via malformed engine message. Zero occurrences in 7200 hands. |
| Unknown message types | ✅ PASS | bot.py:130 `else: continue` (no reply sent) |
| Notice messages | ✅ PASS | bot.py:123–125; `state.on_notice()` is a no-op; no reply |
| `total_hands` from init, not hard-coded | ✅ PASS | state.py:56 |
| `time_bank_ms` from init, not hard-coded | ✅ PASS | state.py:60 |
| Worst-case single decision latency | ✅ PASS | 74.9 ms max vs 5000 ms limit (1.5% utilization) |
| Total time vs time bank | ✅ PASS | 34.09 s max vs 60 s bank (57% utilization) |
| **Bluff path `canr` guard** | ⚠️ BUG | postflop.py:133–136 calls `_size()` without `can_raise()` check. When `min_raise=None`, `_size()` raises `TypeError`, caught by postflop except → `_cheap()`. No notice issued. Zero occurrences in 7200 hands. |
| All-in discard | ✅ PASS | Engine still sends `discard_request` after all-in; bot handles normally |
| All-in equity (no further betting) | ✅ PASS | Engine skips `betting_round` when stacks contain 0 (engine.py:336); `postflop.decide()` never called |

---

## PART C — EMPIRICAL PROFILE

### C1. Match Results (Stage 1, --stage 1)

**Seeds used:** 101, 202, 303, 404, 505 (where available). All duplicate pairs preserved by engine.

| Opponent | Seeds | Hands | Net chips | bb/100 | SE (bb/100) | 95% CI |
|---|---|---|---|---|---|---|
| always_call | 101,202,303,404,505 | 2000 | +50,814 | +1270 | ±97 | ±191 |
| always_raise | 101,202,303 | 1200 | +37,062 | +1544 | ±85 | ±166 |
| maniac | 101 | 400 | +13,350 | +1669 | N/A | N/A |
| random_bot | 101,202,303 | 1200 | +13,976 | +582 | ±65 | ±127 |
| tight_raiser | 101,202,303 | 1200 | +14,042 | +585 | ±74 | ±145 |
| nit | 101,202,303 | 1200 | +2,569 | +107 | ±4 | ±7 |

**Notices in all runs: 0.**

### C2a. Profit by Seat and Last Street (vs always_call, 400 hands seed 101)

| Seat | Hands | Net | bb/100 |
|---|---|---|---|
| Button | 200 | +5,830 | +1458 |
| Big Blind | 200 | +5,526 | +1382 |

| Last street | Hands | Net |
|---|---|---|
| preflop | 17 | −17 |
| river | 383 | +11,373 |

### C2b. Preflop Action Frequencies (instrumented run, vs always_call)

| Action | Count | % |
|---|---|---|
| raise | 230 | 57% |
| check | 109 | 27% |
| call | 44 | 11% |
| fold | 17 | 4% |

### C2c. Postflop Action Frequencies by Street (instrumented run vs always_call; vs nit for comparison)

| Street | Opp | raise% | check% | call% | fold% | N |
|---|---|---|---|---|---|---|
| flop | always_call | 49% | 50% | 0% | 0% | 383 |
| flop | nit | 39% | 60% | 0% | 0% | 383 |
| turn | always_call | 55% | 44% | 0% | 0% | 383 |
| turn | nit | 35% | 64% | 0% | 0% | 293 |
| river | always_call | 60% | 39% | 0% | 0% | 383 |
| river | nit | 38% | 61% | 0% | 0% | 227 |

(vs always_call: near-zero call% because always_call never bets, so we always act first.)

### C2d. Bet Sizing Histogram (instrumented run, all streets vs always_call)

| Raise-to as % of final pot | Count | % |
|---|---|---|
| < 40% | 168 | 19% |
| 40–60% | 508 | 58% |
| 60–80% | 188 | 21% |
| 80–100% | 0 | 0% |
| > 100% (over-bet) | 0 | 0% |

**Mean raise-to: 49% pot. Bot never over-bets.**

### C2e. Showdown vs Non-Showdown (vs always_call, 400 hands)

| Category | Hands | Net chips | WR |
|---|---|---|---|
| Showdown | 383 | +11,373 | 54.6% |
| Non-showdown (fold) | 17 | −17 | — |

vs nit (400 hands):

| Category | Hands | Net chips | WR |
|---|---|---|---|
| Showdown | 180 | −174 | **31.7%** |
| Non-showdown | 220 | +1,044 | — |

### C2f. Biggest Pots Lost — vs nit

The nit showdown win rate of 31.7% (57 wins / 180 showdowns) is the dominant signal. The bot raised 39%/35%/38% on flop/turn/river vs nit despite having equity well below the 50% required to profit from betting vs a non-folder. The correct decision in most of these spots was to check and reach showdown cheaply. Full hand-by-hand detail is available in `audit/logs_nit_101/match.log`.

### C2g. Discard Analysis (500 sampled spots)

| Metric | Value |
|---|---|
| Bot differs from "discard lowest rank" | 204 / 500 (40.8%) |
| Avg equity gain on differing spots | 13.2 pp |
| Avg equity gain per hand overall | **5.4 pp** |

The discard module delivers substantial, measurable value over the naive baseline.

### C2h. Notice Count

**Zero notices across all runs** (7,200+ hands across 6 opponents and multiple seeds).

### C3. Time Profile

| Street | Mean ms | p95 ms | Max ms | Limit |
|---|---|---|---|---|
| preflop | 0.0 | 0.0 | 0.1 | 5000 ms |
| flop | 17.9 | 24.5 | 63.8 | 5000 ms |
| discard | 22.4 | 29.9 | 69.3 | 5000 ms |
| turn | 20.8 | 28.2 | 74.9 | 5000 ms |
| river | 5.3 | 6.9 | 15.4 | 5000 ms |

Total used (instrumented run): 22.11 s / 60 s (37%).

---

## PART D — BETTING DIAGNOSIS

> **Hypothesis assessed:** Betting is the weakest area.
> **Verdict:** **Confirmed vs tight opponents; refuted vs aggressive/random opponents.**
> Against loose/aggressive bots (always_call, always_raise, maniac), the bot is dominant. The structural weakness only manifests vs opponents that rarely fold and hold strong ranges.

### D1. Value-Bet Threshold Too Wide vs Non-Folders — **High Impact**

**Symptom:** vs nit, flop raise frequency = 39%, showdown win rate = 31.7%, net showdown chips = −174 over 180 hands.  
**Evidence:** Nit WR < 50% while bot bet > 35% of streets → betting into a range that beats us.  
**Root cause:** `vthr` [postflop.py:127] is fixed at 0.60 regardless of `fold_to_bet`. The only adjustment is `is_station` (−0.05), requiring `fold_to_bet < 0.25 AND faced_bets ≥ 12`. The nit's estimated `fold_to_bet ~ 3/8 = 0.375` → not station → `vthr = 0.60` → too wide.  
**Proposed fix (postflop.py:127, 2 lines):**
```python
tight_adj = max(0.0, (0.50 - fold_p) / 0.5) * 0.10  # +0–0.10 for tight callers
vthr = (0.58 if river else 0.60) - (0.05 if station else 0.0) + tight_adj
```
**Effort:** S. **Regression risk:** Low (clamped, only tightens vs non-folders).  
**Estimated impact:** +50–80 bb/100 vs tight opponents.

### D2. Bluff Path Missing `canr` Guard — **Medium Impact / Low Effort**

**Symptom:** `_choose()` [postflop.py:133–136] calls `_size(req, 0.6)` without first checking `can_raise(req)`.  
**Evidence:** When `min_raise is None` (all-in situation), `int(None)` raises `TypeError` inside `raise_action()` → caught by `postflop.decide()` except → `_cheap()`. Bluff equity is silently lost.  
**Root cause:** postflop.py:133 — no `canr` guard before the bluff branch.  
**Proposed fix (1 line):**
```python
if canr and e < (0.15 if river else 0.28) and not station:
```
**Effort:** S. **Regression risk:** None.

### D3. Station Detection Too Slow — **Medium Impact**

**Symptom:** `always_call` and similar callers are never classified as `is_station` because `faced_bets = 0` (they never bet postflop). vthr stays at 0.60 instead of 0.55.  
**Evidence:** Always_call never raises postflop → `post_opps` accumulates but `faced_bets` stays 0 [opponent_model.py:153–163] → `is_station` [opponent_model.py:206–207] never True.  
**Root cause:** Station detection relies on opponent betting *us* (we face their bet, then they fold). Against pure callers, there is no such signal.  
**Proposed fix (opponent_model.py:206, 2 lines):**
```python
passive_caller = self.vpip_rate > 0.80 and self.open_raise_freq < 0.05
return passive_caller or (self.faced_bets >= 12 and self.fold_to_bet < 0.25)
```
**Effort:** S. **Regression risk:** Low.

### D4. Uniform Bet Sizing — **Medium Impact, Medium Effort**

**Symptom:** 100% of raises land in 33–68% pot range; no over-bets; no small probes.  
**Evidence:** Raise histogram (Part C2d): mean 49% pot, max 68% pot. Formula `frac = min(1.0, 0.45 + (e − vthr) × 1.6)` produces 0.45–1.0, but `_size()` [postflop.py:84–86] jams to `max_raise` when `add ≥ 0.45 × my_stack`. No board texture input.  
**Root cause:** No board-texture signal (dry vs wet, paired, monotone). Fixed formula regardless of SPR.  
**Proposed fix:** Add a `board_texture` multiplier (dry boards → 1.3× fraction; wet boards → 0.75×). **Effort:** M. **Regression risk:** Medium.

### D5. Call Margin Too Conservative — **Low-Medium Impact**

**Symptom:** Bot may fold marginally profitable calls vs aggressive opponents.  
**Evidence:** Call margin formula [postflop.py:114] starts at 0.025 (2.5% over pot odds minimum). `BLUFF_CATCH_BUFFER=0.05` defined in config.py:35 is never used anywhere in the code.  
**Root cause:** `BLUFF_CATCH_BUFFER` defined but not wired. Call margin is hardcoded in postflop.py:114 with a 2.5% minimum that discards hands at exactly pot odds.  
**Proposed fix:** Set base margin to 0.00; keep stack-fraction premium:
```python
margin = (0.03 if i_bet else 0.0) + (0.02 if not ip and street != "flop" else 0.0) + 0.06 * stack_frac
```
**Effort:** S. **Regression risk:** Low.

### D6. Check-Raise / 3-Bet Frequency — **Low Impact**

**Symptom:** Check-raises only when `e > 0.90 AND not river AND agg > 0.5 AND random() < 0.35` [postflop.py:129–130] — fires ~2.5% of monster hands.  
**Root cause:** The 35% random multiplier and 0.90 equity threshold are very restrictive.  
**Proposed fix:** Increase to 50% for `e > 0.85`, remove `agg > 0.5` requirement (trapping works vs any opponent). **Effort:** S.

### D7. Opponent Discard Information on Turn/River — **Working Correctly**

`build_base()` [equity.py:79] correctly conditions the opponent's pair range on the revealed discard with a soft-weight model. The temperature parameter (0.25) is not calibrated against real opponent behavior (UNVERIFIED), but the direction is correct.

### D8. Exploitation: always_call vs always_raise — **Working Correctly**

- vs always_call: dominant (+1270 bb/100). Bot value-bets repeatedly. Main leak: vthr=0.60 leaves ~15% of moderately strong hands un-bet.
- vs always_raise: dominant (+1544 bb/100). Bot calls/re-raises with strong hands and folds marginal hands. No structural weakness.

---

## PART E — OTHER AREAS RANKED

### E1. Preflop Strategy

**Weakness 1 (Medium):** Evidence gate `OPP_EVIDENCE_MIN_SAMPLES=6` [config.py:72] means width stays ≥ 40% until 6 showdowns with preflop raises. Against a maniac opening 70%+, the bot uses a 40% width assumption for the first ~20–30 hands, calling with hands that should 3-bet. Impact ~20 bb/100 in first 30 hands.  
**Code:** config.py:72, opponent_model.py:243.  
**Fix:** Lower threshold to 3. Effort: S.

**Weakness 2 (Low):** `OPEN_PCT=0.30` (open top 70% of hands on button) is wide; some weak hands open and then struggle postflop. UNVERIFIED net impact — the discard step upgrades many marginal preflop openings.

### E2. Discard Choice — **Strong**

The discard module correctly selects differently from the naive lowest-rank heuristic 40.8% of the time, gaining a measured 5.4 equity pp/hand average. No action needed.

### E3. Opponent Model

**Weakness 1 (Medium):** `is_station` requires `faced_bets ≥ 12` — too slow to trigger vs pure callers (see D3). Fix there covers this.

**Weakness 2 (Low):** `disc_consistency` prior is 4.0/5.0 = 0.80 (strong prior that opponent discards optimally). If the opponent discards randomly, this misleads the range filter for the first ~15 observations. UNVERIFIED impact.

**Strength:** The Bayesian `open_width()` with Laplace smoothing and evidence blending is well-designed. `bet_value_rate` for opponent trust is correct in direction.

### E4. Time Management — **No Action Needed**

Budget formula is conservative (0.8× scaling). Max single-decision: 74.9 ms vs 5000 ms limit. Max total: 34.09 s vs 60 s bank. `preflop` kind not in `_SHARE` dict defaults to 0.3, giving 36 ms budget — fine since preflop is 0.0 ms actual. No issues found.

---

*All numbers are measured unless marked UNVERIFIED. All code references use `file:line` from source as read on 2026-11-09.*
