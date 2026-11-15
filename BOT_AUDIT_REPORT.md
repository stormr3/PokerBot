# Comprehensive Technical Audit: Discard Hold'em Pokerbot

**Audit Date:** November 5, 2026  
**Audited Target:** `src/` modular codebase (`AcesDiscard` v1.0.0)  
**Target Environment:** Python 3.11 (Standard Library, `numpy`, `scipy` only), 1 vCPU, 1 GB RAM, read-only filesystem  
**Tournament Rules Reference:** Pokerbots Rulebook (2026), Protocol Specification v1.0, Problem Statement v1.0  
**Audit Exclusions Enforced:** `preflop_data.py` and `generate_preflop_table_2.py` were strictly excluded from analysis, reference, and conclusions.

---

## 1. Executive Summary

This audit provides an independent, evidence-based technical assessment of the Discard Hold'em poker bot developed for the 2026 Pokerbots competition. The codebase was developed by a two-member first-year student team, splitting responsibilities between infrastructure/equity estimation (Person A) and strategy/betting/discard logic (Person B).

The bot possesses an exceptionally strong architectural foundation: clean IPC protocol framing, zero stdout leaks, automated AST packaging with submission compliance validation, and a precomputed canonical 3-card preflop equity table covering all 1,755 isomorphism classes with $O(1)$ lookup time. In benchmark testing against baseline opponents (`random_bot`, `always_call`, `always_raise`, `tight_folder`), the bot achieves 100% win rates.

However, beneath this polished exterior lie **fatal strategic vacuums and critical reliability traps**:
1. **Zero Postflop Betting Engine (Calling Station Leak):** Postflop betting logic is completely unwritten. On flop, turn, and river, the bot checks whenever possible and calls 100% of opponent bets. The postflop fold branch is mathematically dead code. The bot will call an all-in shove on the river with 7-high, and will check behind the absolute nuts (e.g., Royal Flush) for zero value.
2. **Discard Engine is Blind to Draws:** The discard selector evaluates only 5-card made hands on the 3-card flop. It assigns zero value to flush draws, straight draws, or combo draws. In verified testing, holding $\text{A}\heartsuit\text{K}\heartsuit\text{2}\clubsuit$ on a $\text{Q}\heartsuit\text{J}\heartsuit\text{2}\diamondsuit$ flop, the bot discards $\text{K}\heartsuit$—breaking the Nut Royal Flush and open-ended straight draw—to retain bottom pair deuces.
3. **Orphaned Modules:** The Monte Carlo equity simulation engine (`equity.py`) and opponent statistical model (`opponent_model.py`) are completely disconnected. Neither is imported or called by the decision engine.
4. **Crash-to-Forfeit Bugs:** If the engine ever sends a malformed `discard_request` with empty `hole_cards`, the fallback handler invokes `default_discard([])`, triggering an unhandled `ValueError: min() arg is an empty sequence` that crashes the process and instantly forfeits the match. Furthermore, state update callbacks (`on_new_hand`, `on_hand_result`) lack top-level exception guards in the main event loop.
5. **Gross Preflop Defense Over-extension:** Preflop equity lookup compares private hand equity against a 100% uniform random hand. Against a preflop raise from 2 to 6 chips (pot odds 33.3%), the bot defends the Big Blind with 99.43% of all possible hands (1,745 of 1,755 canonical holdings), calling with complete trash.

Submitted in its current state, the bot will easily beat naive benchmark bots but will be systematically exploited and dismantled by any competent competitor within 20 hands.

---

## 2. Overall Assessment

| Assessment Dimension | Rating | Summary Verdict |
| :--- | :---: | :--- |
| **Protocol Compliance** | **9 / 10** | High compliance with protocol specification; strict JSON framing; zero stdout pollution; proper stderr bounding. |
| **Reliability & Crash Resilience** | **6 / 10** | Strong try/except shields around action requests, but fatal crash bug in discard fallback and unshielded state event handlers. |
| **Poker Evaluation Correctness** | **8 / 10** | Accurate 5-card hand ranking and tiebreaking; verified wheel straight logic; but dangerous dummy card padding bug on $<5$ cards. |
| **Strategic Sophistication** | **3 / 10** | Excellent preflop table lookup, but catastrophic zero-bet postflop passive calling station; discard logic completely ignores draws. |
| **Performance & Resource Budget** | **7 / 10** | Preflop lookup is instantaneous ($O(1)$); however, the hand evaluator is slow (~105 $\mu\text{s}$/eval), making Monte Carlo rollouts too slow for 1 vCPU limits. |
| **Testing & Verification** | **2 / 10** | Zero unit tests exist in the codebase. Only a multi-match benchmark script and a 2-hand smoke test exist. |

---

## 3. Project Architecture and Execution Flow

### 3.1 Architectural Decomposition

The repository adheres to a clean separation of concerns across 9 core modules in `src/`:

```
                    ┌─────────────────────────┐
                    │      engine.py (IPC)    │
                    │   stdin / stdout (JSON) │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │         bot.py          │
                    │ (Main IPC Loop & Guards)│
                    └──────┬───────────┬──────┘
                           │           │
             ┌─────────────┴─────┐     └─────────────┬─────────────┐
             ▼                   ▼                   ▼             ▼
      ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
      │   state.py   │    │ opponent_    │    │ preflop_     │    │ evaluator.py │
      │  (GameState  │    │  model.py    │    │  table.py    │    │ (rank5 &     │
      │   Tracking)  │    │ (VPIP / PFR) │    │ (.npz Table) │    │  best_hand)  │
      └──────┬───────┘    └──────────────┘    └──────┬───────┘    └──────┬───────┘
             │                                       │                   │
             │           ┌───────────────────────────┘                   │
             ▼           ▼                                               ▼
      ┌──────────────────────────┐                        ┌──────────────────────────┐
      │        betting.py        │                        │        discard.py        │
      │ (Preflop / Postflop AI)  │                        │  (Flop 3-card Selection) │
      └──────────────────────────┘                        └──────────────────────────┘
             │                                                           ▲
             │                                                           │
             │     [DISCONNECTED]                                        │
             └ - - - - - - - - - > ┌──────────────────────────┐ - - - - -┘
                                   │        equity.py         │
                                   │ (Monte Carlo Simulation) │
                                   └──────────────────────────┘
```

### 3.2 End-to-End Execution Trace

When the engine communicates with the bot during a hand, the control flow proceeds as follows:

```
[Engine]                          [bot.py]                         [Submodules]
   │                                 │                                   │
   ├─────── {"type":"init"} ────────>│                                   │
   │                                 ├────── state.on_init() ───────────>│
   │                                 │                                   │
   ├───── {"type":"new_hand"} ──────>│                                   │
   │                                 ├────── state.on_new_hand() ───────>│
   │                                 │                                   │
   ├─── {"type":"action_request"} ──>│                                   │
   │    (preflop)                    ├────── state.on_action_request() ─>│
   │                                 ├────── betting.decide() ──────────>│
   │                                 │         │                         │
   │                                 │         ├── preflop_table.get_preflop_equity()
   │                                 │         │     (O(1) table lookup)
   │                                 │         └── pot odds vs buffer
   │<────── {"type":"action"} ───────┤
   │                                 │
   ├─── {"type":"action_request"} ──>│
   │    (flop)                       ├────── betting.decide() ──────────>│
   │                                 │         └── [POSTFLOP SKELETON]   │
   │                                 │               check if legal,     │
   │                                 │               else call!          │
   │<────── {"type":"action"} ───────┤                                   │
   │                                 │                                   │
   ├─── {"type":"discard_request"} ─>│                                   │
   │                                 ├────── state.on_discard_request() ─>│
   │                                 ├────── discard.choose() ──────────>│
   │                                 │         └── evaluator.best_hand() │
   │                                 │               (5-card made hand)  │
   │<────── {"type":"discard"} ──────┤                                   │
   │                                 │                                   │
   ├─── {"type":"discard_result"} ──>│                                   │
   │                                 ├────── state.on_discard_result() ──>│
   │                                 ├────── opp_model.on_discard_result()
   │                                 │                                   │
   ├─── {"type":"action_request"} ──>│                                   │
   │    (turn & river)               ├────── betting.decide() ──────────>│
   │                                 │         └── always check / call!  │
   │<────── {"type":"action"} ───────┤                                   │
   │                                 │                                   │
   ├──── {"type":"hand_result"} ────>│                                   │
   │                                 ├────── state.on_hand_result() ─────>│
   │                                 ├────── opp_model.on_hand_result() ─>│
   │                                 │                                   │
   ├──── {"type":"match_end"} ──────>│                                   │
   │                                 └────── break loop & exit 0         │
```

---

## 4. Module-by-Module Review

### 4.1 `src/bot.py` (Main Entry Point & IPC Event Loop)
* **Author / Owner:** Shared (Person A & Person B).
* **Role:** Reads stdin line-by-line, decodes JSON, routes requests to decision modules, validates replies against tournament legality rules, catches exceptions with safe fallback actions, and outputs flushed JSON to stdout.
* **Positive Findings:**
  * Clean, non-blocking standard I/O loop.
  * Properly redirects debug logging to `sys.stderr`, capped by `MAX_STDERR_BYTES` (50,000 bytes) to stay safely under the official 64 KB engine kill limit.
  * Explicit fallback action handling: catches invalid actions and converts to `check` (if legal) else `fold`, matching Rulebook Section 9.3.
  * Formats outgoing JSON with `separators=(",", ":")` and `flush=True`, minimizing latency and serialization overhead.
* **Flaws & Weaknesses:**
  * **Critical Discard Fallback Bug:** Line 89 calls `default_discard(hole_cards)` inside the exception handler. If `hole_cards` is empty or missing, `min()` crashes with `ValueError`, escaping the handler and causing an immediate fatal process exit.
  * **Unshielded State Events:** Lines 116–126 dispatch `on_init`, `on_new_hand`, `on_discard_result`, `on_hand_result`, and `on_notice` without any `try/except` guard. A single malformed payload or `KeyError` will crash the bot.
  * **Boolean Raise Amount Subclassing:** Line 64 checks `if not isinstance(amt, int)`. Because `isinstance(True, int) == True` in Python, a boolean value would pass validation and be rejected by the engine as `"malformed"`.

### 4.2 `src/config.py` (Configuration & Feature Flags)
* **Author / Owner:** Shared (Person A & Person B).
* **Role:** Stores all tunable gameplay constants, time limits, and feature toggles.
* **Positive Findings:**
  * Centralizes all operational constants cleanly in one file.
  * Accurately reflects tournament constraints (time banks, response timeouts, starting stacks).
* **Flaws & Weaknesses:**
  * **Widespread Dead Configuration:** Several critical constants are declared here but never imported or referenced anywhere in `src/`:
    * `VALUE_BET_EQUITY_THRESHOLD = 0.65` (never used).
    * `BLUFF_CATCH_BUFFER = 0.05` (never used).
    * `USE_OPPONENT_MODEL = True` (never used).
    * `USE_DYNAMIC_BET_SIZING = True` (never used).
    * `MONTE_CARLO_SAMPLES_DEFAULT = 100` (never used).
    * `MONTE_CARLO_SAMPLES_TURBO = 40` (never used).

### 4.3 `src/state.py` (Match & Hand State Tracker)
* **Author / Owner:** Person A.
* **Role:** Tracks stack sizes, pot sizes, bets committed, community cards, private hole cards, and public discards across streets.
* **Positive Findings:**
  * Implements clean dataclass modeling with proper factory defaults.
  * Accurately tracks street bets and pot transitions.
  * Helper `pot_odds()` correctly accounts for total pot after call: `to_call / (pot + to_call)`.
  * Helper `stack_to_pot_ratio()` accurately computes effective SPR.
* **Flaws & Weaknesses:**
  * Does not track cumulative net chips won/lost across the match.
  * Does not calculate win/loss streaks or match point standing.

### 4.4 `src/evaluator.py` (Hand Strength Evaluation)
* **Author / Owner:** Person A.
* **Role:** Computes 5-card hand rankings (categories 0–8), selects best 5-card hand from hole and board cards, and provides default discard tiebreaking.
* **Positive Findings:**
  * Faithfully replicates the official `engine.py` hand ranking logic.
  * Verified edge case correctness: wheel straight ($\text{A}\text{-}2\text{-}3\text{-}4\text{-}5$) evaluated as straight high 5; steel wheel straight flush evaluated as category 8; wrap-around hands ($\text{Q}\text{-}\text{K}\text{-}\text{A}\text{-}2\text{-}3$) correctly rejected as high card; kicker sorting verified across all categories.
  * `default_discard()` matches the tournament tiebreaking order: lowest rank, with suit tiebreak order $\spadesuit, \heartsuit, \diamondsuit, \clubsuit$.
* **Flaws & Weaknesses:**
  * **Dangerous Dummy Card Padding Bug:** Lines 85–86 state:
    ```python
    if len(all_cards) < 5:
        return rank5(all_cards + ["2s"] * (5 - len(all_cards)))
```
    If called on $<5$ cards where `all_cards` already holds `2s`, this injects duplicate cards into `rank5`, manufacturing artificial quads or full houses of deuces.
  * **Evaluation Latency:** Uses `combinations(all_cards, 5)` and Python `Counter`. Takes ~105 $\mu\text{s}$ per 7-card evaluation on modern hardware. This is 100× slower than optimized bitwise or lookup-table evaluators (~1 $\mu\text{s}$).

### 4.5 `src/equity.py` (Monte Carlo Equity Simulator)
* **Author / Owner:** Person A.
* **Role:** Estimates showdown win probability via random rollouts with dynamic time guarding.
* **Positive Findings:**
  * Clean rollout architecture with proper dead-card tracking (`VALID_CARDS` pool filtering).
  * Implements a bitwise time guard (`if (sims & 15 == 0) and time.monotonic() >= deadline: break`) to avoid timer overhead on every rollout.
* **Flaws & Weaknesses:**
  * **Completely Orphaned:** Not imported or executed anywhere in the running bot.
  * **Deadlock / Infinite Loop Hazard:** If an `opp_range` is provided where candidates collide with `known` cards, line 67 executes `continue` without incrementing `sims`. Because `(sims & 15 == 0)` is only checked when `sims` increments, if `sims == 1`, `(1 & 15 == 0)` is `False`. The deadline is never checked again, hanging the bot in a tight loop until the engine kills it.
  * **Massive Redundant Computations on River:** On the river, the board is fixed (5 cards). The player's made hand never changes. However, inside the simulation loop, `compare_hands(my_cards, opp_holding, full_board)` re-evaluates `best_hand(my_cards, full_board)` on *every single rollout*, wasting 50% of CPU cycles.
  * **Incompatible with Pre-Discard Flop:** `estimate()` assumes `my_cards` is 2 cards. Pre-discard flop requires evaluating 3 hole cards, which `estimate()` cannot handle.

### 4.6 `src/discard.py` (Flop Discard Engine)
* **Author / Owner:** Person B.
* **Role:** Chooses 1 card to discard from 3 hole cards upon receiving `discard_request`.
* **Positive Findings:**
  * Guaranteed to return a card from `hole_cards`.
  * Simple, robust fallback to `default_discard` if scoring fails.
* **Flaws & Weaknesses:**
  * **Completely Blind to Draws (Strategic Disaster):** Evaluates only the 5-card made hand on the flop (`score = best_hand(retained, board)`). It has zero understanding of 4-card flush draws, straight draws, or backdoor equity.
  * *Empirical Proof:* Holding $\text{A}\heartsuit\text{K}\heartsuit\text{2}\clubsuit$ on a $\text{Q}\heartsuit\text{J}\heartsuit\text{2}\diamondsuit$ flop, the bot discards $\text{K}\heartsuit$ to preserve bottom pair deuces ($\text{A}\heartsuit\text{2}\clubsuit$ makes category 1), discarding the Royal Flush draw and open-ended straight draw ($\text{A}\heartsuit\text{K}\heartsuit$ is category 0).
  * **Arbitrary Tiebreaking:** When made hand scores tie across candidates (e.g. board plays or no card connects), line 45 (`if score > best_retained_score:`) retains the very first card evaluated, discarding arbitrarily without evaluating kickers, suits, or blockers.

### 4.7 `src/betting.py` (Betting Decision Engine)
* **Author / Owner:** Person B.
* **Role:** Determines legal action (`check`, `call`, `raise`, `fold`) and raise sizing across all streets.
* **Positive Findings:**
  * Implements preflop canonical equity lookup and pot odds calculations.
  * Raise sizing formula `calculate_raise_amount` cleanly scales with pot size and respects `min_raise` and `max_raise` bounds.
* **Flaws & Weaknesses:**
  * **Zero Postflop Betting (100% Passive Calling Station):** Postflop logic consists solely of:
    ```python
    if "check" in legal_actions: return {"type": "action", "action": "check"}
    if "call" in legal_actions:  return {"type": "action", "action": "call"}
    if "fold" in legal_actions:  return {"type": "action", "action": "fold"}
```
    The bot **never raises or bets postflop**. It never value bets, bluffs, or protects made hands.
  * **Dead Postflop Fold Branch:** Because `call` is always legal when facing a bet, line 125 (`if "fold" in legal_actions`) is unreachable. The bot **never folds postflop**. It calls down all-in shoves on the river with 7-high.
  * **Extreme Big Blind Preflop Over-Defense:** Compares hand equity against a random hand. Against a standard min-raise from 2 to 6 chips (pot odds 33.3%), the bot defends 99.43% of its range, calling with hands as weak as 7-4-2 rainbow.

### 4.8 `src/preflop_table.py` (Precomputed Canonical Equity & Pot-Odds)
* **Author / Owner:** Person B.
* **Role:** Maps any 3 cards to canonical isomorphism classes and loads precomputed equity from `preflop_equity.npz`.
* **Positive Findings:**
  * Isomorphism mapping is mathematically complete: all 22,100 possible 3-card combinations in a 52-card deck map cleanly to the 1,755 canonical keys with **0 missing keys**.
  * Table lookups are instantaneous ($O(1)$ in-memory hash table).
* **Flaws & Weaknesses:**
  * **Catastrophic Heuristic Fallback:** If `preflop_equity.npz` fails to load, `_heuristic_equity()` is called. Line 110 assigns 0.78 (78% equity) to any trips holding. In Discard Hold'em, trips deuces ($2\spadesuit 2\heartsuit 2\diamondsuit$) has only 31.9% true equity (because 1 deuce must be discarded and only 1 remains in the deck). The fallback would aggressively 3-bet the worst hand in the game.
  * **Packaging Vulnerability:** If the tournament filesystem restricts binary reads or `.npz` archive unpacking, the bot reverts to the flawed heuristic.

### 4.9 `src/opponent_model.py` (Opponent Modeling & Range Tracking)
* **Author / Owner:** Person B.
* **Role:** Tracks opponent preflop frequencies (VPIP, PFR) and historical showdown holdings.
* **Positive Findings:**
  * Correctly identifies VPIP and PFR actions from hand history.
* **Flaws & Weaknesses:**
  * **Completely Unused:** The class is instantiated, but its methods and metrics are never queried by `betting.py` or `discard.py`.
  * **Incomplete Metric Tracking:** Fields `folds_to_raise` and `raises_faced` are initialized but never updated in `on_hand_result()`.
  * `sample_range()` returns uniform random cards from the deck with no range filtering.

---

## 5. Protocol and Rule Compliance

### 5.1 Verification Checklist

| Protocol Requirement | Rulebook / Spec Ref | Current Code Status | Technical Verification / Evidence |
| :--- | :--- | :---: | :--- |
| **Python 3.11 Environment** | Rulebook §5.1 | **PASS** | Verified running cleanly under Python 3.11.9 (`pokerBot.venv`). |
| **Allowed Libraries Only** | Rulebook §5.2 | **PASS** | AST static analysis in `tools/package.py` verified imports are standard library and `numpy` only. |
| **Max 5.0 MB Archive Size** | Rulebook §5.10 | **PASS** | `submission.zip` weighs 23,168 bytes (0.022 MB), far below 5 MB. |
| **Strict JSON on stdout** | Protocol §2, Rulebook §5.8 | **PASS** | All stdout emissions use `json.dumps(..., separators=(',', ':'))`. Zero debug prints to stdout. |
| **Flushed stdout Lines** | Protocol §2 | **PASS** | Verified `flush=True` on line 135 of `bot.py`. |
| **Stderr Capped at 64 KB** | Protocol §2, Rulebook §5.8 | **PASS** | `log_debug` enforces strict safety cap at `MAX_STDERR_BYTES = 50_000` bytes. |
| **Hand Event Handling** | Protocol §4 | **PASS** | Handles `init`, `new_hand`, `action_request`, `discard_request`, `discard_result`, `hand_result`, `notice`, `match_end`. |
| **Forward Compatibility** | Protocol §2 | **PASS** | Unrecognized message types ignored safely via `else: continue`. |
| **Legal Discard Execution** | Protocol §6.2, Rulebook §4.4 | **PARTIAL** | Normal discards return valid card; however, empty hole cards trigger unhandled `ValueError` crash. |
| **Legal Action Bounding** | Protocol §6.1, Rulebook §4.7 | **PASS** | Raises strictly clamped to `[min_raise, max_raise]`; 4-raise cap checked via `raises_left > 0`. |
| **Read-Only Filesystem** | Rulebook §5.4 | **PASS** | Bot performs no write operations, socket connections, or subprocess launches at runtime. |

---

## 6. Poker Logic and Correctness

### 6.1 Hand Evaluator Verification
We subjected `evaluator.py` to rigorous automated edge case verification against official rules:
* **Wheel Straight ($\text{A}\text{-}2\text{-}3\text{-}4\text{-}5$):** Evaluated as category 4 with high rank 5. Verified lower than a 6-high straight ($\text{score}(5) < \text{score}(6)$).
* **Steel Wheel Straight Flush ($\text{A}\heartsuit\text{-}2\heartsuit\text{-}3\heartsuit\text{-}4\heartsuit\text{-}5\heartsuit$):** Evaluated as category 8 (Straight Flush) with high rank 5. Verified beating a King-high flush.
* **Wrap-around Straights ($\text{Q}\text{-}\text{K}\text{-}\text{A}\text{-}2\text{-}3$):** Correctly rejected; evaluated as category 0 (High Card).
* **Kicker Tiebreakers:** Verified for Two Pair ($\text{AAKKQ} > \text{AAKKJ}$), Full House ($\text{88822} > \text{777AA}$), Flush ($\text{AKQJ9} > \text{AKQJ8}$), and Four of a Kind ($\text{AAAAK} > \text{AAAAQ}$).

### 6.2 Preflop Isomorphism Table Verification
* Total possible 3-card combinations in a 52-card deck: $\binom{52}{3} = 22,100$.
* Number of canonical equivalence classes:
  $$\text{Trips: } 13 \quad | \quad \text{Pair + Kicker: } 312 \quad | \quad \text{Distinct Ranks: } 1,430 \quad \Longrightarrow \quad \mathbf{1,755 \text{ keys}}.$$
* **Empirical Test:** We executed a complete verification script mapping all 22,100 combinations through `canonical_3card()`.
  * **Result:** **1,755 keys present, exactly 0 missing keys**. Every possible 3-card hand in Discard Hold'em resolves cleanly.

### 6.3 Discard Logic Failures
The Discard Hold'em game mechanic requires keeping the 2 hole cards that maximize expected value across future streets. Because `discard.py` evaluates only the immediate made hand on the flop, it suffers from severe systemic failures:
1. **Sacrificing Premium Draws for Marginal Pairs:**
   * Hand: $\text{A}\heartsuit\text{K}\heartsuit\text{2}\clubsuit$ on Flop $\text{Q}\heartsuit\text{J}\heartsuit\text{2}\diamondsuit$.
   * Holding $\text{A}\heartsuit\text{K}\heartsuit$ offers a 12-out mega-draw (Royal Flush + nut flush + open-ended straight), boasting $>65\%$ equity against top pairs.
   * Bot discards $\text{K}\heartsuit$, keeping $\text{A}\heartsuit\text{2}\clubsuit$ for bottom pair deuces.
2. **Discarding Board Connectors on Paired Flops:**
   * When holding high cards with backdoor draws and no made pair, the bot discards cards that would provide backdoor nut flush potential because it treats all non-pairing cards identically.

---

## 7. Strategic Strengths

1. **Precomputed Preflop Equity Architecture:**
   * Compressing all 22,100 3-card starting hands into a 1,755-key canonical `.npz` table is mathematically optimal. It grants the bot immediate $O(1)$ access to high-precision preflop equities without spending a single millisecond of its time bank.
2. **Clean Protocol Separation and Stderr Bounding:**
   * Isolating engine communication to `bot.py` and strictly bounding debug output to `MAX_STDERR_BYTES = 50_000` prevents the catastrophic stdout pollution and stderr overflow penalties that frequently disqualify hackathon teams.
3. **Automated Submission Packaging and AST Verification:**
   * The developer tool `tools/package.py` parses file ASTs to enforce the competition import sandbox (`stdlib`, `numpy`, `scipy` only) and runs a 2-hand smoke test against `engine.py`. This guarantees zero packaging defects upon upload.
4. **Clean Duplicate Deal Exploitation Potential:**
   * Stacks reset to 200 chips every hand, and seats alternate every hand in duplicate deals. The bot's state tracking cleanly resets on `new_hand`, ensuring zero state pollution across duplicate boards.
5. **Robust Raise Sizing Math:**
   * `calculate_raise_amount` correctly scales bets as a percentage of the total pot while rigorously enforcing `min_raise` and `max_raise` all-in clamps.

---

## 8. Strategic Weaknesses

1. **100% Passive Calling Station Postflop:**
   * The bot **never bets or raises postflop**. It never extracts value when holding monsters (flushes, full houses, quads), and it never folds to opponent bets. A human or bot betting 75% pot with good hands and checking marginal hands will extract maximum chips every time.
2. **Inability to Fold Postflop (Infinite Bleed):**
   * The postflop code path cannot fold (`if 'call' in legal_actions:` precedes `if 'fold' in legal_actions:`). It will call all-in bets on turn and river with bottom pair or high card.
3. **Draw-Blind Flop Discard Engine:**
   * The discard selector has no heuristic or simulation for draws. It routinely throws away flush draws and straight draws to keep worthless bottom pairs.
4. **Extreme Preflop Defending Range (99.43% Defense vs Min-Raise):**
   * Comparing private hand equity against a uniform random distribution leads the bot to believe every hand has $\ge 30.87\%$ equity. Facing a min-raise, it defends 99.43% of its range, entering postflop out of position with unplayable holdings.
5. **Ultra-Passive Button Opening (Surrendering Positional Advantage):**
   * On the button, the bot open-raises only 29.9% of hands, limps 58.8%, and folds 11.3%. In heads-up poker, the button acts last on every postflop street. Limping 58.8% gives the Big Blind a free flop and wastes the single greatest strategic asset in heads-up play.

---

## 9. Performance and Runtime Assessment

### 9.1 Time Bank Constraints & Budgeting
* **Stage 1:** 60.0 seconds for 400 hands $\implies$ **150 ms average per hand**.
* **Stage 2:** 150.0 seconds for 1,000 hands $\implies$ **150 ms average per hand**.
* **Decision Budget:** A hand lasting 4 streets typically involves 3 to 6 action/discard requests. The bot must average **$\le 25\text{ ms}$ per decision request**.

### 9.2 Measured Component Latency
We empirically profiled the core operations under Python 3.11:

| Operation | Measured Latency | Assessment vs Budget |
| :--- | :---: | :--- |
| `preflop_table.get_preflop_equity` | **$0.002\text{ ms}$** ($2\ \mu\text{s}$) | **Flawless.** Instantaneous $O(1)$ dict lookup. |
| `evaluator.best_hand` (7 cards) | **$0.105\text{ ms}$** ($105\ \mu\text{s}$) | **Slow.** Uses `combinations(7, 5)` + `Counter`. |
| `discard.choose` (3 candidates) | **$0.315\text{ ms}$** ($315\ \mu\text{s}$) | **Fast.** Evaluates 3 hands on 5-card board. |
| `equity.estimate` (100 sims, flop) | **$22.12\text{ ms}$** | **High Risk.** On 1 vCPU, this will take $50\text{--}70\text{ ms}$. |
| `equity.estimate` (100 sims, river) | **$22.04\text{ ms}$** | **High Risk.** 50% CPU wasted re-evaluating player hand. |

### 9.3 Performance Conclusions
* The bot currently uses **0.00 seconds** of its time bank across an entire 400-hand match solely because **postflop equity calculation is completely disconnected**.
* If `equity.estimate` is plugged directly into `betting.py` without optimization, the bot will consume $50\text{--}70\text{ ms}$ per decision on 1 vCPU, rapidly exhausting its 60-second time bank in deep matches and suffering an immediate **forfeit loss**.
* To utilize Monte Carlo postflop equity, the hand evaluator must be accelerated (e.g., using a lookup table or fast integer bitwise evaluation) to achieve $<1\ \mu\text{s}$ per evaluation.

---

## 10. Testing Coverage and Missing Tests

### 10.1 Existing Test Suite
* **Unit Tests:** **0 tests.** There are literally no test files (`test_*.py`) anywhere in the repository.
* **Harness Tools:**
  * `tools/bench.py`: Successfully runs matches between bots across random seeds and parses scores.
  * `tools/package.py`: Runs a 2-hand smoke test against `opponents/random_bot.py`.
* **Empirical Execution During Audit:**
  * Ran 20 hands vs `random_bot.py`: **Won +55 chips** (0 notices, 0 crashes).
  * Ran 20 hands vs `always_raise.py`: **Won +15 chips** (0 notices, 0 crashes).
  * Ran 20 hands vs `always_call.py`: **Won +7 chips** (0 notices, 0 crashes).
  * Ran 20 hands vs `tight_folder.py`: **Won +5 chips** (0 notices, 0 crashes).
  * Ran 2 matches $\times$ 50 hands via `bench.py`: **2 Wins, 0 Losses, Net +62 chips**.

### 10.2 Critical Missing Tests
1. **Evaluator Edge Case Tests:** No unit tests verifying straight flushes, low-ace wheels, quad kickers, or full house hierarchy.
2. **Discard Scenario Tests:** No tests validating that the bot keeps flush draws, straight draws, or pairs over trash.
3. **Betting Logic Regression Tests:** No tests verifying that the bot raises for value, folds to excessive bets, or sizes bets properly.
4. **Protocol Fuzzing Tests:** No tests injecting malformed messages, empty card lists, or missing fields to test exception handling.
5. **Opponent Exploit Tests:** No simulations against aggressive bots, value-betting bots, or maniac bots.

---

## 11. Critical Bugs and Risks

### 11.1 Verified Bugs (Empirically Confirmed)

#### Bug 1: Crash-to-Forfeit on Malformed Discard Request (P0 — Critical)
* **Location:** `src/bot.py`, line 89 (`handle_discard_request`) & `src/evaluator.py`, line 103 (`default_discard`).
* **Mechanism:**
  ```python
  # bot.py
  except Exception as err:
      fallback_card = default_discard(hole_cards)
      return {"type": "discard", "card": fallback_card}
```
  If `hole_cards` is empty `[]` or missing from the engine message:
  ```python
  # evaluator.py
  def default_discard(hole: Sequence[str]) -> str:
      return min(hole, key=lambda c: (RANK_VALUE[c[0]], SUIT_ORDER[c[1]]))
```
  `min([])` raises `ValueError: min() arg is an empty sequence`.
* **Impact:** The exception escapes `handle_discard_request` to `main()`, which exits with code 1. The engine detects process death and issues an **immediate match forfeit** ($\Delta = -C$).
* **Verification:** Confirmed via standalone execution of `bot.handle_discard_request({'type': 'discard_request', 'hole_cards': []}, state, opp)`.

#### Bug 2: Unshielded State Updates in IPC Event Loop (P0 — Critical)
* **Location:** `src/bot.py`, lines 116–126.
* **Mechanism:**
  ```python
  elif msg_type == "new_hand":
      state.on_new_hand(msg)
  elif msg_type == "hand_result":
      state.on_hand_result(msg, opp_model)
```
  Unlike `handle_action_request` and `handle_discard_request`, these state update dispatches are not wrapped in a `try/except` block.
* **Impact:** Any unexpected field type, missing key, or internal state corruption causes an unhandled crash to `main()`, forfeiting the match.

#### Bug 3: Dead Postflop Fold Logic / Passive Calling Station (P0 — Critical Strategy)
* **Location:** `src/betting.py`, lines 119–126.
* **Mechanism:**
  ```python
  if "check" in legal_actions: return {"type": "action", "action": "check"}
  if "call" in legal_actions:  return {"type": "action", "action": "call"}
  if "fold" in legal_actions:  return {"type": "action", "action": "fold"}
```
  In poker, whenever facing a bet, calling is always legal. Therefore, `if "call" in legal_actions:` evaluates to `True` on 100% of postflop bets. Line 125 (`return fold`) is unreachable dead code.
* **Impact:** The bot never folds postflop and never bets postflop. It calls down 200-chip shoves with 7-high.

#### Bug 4: Draw-Blind Discard Engine (P1 — High Strategy)
* **Location:** `src/discard.py`, lines 41–48.
* **Mechanism:** Evaluates only `score = best_hand(retained, board)`. Because the flop has only 3 cards, this evaluates only the 5-card made hand on the flop, completely ignoring draw equity.
* **Impact:** The bot discards nut flush draws and open-ended straight draws to hold bottom pairs.

#### Bug 5: Dummy Card Padding in Hand Evaluator (P1 — High)
* **Location:** `src/evaluator.py`, lines 85–86.
* **Mechanism:**
  ```python
  if len(all_cards) < 5:
      return rank5(all_cards + ["2s"] * (5 - len(all_cards)))
```
  Pads with `"2s"`. If `all_cards` already contains `"2s"`, duplicate deuces are counted, generating fake quads or full houses.

#### Bug 6: Inverted Preflop Heuristic for Trips (P1 — High)
* **Location:** `src/preflop_table.py`, line 111.
* **Mechanism:** `if counts[0][1] == 3: return 0.78`.
* **Impact:** If `preflop_equity.npz` fails to load, trips deuces ($2\spadesuit 2\heartsuit 2\diamondsuit$) is assigned 78% equity and 3-bet aggressively, when its true Discard Hold'em equity is only 31.9%.

---

## 12. Prioritized Improvement Roadmap

### Summary Priority Table

| Priority | Issue Description | File(s) Affected | Impact | Recommended Technical Action |
| :---: | :--- | :--- | :--- | :--- |
| **P0** | Crash on empty discard request | `src/bot.py`, `src/evaluator.py` | Fatal match forfeit | Guard `hole_cards` before calling `min()`; return `"2s"` or fallback safely. |
| **P0** | Unshielded state event loop | `src/bot.py` | Fatal match forfeit | Wrap entire loop body in `try/except Exception` shield. |
| **P0** | Postflop calling station / zero betting | `src/betting.py` | Massive chip bleed | Implement postflop equity threshold betting (value bet, bluff-catch, fold). |
| **P1** | Draw-blind flop discard logic | `src/discard.py` | Breaks monster draws | Score 4-flushes, open-ended straights, and gutshots with draw bonus points. |
| **P1** | Hand evaluator dummy padding bug | `src/evaluator.py` | Corrupted hand ranks | Reject $<5$ cards or pad with unique unused cards outside the deck. |
| **P1** | Excessive Big Blind preflop defense | `src/betting.py`, `src/config.py` | Calls trash OOP | Discount preflop equity against raising ranges; fold bottom 40% vs raises. |
| **P1** | Ultra-passive button open strategy | `src/betting.py`, `src/config.py` | Surrenders button EV | Lower `PREFLOP_OPEN_EQUITY` from 0.54 to 0.44; open-raise 70%+ from button. |
| **P2** | Slow hand evaluator ($105\ \mu\text{s}$) | `src/evaluator.py` | Prevents MC rollouts | Implement Cactus Kev or 2+2 lookup table evaluator ($<1\ \mu\text{s}$). |
| **P2** | Disconnected equity module | `src/equity.py` | Wasted capability | Optimize river/turn evaluation and connect to `betting.py`. |
| **P2** | Disconnected opponent model | `src/opponent_model.py` | Zero adaptation | Use observed VPIP/PFR to adjust calling thresholds vs loose/tight opponents. |
| **P2** | Redundant river evaluations in MC | `src/equity.py` | Wastes 50% CPU cycles | Pre-compute player made hand score outside the simulation loop. |
| **P3** | Clean up dead configuration keys | `src/config.py` | Maintainability | Connect or prune unused thresholds and flags. |
| **P3** | Add comprehensive unit test suite | `tests/` (new) | Prevents regressions | Implement pytest suite covering evaluators, discards, and betting rules. |

---

### Detailed Action Items

#### Item 1: Fix Discard Fallback Crash (P0)
1. **Affected File & Function:** `src/bot.py`, `handle_discard_request()` (lines 86–91) and `src/evaluator.py`, `default_discard()` (line 101).
2. **Problem:** `default_discard([])` calls `min([])`, throwing `ValueError` and crashing the process.
3. **Why it matters:** An unexpected engine payload causes an instant match forfeit ($\Delta = -C$).
4. **Proposed Solution:** In `bot.py`:
   ```python
   except Exception as err:
       log_debug(f"Discard fallback triggered: {err}")
       if hole_cards:
           fallback_card = default_discard(hole_cards)
       else:
           fallback_card = "2s"
       return {"type": "discard", "card": fallback_card}
```
5. **How to Test:** Invoke `handle_discard_request({'type': 'discard_request', 'hole_cards': []}, state, opp)` and verify it cleanly returns `{"type": "discard", "card": "2s"}` without crashing.
6. **Difficulty:** Trivial (5 minutes).

#### Item 2: Wrap Event Loop in Top-Level Safety Shield (P0)
1. **Affected File & Function:** `src/bot.py`, `run_bot()` (lines 98–137).
2. **Problem:** Engine events `new_hand`, `hand_result`, `discard_result`, `init`, and `notice` execute without exception handling.
3. **Why it matters:** Any malformed string or unexpected key crashes the process.
4. **Proposed Solution:** Wrap the inner processing block of `run_bot()` in a generic `try/except Exception as exc:` block that logs to `log_debug` and continues to the next line.
5. **How to Test:** Feed corrupted JSON and unexpected event types to `bot.py` via stdin; verify the bot stays alive.
6. **Difficulty:** Trivial (10 minutes).

#### Item 3: Implement Postflop Value Betting, Bluff-Catching, and Folding (P0)
1. **Affected File & Function:** `src/betting.py`, `decide()` (lines 116–128).
2. **Problem:** Postflop logic unconditionally checks if free and calls if facing a bet. It never bets or folds.
3. **Why it matters:** Any bot that bets for value will drain all 200 chips from this bot every hand.
4. **Proposed Solution:**
   * Calculate effective hand strength or call `equity.estimate` (or a fast made-hand heuristic):
     * If `to_call == 0`: If hand strength $\ge 0.65$ and `can_raise`, bet $60\%$ pot. Otherwise `check`.
     * If `to_call > 0`: Compute `pot_odds = to_call / (pot + to_call)`. If hand strength $\ge (\text{pot\_odds} + 0.05)$, `call`. Otherwise `fold`.
5. **How to Test:** Run a benchmark against a test bot that bets large; verify that the bot folds weak hands postflop and bets strong hands.
6. **Difficulty:** Medium (1–2 hours).

#### Item 4: Implement Draw Potential in Discard Selection (P1)
1. **Affected File & Function:** `src/discard.py`, `choose()` (lines 36–52).
2. **Problem:** Evaluates only the 5-card made hand on the flop, ignoring flush and straight draws.
3. **Why it matters:** Throws away monster draws with $>50\%$ equity to keep bottom pairs.
4. **Proposed Solution:** In `discard.py`, augment the candidate holding evaluation:
   ```python
   score = best_hand(retained, board)
   # Bonus for flush draw (4 cards of same suit)
   suits = [c[1] for c in retained + board]
   flush_draw = max(Counter(suits).values()) == 4
   # Bonus for open-ended straight draw (8 outs)
   ...
   candidate_value = score_tuple + (1.5 if flush_draw else 0.0) + (1.0 if oesd else 0.0)
```
5. **How to Test:** Run our verified test case ($\text{A}\heartsuit\text{K}\heartsuit\text{2}\clubsuit$ on $\text{Q}\heartsuit\text{J}\heartsuit\text{2}\diamondsuit$); verify that the bot discards $\text{2}\clubsuit$ and retains $\text{A}\heartsuit\text{K}\heartsuit$.
6. **Difficulty:** Medium (1–2 hours).

#### Item 5: Rebalance Preflop Raising & Defending Thresholds (P1)
1. **Affected File & Function:** `src/config.py` & `src/betting.py`.
2. **Problem:** Button open-raises only 29.9% (limps 58.8%); Big Blind calls 99.43% against min-raises.
3. **Why it matters:** Severe chip bleed out of position; failure to exploit button positional advantage.
4. **Proposed Solution:**
   * In `config.py`:
     * Set `PREFLOP_OPEN_EQUITY = 0.46` (raises ~65–70% of button hands).
     * Set `PREFLOP_LIMP_EQUITY = 0.38` (limps 15%, folds worst 15%).
   * In `betting.py`, discount equity when facing a raise:
     ```python
     # Opponent open range is strong, so discount random-hand equity
     realized_equity = equity * 0.82
     if realized_equity >= pot_odds:
         return {"type": "action", "action": "call"}
```
5. **How to Test:** Check opening percentages using the table distribution script; verify button open-raise rate is $>65\%$.
6. **Difficulty:** Easy (30 minutes).

---

## 13. Competitive Potential

### 13.1 Realistic Assessment of Current Bot
In its current state, this bot will finish in the **lower quartile (bottom 25%)** of a competitive collegiate tournament.
* **Why it beats starter bots:** It dominates primitive baseline bots (`random_bot`, `always_call`, `tight_folder`) because its preflop equity table ensures it enters pots with better starting cards.
* **Why it will lose to competitive bots:** Any intermediate team with a basic postflop strategy (e.g. continuation betting 50% pot with top pair or better, folding missed hands) will win almost every chip against this bot. Because this bot never bets postflop, opponents see turns and rivers for free. Because this bot never folds postflop, opponents will size up to full pot on the river with made hands and extract full value.

### 13.2 Evaluation of Advanced Algorithms (CFR / MCCFR)
* **Is CFR / MCCFR Realistic?** **No, do not attempt CFR.**
  * Counterfactual Regret Minimization (CFR) requires abstracting the game state, solving the extensive-form game tree over millions of iterations, and managing massive strategy lookup files within the 5.0 MB zip limit.
  * Discard Hold'em has private cards dealt before and after flop betting, with simultaneous exposed discard mechanics. Standard heads-up Hold'em CFR abstractions cannot be reused directly without extensive game-tree re-engineering.
  * For a two-member first-year student team with days remaining before the deadline, attempting CFR would be a catastrophic time sink with near-certain failure.
* **What to Implement Instead:**
  1. Fast rule-based postflop heuristics (made hand tiers + pot odds).
  2. Draw-aware discard evaluation.
  3. Optimized Monte Carlo rollouts (30–50 samples using an accelerated hand evaluator).
  4. Exploitative opponent tracking (detecting whether the opponent folds to c-bets or calls down light).

---

## 14. Recommended Development Plan for a Two-Member Team

### Workload Split for Days 1–3

```
┌────────────────────────────────────────────────────────────────────────┐
│                   PERSON A: Evaluator & Reliability                    │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Fix crash bugs in bot.py (discard fallback & event loop shield).    │
│ 2. Fix dummy card padding bug in evaluator.py.                         │
│ 3. Build a comprehensive unit test suite in tests/test_evaluator.py.   │
│ 4. Optimize hand evaluation (vectorize or use lookup table for <5 us). │
│ 5. Optimize equity.py (precompute player hand on river).               │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  PERSON B: Strategy & Decision Logic                   │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Upgrade discard.py with flush/straight draw bonuses.                │
│ 2. Rewrite postflop betting.py (value betting, bluff-catching, folding)│
│ 3. Rebalance preflop thresholds (open 70% on button, fold trash in BB) │
│ 4. Connect opponent_model.py to adapt bet sizing vs passive/aggressive.│
│ 5. Run tools/bench.py across 500-hand matches to tune win rates.       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 15. Questions and Missing Information

1. **Read-Only Filesystem Mechanics:** Does the official evaluation environment permit reading static binary files (like `preflop_equity.npz`) packaged inside the submission zip?
   * *Mitigation:* `tools/package.py` packages `preflop_equity.npz` directly. However, having an in-code Python table or fallback ensures safety if file reading is blocked by sandbox seccomp filters.
2. **Time Bank Jitter on 1 vCPU:** How strictly is the 60-second time bank measured on the competition server?
   * *Mitigation:* Keep per-decision latency well under $15\text{ ms}$ to maintain a safety cushion against CPU throttling.
3. **Engine Notice Thresholds:** Does the tournament server enforce a penalty or forfeit if a bot accumulates excessive notices (e.g. $>10$ illegal actions corrected)?
   * *Mitigation:* Ensure all actions and discards are 100% legal before sending to stdout.

---

## 16. Summary Tables & Core Takeaways

### The 5 Strongest Aspects of the Bot
1. **$O(1)$ Canonical Preflop Equity Table:** Flawlessly maps all 22,100 3-card hands to 1,755 keys with zero missing entries.
2. **Strict Protocol & Stderr Hygiene:** Pure JSON communication with automatic stdout flushing and a 50 KB stderr cap preventing disqualification.
3. **Automated Submission Pipeline (`package.py`):** Static AST import inspection, size validation ($<5\text{ MB}$), and automated 2-hand smoke test.
4. **Accurate 5-Card Hand Evaluator:** Exact rank ordering and tiebreaking matching the official tournament engine.
5. **Clean Modular Architecture:** Clear division between state tracking, evaluation, strategy, and IPC protocol.

### The 5 Biggest Weaknesses
1. **Zero Postflop Betting Engine:** Checks every hand and calls every bet; never bets for value; never folds postflop.
2. **Draw-Blind Flop Discard Engine:** Evaluates made hands only; discards nut flush and straight draws to keep bottom pairs.
3. **Crash Bug on Empty Discard:** `default_discard([])` crashes with `ValueError`, causing immediate match forfeit.
4. **Massive Big Blind Preflop Over-Defense:** Defends 99.43% of hands against preflop min-raises, bleeding chips out of position.
5. **Orphaned Equity and Opponent Modules:** `equity.py` and `opponent_model.py` are completely disconnected dead code.

### The 5 Most Valuable Improvements to Implement Next
1. **Postflop Betting & Folding:** Implement equity/strength threshold betting (value bet strong hands, fold weak hands facing bets).
2. **Draw Bonus in Discard:** Add flush/straight draw bonus scoring to `discard.py` so the bot retains high-equity draws.
3. **Crash Shields in `bot.py`:** Guard `default_discard` against empty lists and wrap the stdin event loop in `try/except`.
4. **Button & Big Blind Preflop Rebalancing:** Open-raise 70% from the button; discount equity against raises to fold the bottom 40% in the Big Blind.
5. **Connect Opponent Model:** Adjust calling and folding thresholds dynamically based on opponent VPIP and aggression.

### Recommended Order of Implementation
1. **Step 1 (Reliability):** Fix the discard fallback crash and wrap the event loop in `bot.py` (P0).
2. **Step 2 (Strategy Core):** Rewrite postflop logic in `betting.py` to allow value betting and folding (P0).
3. **Step 3 (Discard Intelligence):** Add draw scoring to `discard.py` (P1).
4. **Step 4 (Preflop Rebalancing):** Adjust button open-raise and BB defense thresholds in `config.py` and `betting.py` (P1).
5. **Step 5 (Opponent Exploitation):** Wire up `opponent_model.py` to adjust thresholds vs maniacs and calling stations (P2).

---

## 17. Final Concise Verdict

> **If this bot were submitted in its current state, what would concern you most, and what should we fix first?**
>
> **What concerns me most:**  
> The bot has **zero postflop betting logic**. It operates as a 100% passive calling station on the flop, turn, and river: it **never bets or raises** (even with a Royal Flush), and it **never folds** (calling 200-chip all-in shoves with 7-high). Any competent competitor will exploit this immediately to win maximum chips.
>
> **What you should fix first:**  
> 1. **Immediate Crash Fix:** In `bot.py` (`handle_discard_request`), ensure `hole_cards` is non-empty before calling `default_discard()` to eliminate the instant-forfeit crash bug.  
> 2. **Postflop Folding & Betting:** In `betting.py`, replace the passive check/call skeleton with a basic threshold rule: value bet strong hands ($\ge \text{top pair}$) and fold trash when facing bets larger than your pot odds. That single change will instantly transform the bot from a free target into a competitive contender.
