# AGENTS.md — Antigravity AI Agent Guidelines

This document defines the strict system prompt, code architecture standards, and safety invariants for any **Antigravity AI Agent** working within this repository.

---

## 🤖 Master System Prompt for Antigravity AI

```markdown
You are an expert AI software engineer developing a Pokerbot for the "Discard Hold'em" competition in Python 3.11.

HARD CONSTRAINTS & COMPLIANCE RULES:
1. Environment & Dependencies:
   - Use Python 3.11 with standard library, `numpy`, and `scipy` ONLY.
   - Do not import any non-standard third-party libraries.
2. I/O Protocol Discipline:
   - Read UTF-8 JSON line messages from `sys.stdin`.
   - Reply ONLY to `action_request` and `discard_request` messages.
   - Write ONLY valid JSON reply objects to `sys.stdout`.
   - ALWAYS flush output immediately: `print(json.dumps(reply), flush=True)`.
   - Redirect all debug output to `sys.stderr`. NEVER call plain `print()` or output non-JSON text to `stdout`.
3. Action & Discard Safety:
   - Validate that returned actions belong to `legal_actions`.
   - Ensure `raise` amounts are integers between `min_raise` and `max_raise`.
   - Ensure the discarded card is present in the current 3 hole cards.
   - Implement fallbacks: `check` if legal, else `fold`; discard lowest-ranked card on error.
4. Time Bank Management:
   - Target decision latency < 15ms per request to conserve the 60s/150s cumulative time bank.
```

---

## 🚫 Critical Code Invariants (Do Not Break)

### 1. `stdout` Integrity
`stdout` is the raw IPC protocol pipe connected directly to the authoritative match engine.
- ❌ **NEVER write standard `print("debug log")` statements.**
- ✅ **ALWAYS route logs to `sys.stderr`:**
  ```python
  import sys
  print("[DEBUG] Hand state updated", file=sys.stderr)
  ```

### 2. Immediate Output Flushing
Unflushed responses stay in the stdout buffer and will cause a 5-second timeout forfeit.
- ✅ **ALWAYS pass `flush=True` when replying:**
  ```python
  import sys, json
  print(json.dumps(reply_dict), flush=True)
  ```

### 3. Action Boundary Guarding
Engine notices and forfeits occur if an illegal action or out-of-bound raise is emitted.
- ✅ **ALWAYS validate in `core/safety.py` before sending:**
  - Check if action is in `req["legal_actions"]`.
  - For raises: `min_raise <= amount <= max_raise`.
  - For discards: `card in req["hole_cards"]`.

### 4. Dependency Sandbox
- ✅ Allowed: `import sys, json, math, random, time, numpy, scipy`
- ❌ Forbidden: `requests`, `pandas`, `sklearn`, `torch`, `cython`, or any external package.

---

## 🛠 File Ownership & Scope Boundaries

To ensure safe collaboration between team members and their AI agents:

| Module Path | Owner | Primary Responsibility | Agent Constraints |
| :--- | :--- | :--- | :--- |
| `bot.py` | Shared | Main entry point & event loop | Keep lightweight; delegate to `core/` and `strategy/`. |
| `core/protocol.py` | Member 1 | JSON parsing & transport | Never touch strategic evaluation. |
| `core/state.py` | Member 1 | Game state tracking | Maintain hand & pot state accurately across requests. |
| `core/safety.py` | Member 1 | Action validation & fallbacks | Must never throw uncaught exceptions. |
| `strategy/evaluator.py` | Member 2 | Preflop & 5-card equity math | Use fast vectorization with `numpy`. |
| `strategy/discard.py` | Member 2 | Flop discard decision | Choose 1 card from 3 hole cards post-flop. |
| `strategy/betting.py` | Member 2 | Preflop & postflop betting logic | Generate action dict (`check`/`call`/`raise`/`fold`). |
| `tests/local_runner.py` | Member 1 | Bot-vs-Bot local match simulator | Test time usage and stdout purity. |

---

## 🧪 AI Agent Verification Checklist

Before suggesting or committing any code changes, the Antigravity agent must verify:
1. [ ] No plain `print()` statements exist in any module.
2. [ ] All JSON output calls include `flush=True`.
3. [ ] All imports are restricted to stdlib, `numpy`, and `scipy`.
4. [ ] All decision functions complete within <15ms.
5. [ ] `tests/local_runner.py` completes 400 hands without protocol error notices.
