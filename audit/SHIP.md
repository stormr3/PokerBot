# Ship-Check Report — AcesDiscard (`src/`)

**Date:** 2026-11-11  
**Target Python:** `C:\Users\Deep\AppData\Local\Programs\Python\Python311\python.exe` (`Python 3.11.9`)  
**Git Branch / Scope Note:** Attempting `git checkout -b ship-check` failed with `fatal: cannot lock ref 'refs/heads/ship-check': Permission denied` on `.git/refs/heads/`, so work was performed on branch `preflop_feature`. Only the two authorized fixes `(a)` and `(b)` were applied; all other repo files remained untouched, and all test artifacts/logs were written under `./audit/` and `%TEMP%`.

---

## Fixes Applied (Only Authorized Changes)

| Fix | Location | Change | Verification |
|---|---|---|---|
| **(a)** Bluff `can_raise` guard | [`src/postflop.py:133`](file:///c:/VSC_Projects/PokerBots/src/postflop.py#L133) | `if e < ...` → `if canr and e < (0.15 if river else 0.28) and not station:` | 200 trials in `unit_fix_a_and_b` with `legal_actions=["check"]`, `e=0.05`, `min_raise=2`, `max_raise=100` all returned `{"type":"action","action":"check"}`. |
| **(b)** Safe discard fallback on empty/malformed `hole_cards` | [`src/bot.py:26`](file:///c:/VSC_Projects/PokerBots/src/bot.py#L26), [`src/bot.py:83`](file:///c:/VSC_Projects/PokerBots/src/bot.py#L83), [`src/bot.py:89-95`](file:///c:/VSC_Projects/PokerBots/src/bot.py#L89-L95) | Imported `VALID_CARDS`; validated `card not in VALID_CARDS or card not in hole_cards`; fallback filters `(list, tuple)` elements against `VALID_CARDS`, calls `default_discard(valid_cards)` if non-empty, else returns `"2s"`. | Tested `[]`, `None`, `123`, `["XX"]`, `["XX","YY"]`, `["bad","As","3h"]` (returned `"3h"`), `[None, 42]`, `["AsXYZ"]` (returned `"2s"`): zero crashes, all valid card strings. |

---

## Summary Scorecard

| # | Check | Status | Key Measured Evidence |
|---|---|---|---|
| 1 | Upload artifact & isolated temp extraction | **PASS** *(packager caveat)* | [`audit/submission_ship.zip`](file:///c:/VSC_Projects/PokerBots/audit/submission_ship.zip) = `89,633` bytes (`0.0855 MB < 5 MB`); 20/20 hands (`notices 0`) from `%TEMP%\pb_ship_extract`; all 14 modules resolved inside `%TEMP%\pb_ship_extract`. (`tools/package.py` currently fails because `timemgr.py` is omitted from `BOT_MODULES` — left unedited.) |
| 2 | Explicit Python 3.11 & import allowlist | **PASS** | Ran with `Python 3.11.9` (`--python`); AST scan of all 14 files found **0** third-party imports (100% Python 3.11 stdlib + local modules; not even `numpy`/`scipy`). |
| 3 | Read-only filesystem + `PYTHONDONTWRITEBYTECODE=1` + static grep | **PASS** | Static regex + AST scan: **0** file-write / `open(` / `makedirs` / `tempfile` / `socket` / `subprocess` hits. Full 400-hand Stage 1 match on `icacls` read-only folder (`%TEMP%\pb_ship_ro_final`) with `PYTHONDONTWRITEBYTECODE=1`: `400/400` hands, `57.27 s / 60 s`, `notices 0`, `0` `__pycache__`, `0` B stderr. |
| 4 | Cold launch-to-ready time (no `.pyc`) | **PASS** | 5 cold `python3.11 -B` launches (`0` `.pyc` files) to first JSON reply: **min `169.5 ms`, mean `187.7 ms`, max `222.1 ms`** (vs `5000 ms` limit). |
| 5 | Stage 2 (`1000` hands, `150 s` bank) vs two opponents | **PASS** *(tight time margin)* | vs `always_call` (`seed 702`): `+26175`, **`148.60 s / 150 s`**, `notices 0`. vs `always_raise` (`seed 701`): `+28367`, **`148.82 s / 150 s`**, `notices 0`. |
| 6 | Legs format (`audit/engine_legs.py`, `200` hands, `30 s` bank, `90 s` wallclock) | **PASS** | Two fresh processes vs `always_call`: Leg 1 (`seed 801`) `+4825`, **`24.62 s / 30 s`**, `notices 0`; Leg 2 (`seed 802`) `+5150`, **`19.61 s / 30 s`**, `notices 0`. |
| 7 | Slow CPU (3 concurrent matches + 2 busy loops pinned to 2 cores) | **PASS** | Affinity mask `0x3` (2/16 logical CPUs): all 3 matches completed `400/400` hands, **0 forfeits, 0 notices**; max time used **`58.58 s / 60 s`** (`m2_raise`), `58.55 s / 60 s` (`m1_call`), `39.57 s / 60 s` (`m3_tight`). |
| 8 | Fuzz harness (protocol edge cases) | **PASS** *(non-dict JSON note)* | 32 inputs → **18/18** valid replies, **0** extra stdout bytes, **exit 0** (`0` B stderr). Valid-JSON non-dicts (`null`, `123`, `[1,2]`) crash at `bot.py:112` (unmodified outside `(a)`/`(b)` scope). |

---

## Detailed Evidence Per Check

### 1. Upload Artifact & Isolated Temp Extraction
- **Existing `tools/package.py` status (observed failure, not modified):** Running `tools/package.py` exits with code 1:
  ```
  ERROR: Forbidden imports or runtime file access detected!
    - [discard.py] Line 7: import timemgr ('timemgr' is not permitted)
    - [postflop.py] Line 8: import timemgr ('timemgr' is not permitted)
  ```
  Root cause: [`tools/package.py:28-42`](file:///c:/VSC_Projects/PokerBots/tools/package.py#L28-L42) omits `"timemgr.py"` from `BOT_MODULES`. The stale root `submission.zip` (`23,168` bytes, dated `05-11-2026`) was left untouched per the read-only constraint.
- **Built upload zip:** [`audit/submission_ship.zip`](file:///c:/VSC_Projects/PokerBots/audit/submission_ship.zip) (`89,633` bytes = `0.0855 MB < 5.0 MB`), containing all 14 `.py` modules at zip root (`bot.py` at top level):
  `bet_utils.py`, `betting.py`, `bot.py`, `config.py`, `discard.py`, `equity.py`, `evaluator.py`, `opponent_model.py`, `postflop.py`, `preflop.py`, `preflop_data.py`, `preflop_table.py`, `state.py`, `timemgr.py`.
- **Isolated execution & module resolution:** Extracted to `C:\Users\Deep\AppData\Local\Temp\pb_ship_extract` (outside workspace).
  - Match run (`engine.py` vs `opponents/random_bot.py`, `--hands 20 --seed 42 --python python3.11`): `20 of 20 hands played`, `net +32`, `notices 0`, `A_stderr.txt` = `0` bytes (`audit/logs_ship_check1_final/`).
  - Importing `bot` from `cwd=pb_ship_extract` confirmed all 14 loaded workspace/local modules resolved strictly under `C:\Users\Deep\AppData\Local\Temp\pb_ship_extract\*.py` (0 files loaded from `c:\VSC_Projects\PokerBots\src`).

### 2. Python 3.11 Interpreter & Import Allowlist
- Interpreter verified: `C:\Users\Deep\AppData\Local\Programs\Python\Python311\python.exe` → `Python 3.11.9`.
- Full AST import listing across all 14 extracted files (`sys.stdlib_module_names` checked under Python 3.11.9; **0 violations**; **0 third-party imports**):
  - `bet_utils.py`: `typing` (stdlib), `config` (local)
  - `betting.py`: `typing` (stdlib), `config`, `postflop`, `preflop`, `bet_utils` (local)
  - `bot.py`: `json`, `pathlib`, `sys` (stdlib), `betting`, `config`, `discard`, `evaluator`, `opponent_model`, `state` (local)
  - `config.py`: *(none)*
  - `discard.py`: `random`, `time`, `typing` (stdlib), `equity`, `timemgr`, `evaluator`, `postflop` (local)
  - `equity.py`: `math`, `random`, `itertools`, `time` (stdlib), `evaluator` (local)
  - `evaluator.py`: `typing` (stdlib)
  - `opponent_model.py`: `dataclasses`, `random`, `sys`, `typing` (stdlib), `config`, `preflop_table`, `equity`, `evaluator` (local)
  - `postflop.py`: `random`, `sys`, `time`, `typing` (stdlib), `equity`, `timemgr`, `bet_utils`, `evaluator` (local)
  - `preflop.py`: `sys`, `typing` (stdlib), `config`, `preflop_table`, `bet_utils` (local)
  - `preflop_data.py`: *(none)*
  - `preflop_table.py`: `re`, `sys`, `collections`, `typing` (stdlib), `preflop_data` (local)
  - `state.py`: `dataclasses`, `typing` (stdlib), `opponent_model` (local)
  - `timemgr.py`: *(none)*

### 3. Read-Only Filesystem, `PYTHONDONTWRITEBYTECODE=1`, and Static Grep
- **Static scan** (`audit/scratch/check3_static.py` + regex/AST scan over all 14 extracted `.py` files): **0 hits** for `open(`, `makedirs`, `mkdir`, `tempfile`, `socket`, `subprocess`, `shutil`, `urllib`, `http`, `ctypes`, `multiprocessing`, `write_text`, `write_bytes`, `touch`, `unlink`, `rmdir`, `rename`, `os.open`.
- **WSL / Docker availability:** `wsl --status` returned `Wsl/E_ACCESSDENIED`; `docker` is not installed.
- **Windows real read-only folder test:** Extracted `submission_ship.zip` to `%TEMP%\pb_ship_ro_final`, applied `attrib +R *.py` and `icacls <dir> /deny "<user>:(OI)(CI)(WD,AD,WEA,WA)"`. Verified directly via Python 3.11 that both `open(..., 'w')` and `os.mkdir('__pycache__')` raised `PermissionError`.
- **Full Stage 1 match** (`PYTHONDONTWRITEBYTECODE=1`, `--stage 1 --hands 400 --seed 101`, vs `opponents/always_call.py`, `--python python3.11`):
  - `400 of 400 hands played` | `net +11132` | `time used 57.27 s of 60 s` | `notices 0` | `A wins`
  - `__pycache__` count after match: `0` | `audit/logs_ship_ro_final/A_stderr.txt`: `0` bytes.

### 4. Cold Launch-to-Ready Time (No `.pyc`)
Measured in fresh `%TEMP%\pb_ship_cold_final` with `PYTHONDONTWRITEBYTECODE=1` and `python3.11 -B` (`0` `.pyc` files before and after). Wall-clock time measured from `subprocess.Popen` launch until first valid JSON action reply (`init` + `new_hand` + preflop `action_request` sent immediately on stdin):
- Trial 1: `190.4 ms`
- Trial 2: `182.1 ms`
- Trial 3: `174.6 ms`
- Trial 4: `169.5 ms`
- Trial 5: `222.1 ms`
- **Summary:** **min `169.5 ms`, mean `187.7 ms`, max `222.1 ms`** (well below `5000 ms` startup limit; < 4.5%).

### 5. Stage 2 (`1000` hands, `150 s` time bank, `450 s` wallclock)
All Stage 2 runs executed with `--python python3.11` against `%TEMP%\pb_ship_extract\bot.py`:

| Opponent | Seed | Hands | Net Chips | Time Used | Notices | Stderr | Log Dir |
|---|---|---|---|---|---|---|---|
| `opponents/always_call.py` | `702` | `1000 / 1000` | `+26175` | **`148.60 s / 150 s`** | `0` | `0` B | `audit/logs_ship_s2_call_repro` |
| `opponents/always_raise.py` | `701` | `1000 / 1000` | `+28367` | **`148.82 s / 150 s`** | `0` | `0` B | `audit/logs_ship_s2_raise_final` |

*Notes:*
- An earlier `Seed 702` run (`audit/logs_ship_s2_call`) forfeited at hand 471 (`reply took longer than 5 s`) after an unexpected 36-minute host suspend gap (`07:15:27Z` → `07:51:36Z`); re-running `Seed 702` unpaused completed all 1000 hands cleanly.
- **Operational observation:** Both full-1000-hand matches against non-folding opponents reached `timemgr.low_time` (`time_left_ms < 1500` in [`src/timemgr.py:15-16`](file:///c:/VSC_Projects/PokerBots/src/timemgr.py#L15-L16)) near the end of the match and finished with only **`1.18 s – 1.40 s`** remaining out of `150 s`. `timemgr` successfully prevented timeout forfeits, though strategy fell back to `_cheap` / `default_discard` during the final hands once `time_left_ms < 1500`.

### 6. Legs Format (`audit/engine_legs.py`)
Copied `engine.py` to [`audit/engine_legs.py`](file:///c:/VSC_Projects/PokerBots/audit/engine_legs.py) changing Stage 1 to `{"hands": 200, "time_bank_ms": 30_000, "wallclock_s": 90, "cap": 200}`. Ran two fresh bot processes (`--python python3.11`) vs `opponents/always_call.py`:

| Leg | Seed | Hands | Net Chips | Time Used vs 30 s | Notices | Stderr | Log Dir |
|---|---|---|---|---|---|---|---|
| Leg 1 | `801` | `200 / 200` | `+4825` | **`24.62 s / 30 s`** (`82.1%`) | `0` | `0` B | `audit/logs_ship_leg1` |
| Leg 2 | `802` | `200 / 200` | `+5150` | **`19.61 s / 30 s`** (`65.4%`) | `0` | `0` B | `audit/logs_ship_leg2` |

### 7. Slow CPU Stress Test (3 Concurrent Matches + 2 Busy Loops on Same Cores)
Harness [`audit/scratch/run_slow_cpu.py`](file:///c:/VSC_Projects/PokerBots/audit/scratch/run_slow_cpu.py) pinned itself via `SetProcessAffinityMask` to **`0x3`** (2 of 16 logical cores; inherited by all 2 busy-loop processes + all 3 `engine.py` matches and their bot/opponent subprocesses):

| Match | Opponent | Seed | Hands | Net | Time Used vs 60 s | Wallclock | Notices | Forfeits |
|---|---|---|---|---|---|---|---|---|
| `m1_call` | `always_call.py` | `901` | `400 / 400` | `+11103` | **`58.55 s / 60 s`** | `65.0 s` | `0` | `0` |
| `m2_raise` | `always_raise.py` | `902` | `400 / 400` | `+11557` | **`58.58 s / 60 s`** | `65.2 s` | `0` | `0` |
| `m3_tight` | `tight_raiser.py` | `903` | `400 / 400` | `+5062` | **`39.57 s / 60 s`** | `65.2 s` | `0` | `0` |

- `m3_tight` slowed from `~5.5–5.8 s` (baseline in `AUDIT.md`) to `39.57 s` (~7× CPU/scheduling slowdown), while `m1_call` and `m2_raise` engaged `timemgr.low_time` around `~58.5 s` and finished cleanly with **0 forfeits**, **0 notices**, and **0 B stderr**.

### 8. Fuzz Harness
Harness [`audit/scratch/fuzz_bot.py`](file:///c:/VSC_Projects/PokerBots/audit/scratch/fuzz_bot.py) launched `%TEMP%\pb_ship_extract\bot.py` via `python3.11 -B` and streamed a 32-message interactive sequence checking 1-to-1 reply synchronization:
- **Tested cases:** malformed/truncated JSON (`{not valid json`, incomplete JSON, whitespace, plain text), unknown message types (`ping`, `future_protocol_v2`, `{}`), 4-card hole lists across preflop/flop/discard/turn/river, `min_raise > max_raise` (including monster hands wanting to raise), empty `history: []`, missing fields (`action_request`, `discard_request`), empty/malformed `hole_cards` (`[]`, `None`, `12345`, `["XX","YY","ZZ"]`, `["bad","As","3h"]`, `["AsXYZ"]`), and `notice` mid-hand.
- **Measured result:** `[PASS] fuzz_main_battery: 32 inputs, 18 valid replies, 0 extra stdout lines, exit=0`. `unit_fix_a_and_b` also passed all assertions.
- **Unfixed edge case noted (outside `(a)`/`(b)` scope):** Feeding *valid JSON that is not a dict* (`null`, `123`, `[1,2]`) exits with `rc=1` and `[FATAL] Bot exception: '...' object has no attribute 'get'` at [`src/bot.py:112`](file:///c:/VSC_Projects/PokerBots/src/bot.py#L112) because `msg` is not checked with `isinstance(msg, dict)` after `json.loads`. (Never occurs with valid protocol messages or unparseable JSON.)
