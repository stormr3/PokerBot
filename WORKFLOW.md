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
* **Primary Scope:** `core/` directory (`protocol.py`, `state.py`, `safety.py`), initial `bot.py` event loop integration, and `tests/local_runner.py`.
* **Deliverables:**
  1. Build `core/protocol.py` to parse JSON from `stdin` and route `action_request` / `discard_request`.
  2. Implement `core/state.py` to track pot, bets, history, stacks, and time bank.
  3. Implement `core/safety.py` to sanitize actions and handle fallbacks.
  4. Scaffolding and initial integration of `bot.py` event loop.
  5. Build `tests/local_runner.py` to simulate a complete 400-hand match between two bots over pipes.

### Member 2: Strategic Decision Engines & Equity Evaluator
* **Primary Scope:** `strategy/` directory (`cards.py`, `evaluator.py`, `equity.py`, `discard.py`, `betting.py`, `opponent.py`).
* **Deliverables:**
  1. Build `strategy/cards.py` for card ID mapping (0..51) and 32-bit Cactus Kev bitmasks.
  2. Build `strategy/evaluator.py` for fast O(1) 5-card & 7-card hand strength evaluation.
  3. Build `strategy/equity.py` for vectorized Monte Carlo equity rollouts with `numpy`.
  4. Build `strategy/discard.py` to determine flop discard candidate optimization.
  5. Build `strategy/betting.py` for preflop opening rules, pot-odds calculation, and bet sizing.
  6. Build `strategy/opponent.py` for independent opponent sampling without card leakage.

### Joint Responsibilities & Collaboration Guidelines
* **Tests & Integration:** Both members jointly write and review unit tests in `tests/` and participate in end-to-end integration reviews.
* **Shared File Discipline:** Avoid simultaneous overlapping edits to shared files (e.g., `bot.py`). Member 1 establishes the initial `bot.py` interface; Member 2 hooks in strategy endpoints via small, focused PRs.
* **Feature Branches & Reviews:** All code lands via dedicated feature branches (e.g. `feature/protocol-io`, `feature/evaluator`). Direct pushes to `main` are strictly forbidden; each PR requires peer review.

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
