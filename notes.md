# Discard Hold'em Pokerbot — Engineering Notes & Task Board

## 1. Competition Constraints & Invariants

* **Runtime:** Python 3.11 (Standard Library + `numpy` + `scipy` ONLY).
* **Hardware:** 1 vCPU, 1 GB RAM, read-only filesystem, no network access.
* **Submission Format:** `.zip` file with `bot.py` at top level (sibling modules), max 5 MB.
* **I/O Interface:**
  * Read UTF-8 JSON lines on `sys.stdin`.
  * Emit **ONLY** valid protocol JSON to `sys.stdout` with `flush=True`.
  * Debug logs **MUST** go to `sys.stderr` (capped at 64 KB = 65,536 bytes per match).
* **Time Bank:**
  * Stage 1: 60 seconds per 400 hands (~150 ms/hand average, ~15 ms/decision).
  * Stage 2: 150 seconds per ~1000 hands.
  * Max 5.0 seconds per response.
* **Error Discipline:**
  * Illegal action -> corrected to `check` if legal, else `fold`.
  * Illegal discard -> corrected to lowest-ranked card (tiebreak suit order: spades, hearts, diamonds, clubs).
  * Crash or timeout -> **immediate match forfeit** ($\Delta = -C$).

---

## 2. Team Workload Split & Task Board

### Person A: Infrastructure, Evaluator & Equity Estimation
* [x] Scaffold `src/state.py` (GameState tracking, pot odds, SPR, opponent model callbacks).
* [x] Implement `src/evaluator.py` (5-card hand rankings, 7-card best hand selection, default discard).
* [x] Implement `src/equity.py` (Monte Carlo rollout simulation with dynamic time budget check).
* [ ] Accelerate `src/evaluator.py` (lookup tables / Cactus Kev bitwise algorithm for sub-microsecond evals).
* [ ] Implement dead-card exclusion and draw-out estimation in `src/equity.py`.
* [ ] Benchmark Monte Carlo iterations vs time bank consumption (target $\ge 200$ rollouts in $< 10$ ms).

### Person B: Discard Strategy, Betting Engine & Opponent Modeling
* [x] Scaffold `src/preflop_table.py` (3-card hand tier classification and opening rules).
* [x] Scaffold `src/opponent_model.py` (statistical profile: VPIP, PFR, discards seen, range sampling).
* [x] Implement `src/discard.py` (scoring 3 candidate 2-card holdings on flop, keeping best made hand).
* [x] Implement `src/betting.py` (pot-odds calculation, raise sizing, legal action clamping).
* [ ] Enhance `src/discard.py` with draw potential bonuses (flush/straight draws) and blocker considerations.
* [ ] Enhance `src/betting.py` with multi-tier equity thresholds (value betting, bluff-catching, semi-bluffs).
* [ ] Enhance `src/opponent_model.py` with exploitative adjustments (calling station vs maniac counters).

### Joint Responsibilities
* [x] Maintain `src/bot.py` IPC loop and top-level exception guards.
* [x] Maintain `src/config.py` tunable parameters and feature flags.
* [x] Maintain test bots in `opponents/` (`always_call`, `always_raise`, `tight_folder`, `random_bot`).
* [x] Implement `tools/bench.py` and `tools/package.py`.
* [ ] Log match results in the Results Ledger before committing major changes.

---

## 3. Benchmark Results Ledger

| Date / Commit | Bot Config | Opponent | Hands | Seed | Net Chips | Time Used | Notices | Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-11-04 (Init) | Baseline Skeleton | always_call | 400 | 12345 | +13 | 0.00s / 60s | 0 | Win |
| 2026-11-04 (Init) | submission.zip | random_bot | 3x100 | multi | +617 | 0.00s / 60s | 0 | 3 Wins, 0 Losses |
| 2026-11-04 (Init) | Baseline Skeleton | tight_folder | 2x100 | multi | +152 | 0.00s / 60s | 0 | 2 Wins, 0 Losses |
| 2026-11-04 (Init) | Baseline Skeleton | always_raise | 2x100 | multi | +426 | 0.00s / 60s | 0 | 2 Wins, 0 Losses |
