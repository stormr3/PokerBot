# ==============================================================================
# config.py — Central Configuration & Feature Flags
# Owner: Shared (Person A & Person B)
#
# Responsibilities:
# - All tunable strategy parameters (bet sizing, equity thresholds, weights).
# - Time bank management limits (budgeting ms per action, emergency cutoffs).
# - Boolean feature flags for toggling modules (preflop tables, opponent model, etc).
# ==============================================================================

# Version metadata
BOT_NAME: str = "AcesDiscard"
VERSION: str = "1.0.0"

# Time bank budgeting (Official: 60s per 400 hands Stage 1; 150s per 1000 hands Stage 2)
# Average budget: ~150 ms/hand or ~15-20 ms per decision request
TARGET_REPLY_TIME_MS: float = 12.0
EMERGENCY_TIME_LEFT_MS: int = 5_000   # Drop all expensive rollouts if below this
PER_RESPONSE_LIMIT_MS: int = 5_000

# Monte Carlo Equity Simulation settings
MONTE_CARLO_SAMPLES_DEFAULT: int = 100
MONTE_CARLO_SAMPLES_TURBO: int = 40

# Feature Flags
USE_PREFLOP_TABLE: bool = True
USE_OPPONENT_MODEL: bool = True
USE_DYNAMIC_BET_SIZING: bool = True
DEBUG_LOGGING: bool = False

# Strategic Thresholds
VALUE_BET_EQUITY_THRESHOLD: float = 0.65
BLUFF_CATCH_BUFFER: float = 0.05
DEFAULT_POT_FRACTION: float = 0.60

# Preflop Canonical Equity & Pot-Odds Thresholds
PREFLOP_OPEN_EQUITY: float = 0.54       # Button open-raise threshold
PREFLOP_BB_RAISE_EQUITY: float = 0.58    # Big Blind raise vs limp threshold
PREFLOP_3BET_EQUITY: float = 0.65        # Re-raise / 3-bet value threshold
PREFLOP_LIMP_EQUITY: float = 0.40        # Button limp / call 1 chip threshold
PREFLOP_CALL_BUFFER_IP: float = 0.04     # In-position pot odds realization discount
PREFLOP_CALL_BUFFER_OOP: float = 0.00    # Out-of-position pot odds buffer

# Logging limits (Official engine limit: 64 KB = 65,536 bytes)
MAX_STDERR_BYTES: int = 50_000
