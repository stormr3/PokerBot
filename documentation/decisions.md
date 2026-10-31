# Architectural & Strategic Decisions Record

This document records the foundational architectural decisions, strategy roadmap, runtime environment considerations, official protocol rules, and internal implementation choices for the Discard Hold'em tournament bot.

> **Scope Notice:** This audit and design are strictly bounded by the official **Pokerbots Rulebook** and **Protocol Specification**. The full Problem Statement (noted in the rulebook to be released 1st November) is not present; no missing rules have been invented.

---

## Decision 1: Monte Carlo Equity Simulation First

### Context
Discard Hold'em introduces 3 initial hole cards and an exposed simultaneous discard after the flop betting round. We evaluated two algorithmic approaches:
1. Counterfactual Regret Minimization (CFR / MCCFR).
2. High-performance vectorized Monte Carlo equity simulation with pot-odds and SPR threshold betting.

### Decision
We build and benchmark **Monte Carlo equity simulation first** for the competition bot.

### Rationale
1. **Computational Feasibility & Latency:** Vectorized Monte Carlo rollouts with NumPy execute in 2–5 ms per decision on 1 vCPU, safely inside our < 15 ms target budget.
2. **Memory & Complexity Constraints:** Solving full-game CFR within 1 GB RAM requires complex game abstractions and bucket precomputation that carries high risk of abstraction errors.
3. **Speed of Delivery:** An equity-driven engine combined with positional rules, clean pot-odds calculations, and discard optimization delivers a robust, reliable tournament competitor.

---

## Decision 2: Offline CFR / MCCFR Research Decoupled from Bot Runtime

### Context
Game-theoretic analysis (CFR) remains valuable for investigating equilibrium blueprint strategies, bluffing ratios, and abstract subgame dynamics, but must not bloat the tournament submission.

### Decision
CFR and MCCFR research is isolated strictly in the `training/` directory (`training/kuhn_cfr.py`, `training/mccfr.py`, and `training/experiments/`).

### Rationale
- The tournament bot package must stay compact (< 5 MB, pure code) and free of offline training dependencies.
- Code in `training/` will NOT be bundled into the competition submission zip.
- Prevents circular imports and runtime overhead in `bot.py`.

---

## Decision 3: Read-Only Filesystem Compatibility

### Context
The tournament sandbox specifies a read-only filesystem, 1 vCPU, 1 GB RAM, and no network access.

### Decision
1. **Zero File I/O:** The bot performs zero file write or creation operations (`open(..., 'w')`, temporary directories, disk caching).
2. **In-Memory Tables:** Hand evaluation tables and bitmasks are generated purely in memory upon bot launch during the 5-second uncharged start-up grace period.
3. **Logging Discipline:** All diagnostic logging is routed through `core.protocol.log_debug()` to `sys.stderr` with an internal 50 KB safety cap to satisfy the official 64 KB engine limit.
4. **Bytecode Cache:** Python's attempt to write `.pyc` bytecode files into `__pycache__` is ignored by Python 3.11 runtime on read-only filesystems.

---

## Decision 4: Official Protocol Rules vs. Implementation Choices

To prevent conflation, system components are partitioned into official rules vs. internal choices:

### A. Authoritative Official Rules (Rulebook & Protocol Spec)
1. **Discard Request Board:** `discard_request.board` contains **exactly the 3 flop cards** (Section 5.4).
2. **Discard Timing & All-In:** Discard occurs after flop betting round if no player has folded. Discard takes place if both players are all-in, but does NOT occur if a player folds before flop betting ends (Section 4).
3. **Simultaneous & Hidden Discards:** Both players choose discards secretly and simultaneously. Both discards remain hidden until `discard_result` is broadcast (Section 4.4).
4. **Discard Result Revelation:** `discard_result` reveals both `my_discard` and `opp_discard` face-up, and updates `hole_cards` to the 2 remaining cards (Section 5.5).
5. **Hand Result Hole Cards:** `hand_result.my_hole_cards` contains 3 cards if the hand ended before the discard, and 2 cards if a discard occurred (Section 5.6).
6. **Action Request Authoritative Fields:** `legal_actions`, `min_raise`, `max_raise`, and `raises_left` from `action_request` are authoritative. Maximum 4 bets/raises per street (BB is 1st preflop). Raise amount is a "to" amount (total committed on street), not increment (Section 3, 5.3 & 7).
7. **Official Fallback Corrections:**
   - Illegal action -> corrected to check if legal (to_call == 0), otherwise fold.
   - Illegal discard -> lowest-ranked card (2 lowest, ace highest). Among equal ranks, the card whose suit comes first in `spades, hearts, diamonds, clubs` is discarded (earliest suit discarded) (Section 9.4).
8. **Notice Message:** Informational error notice from engine; **no reply is expected** (Section 5.7).
9. **Duplicate Deals:** Every deal is played twice with cards swapped between seats. The bot is not told which deals are duplicates, keeps no state between matches, and must not predict paired hands (Section 1.4 & 3).
10. **Provisional Limits:** Time bank (60s Stage 1, 150s Stage 2), per-reply limit (5s), and wall-clock kills (180s/450s) are officially marked *(provisional)* (Section 8).

### B. Internal Implementation Choices (Not Official Rules)
1. **Card Encoding:** Representing cards as dense integers `[0, 51]` and Cactus Kev 32-bit bitmasks with primes is an internal choice for evaluation speed.
2. **Evaluator Architecture:** Prime product lookup tables, 21-combination evaluation for 7 cards, and score ranking `[1, 7462]` are internal algorithms.
3. **Opponent Modeling:** Tracking opponent VPIP/PFR and modeling independent discard logic are heuristic strategic layers.
4. **Monte Carlo Sampling:** Rollout sample counts (e.g. 150, 100) and rollout sampling formulas are internal choices calibrated for the < 15 ms target latency.
5. **Betting Thresholds & Sizing:** Bet sizing fractions (e.g., 50-75% pot), equity thresholds (e.g., 0.68 value raise), and preflop range tiers are internal heuristics.
6. **Local Runner Scope:** `tests/local_runner.py` is an adapter for the organiser's official starter-kit runner; we do not build a custom poker engine.

---

## Decision 5: Organiser Clarifications & Uncertainties Flag

| # | Topic | Documentation Status | Handling Strategy |
| :--- | :--- | :--- | :--- |
| **U1** | **Problem Statement Release** | Referenced in Rulebook 1.3 as releasing 1st November. Not currently in workspace. | Confining all assumptions and rules strictly to Rulebook and Protocol Specification. |
| **U2** | **Provisional Time Limits Confirmation** | Time limits (60s / 150s, 5s per response) are marked *(provisional)*. | Bot relies on dynamic `time_left_ms` provided in each request rather than hardcoding. |
| **U3** | **Official Starter Kit Local Runner** | Protocol Section 12 notes the bot is tested against the starter kit's runner. | Kept `tests/local_runner.py` as a lightweight adapter for the official runner rather than maintaining a redundant custom engine. |
