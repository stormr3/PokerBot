# WORKFLOW.md — Team Collaboration & GitHub Git Workflow

This document outlines the development workflow, branching strategy, testing protocol, and workload distribution for our two-person team competing in the **Pokerbots Competition**.

---

## 🌿 Git Branching Strategy

To prevent merge conflicts and ensure code stability, **direct commits to `main` are strictly forbidden**.

### Branch Naming Conventions
* `main` — Production-ready submission code. Must pass all 400-hand simulation tests.
* `feature/protocol-io` — Engine message parsing, state tracking, and output safety.
* `feature/evaluator` — Hand evaluation and equity calculation modules.
* `feature/discard-engine` — Flop card discard strategies.
* `feature/betting-strategy` — Preflop and postflop betting algorithms.
* `feature/local-runner` — Local match simulation and testing harness.
* `bugfix/<issue-description>` — Fixes for edge cases, memory leaks, or protocol bugs.

---

## 👥 Workload Split & Responsibilities

### Member 1: Infrastructure, Protocol Engine & Testing Harness
* **Primary Scope:** `core/` directory, `bot.py` event loop, and `tests/local_runner.py`.
* **Deliverables:**
  1. Build `core/protocol.py` to parse JSON from `stdin` and route `action_request` / `discard_request`.
  2. Implement `core/state.py` to track pot, bets, history, stacks, and time bank.
  3. Implement `core/safety.py` to sanitize actions and handle fallbacks.
  4. Build `tests/local_runner.py` to simulate a complete 400-hand match between two bots over pipes.

### Member 2: Strategic Decision Engines & Equity Evaluator
* **Primary Scope:** `strategy/` directory.
* **Deliverables:**
  1. Build `strategy/evaluator.py` for 3-card preflop hand strength and 5-card post-flop evaluation using `numpy`.
  2. Build `strategy/discard.py` to determine which card to discard on the flop based on remaining hand equity.
  3. Build `strategy/betting.py` for pot-odds-based betting, raise sizing, and fold thresholds.

---

## 🔄 Pull Request & Merge Workflow

Every PR must satisfy the following checklist before merging into `main`:

1. **Local Simulation Pass:** Run the local runner and ensure 400 hands complete with 0 notices/forfeits:
   ```bash
   python3 tests/local_runner.py
   ```
2. **`stdout` Cleanliness Check:** Confirm that no non-JSON output is sent to stdout.
3. **Time Bank Verification:** Ensure average reply time is < 15ms and total time used is well under 60 seconds.
4. **Peer Review:** The non-author team member must review and approve the PR.

---

## 📅 Implementation Timeline

```text
Phase 1: Foundation & Simulator (Days 1–3)
├── Implement core/protocol.py & core/state.py
├── Build core/safety.py fallback handlers
└── Create tests/local_runner.py with a check/fold baseline bot

Phase 2: Evaluator & Discard Logic (Days 4–7)
├── Implement strategy/evaluator.py (numpy lookup tables / equity math)
└── Implement strategy/discard.py (flop discard decision logic)

Phase 3: Betting Engine & Position Rules (Days 8–11)
├── Preflop opening ranges (Button vs Big Blind)
└── Postflop pot odds, bet sizing, and raise limits

Phase 4: Benchmarking, Optimization & Submission (Days 12–15)
├── Benchmark bot against multiple strategy archetypes
├── Optimize decision speed and time bank budget
├── Package into single zip file (<= 5 MB)
└── Final Upload before Nov 15, 23:59 IST deadline
```

---

## 📦 Submission Zip Generator

Before submitting on the platform, create the final submission package:

```bash
# Verify zip size is under 5 MB and bot.py is at the root
zip -r submission.zip bot.py core/ strategy/ -x "*.pyc" "__pycache__/*"
```
