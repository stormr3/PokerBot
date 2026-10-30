# Discard Hold'em Pokerbot

An AI-driven poker bot built for the **Pokerbots Competition**. The bot plays **Discard Hold'em**, a heads-up Texas Hold'em variant featuring 3 initial hole cards and a simultaneous exposed discard phase after the flop betting round.

---

## 📋 Table of Contents
- [Game Overview](#game-overview)
- [Technical Constraints](#technical-constraints)
- [Repository Structure](#repository-structure)
- [Protocol Specification](#protocol-specification)
- [Setup & Local Testing](#setup--local-testing)
- [Team Workload Split](#team-workload-split)
- [Submission Guidelines](#submission-guidelines)

---

## 🃏 Game Overview

* **Variant:** Heads-up No-Limit Discard Hold'em.
* **Starting Stack:** 200 chips per player (stacks reset every hand).
* **Blinds:** Small Blind = 1 chip, Big Blind = 2 chips.
* **Hole Cards:** Each player is dealt **3 initial hole cards**.
* **Discard Phase:** After the flop betting round (if no player folds), both players secretly and simultaneously select **1 card to discard**. Both discards are revealed face-up before the turn card is dealt.
* **Showdown:** Best 5-card combination formed from 2 remaining hole cards + 5 community cards.
* **Betting Rules:** No-limit. Minimum raise equals the size of the previous bet/raise (min 2 chips). Maximum 4 bets/raises per betting street (big blind counts as the first raise preflop).

---

## ⚡ Technical Constraints

* **Runtime:** Python 3.11.
* **Allowed Libraries:** Standard library, `numpy`, and `scipy` ONLY. No runtime package installations allowed.
* **Environment:** 1 vCPU, 1 GB RAM, read-only filesystem, no network access.
* **Communication Interface:** UTF-8 JSON lines via `stdin` (from match engine) and `stdout` (to match engine).
* **I/O Discipline:** `stdout` must contain **ONLY valid JSON responses**. All debug logs must go to `stderr` (capped at 64 KB per match). Every response must use `flush=True`.
* **Time Limits:** 
  * Stage 1: 60-second time bank per 400-hand match.
  * Stage 2: 150-second time bank per ~1000-hand match.
  * Per-reply timeout: 5 seconds max.

---

## 📁 Repository Structure

```text
pokerbot/
├── bot.py                # Main entry point (reads stdin, routes JSON messages)
├── core/
│   ├── protocol.py       # Stdin/stdout JSON transport & message parser
│   ├── state.py          # Tracks game state, pot, stacks, board, and history
│   └── safety.py         # Validates legal actions, raise bounds, & fallback safety
├── strategy/
│   ├── evaluator.py      # 3-card preflop strength & 5-card hand equity evaluator
│   ├── discard.py        # Flop card discard decision engine
│   └── betting.py        # Preflop & postflop action decision logic
├── tests/
│   └── local_runner.py   # Local engine simulator for 400-hand bot-vs-bot matches
├── AGENTS.md             # Antigravity AI agent instructions & safety rules
├── WORKFLOW.md           # Git branching, PR guidelines, and team task split
└── README.md             # Project documentation
```

---

## 🛰 Protocol Specification

The bot receives JSON messages line-by-line on `stdin` and replies on `stdout`:

| Message Type | Direction | Expects Reply? | Description |
| :--- | :--- | :--- | :--- |
| `init` | Engine → Bot | No | Match setup details (hands, stack, time bank). |
| `new_hand` | Engine → Bot | No | Starts hand, gives seat and 3 hole cards. |
| `action_request` | Engine → Bot | **Yes** (`action`) | Request for fold, check, call, or raise. |
| `discard_request` | Engine → Bot | **Yes** (`discard`) | Request to select 1 card to discard post-flop. |
| `discard_result` | Engine → Bot | No | Reveals both discarded cards. |
| `hand_result` | Engine → Bot | No | End of hand, net chips won/lost, showdown info. |
| `notice` | Engine → Bot | No | Error notification (e.g., corrected action/discard). |
| `match_end` | Engine → Bot | No | Signals end of match; bot should exit cleanly. |

---

## 🚀 Setup & Local Testing

### Prerequisites
* Python 3.11
* `numpy` and `scipy`

```bash
pip install numpy scipy
```

### Running the Local Simulator
Verify stdout compliance and time performance across 400 hands before committing:

```bash
python3 tests/local_runner.py
```

---

## 👥 Team Workload Split

* **Member 1 (Infrastructure & Transport):** Focuses on `core/protocol.py`, `core/state.py`, `core/safety.py`, and `tests/local_runner.py`.
* **Member 2 (Strategy & Evaluation):** Focuses on `strategy/evaluator.py`, `strategy/discard.py`, and `strategy/betting.py`.

Refer to [`WORKFLOW.md`](./WORKFLOW.md) for full branch management and PR guidelines.

---

## 📦 Submission Guidelines

* **Format:** Single root `bot.py` or `.zip` file containing `bot.py` at the top level (max 5 MB).
* **Deadline:** 15 November 2026, 23:59 IST.
