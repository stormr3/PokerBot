# Discard Hold'em Pokerbot

A modular, high-performance Python 3.11 Pokerbot built for the **Discard Hold'em** competition.

---

## 📁 Repository Structure

```text
PokerBot/
├── src/                    # Bot source code (packaged into submission.zip root)
│   ├── bot.py              # [Shared] Main entry point, IPC event loop, & fallback handler
│   ├── state.py            # [Shared] GameState tracking & opponent model callbacks
│   ├── config.py           # [Shared] Tunable thresholds, time budgets, & feature flags
│   ├── evaluator.py        # [Person A] Hand strength ranking (5-card & 7-card best hand)
│   ├── equity.py           # [Person A] Monte Carlo rollout simulation engine
│   ├── discard.py          # [Person B] Flop 3-card discard candidate evaluation
│   ├── betting.py          # [Person B] Preflop/postflop betting decision logic
│   ├── preflop_table.py    # [Person B] 3-card preflop hand tiers & range charts
│   └── opponent_model.py   # [Person B] Opponent statistics (VPIP, PFR) & range sampling
│
├── docs/                   # Official competition documentation & starter kit
│   ├── PS.pdf              # Problem Statement & worked examples
│   ├── Protocol.pdf        # Stdin/stdout JSON protocol specification
│   ├── Rulebook.pdf        # Tournament rules, scoring, limits, and conduct
│   └── Starter_Kit.zip     # Original starter kit archive
│
├── opponents/              # Baseline bots for local testing
│   ├── always_call.py      # Checks if free, calls any bet
│   ├── always_raise.py     # Min-raises whenever legal, otherwise checks/calls
│   ├── tight_folder.py     # Checks if free, folds to any bet
│   └── random_bot.py       # Chooses randomly among legal actions/discards
│
├── tools/                  # Developer utilities
│   ├── bench.py            # Multi-match benchmark runner (supports .py and .zip bots)
│   └── package.py          # Packages src/ into submission.zip and verifies import sandbox
│
├── example_bots/           # Starter kit example bots
├── engine.py               # Official local match runner from organisers
├── notes.md                # Team task board (Person A / B split) & results ledger
└── README.md               # Project documentation
```

---

## ⚡ Quick Start

### 1. Requirements
* Python 3.11 (or 3.12 locally)
* Standard library, `numpy`, and `scipy` ONLY.

### 2. Run a Single Match
Run a 400-hand Stage 1 match against a baseline bot:
```bash
python engine.py src/bot.py opponents/random_bot.py --stage 1 --hands 400
```

### 3. Run Multi-Match Benchmarks
Run a multi-match benchmark across random seeds:
```bash
python tools/bench.py src/bot.py opponents/always_call.py -n 5 --hands 400
```
*(You can also pass `submission.zip` to test the packaged archive directly).*

### 4. Build & Verify Submission Package
Build `submission.zip` and verify that all packaged modules adhere strictly to the allowed import sandbox:
```bash
python tools/package.py
```
This produces `submission.zip` with `bot.py` and all sibling modules at the root of the archive, verified under the 5 MB limit.
