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
USE_RANGE_TABLES: bool = True            # False = always use the "any hand" table (old single-table behaviour)
USE_OPP_CLASSIFIER: bool = True          # False = fixed DEFAULT_OPP_WIDTH instead of the measured width
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

# ------------------------------------------------------------------------------
# Preflop range tables (see preflop.py / preflop_table.py)
# "Width" = the percent of all hands the opponent could hold when they act.
# ------------------------------------------------------------------------------
DEFAULT_OPP_WIDTH: float = 40.0              # prior for how wide an opponent's first raise is
PREFLOP_RERAISE_FACTOR: float = 0.40         # each further raise narrows a "selective" opponent's range by this factor
PREFLOP_MIN_WIDTH: float = 5.0               # never assume a range narrower than the tightest table
PREFLOP_MIN_WIDTH_NO_EVIDENCE: float = 40.0  # don't assume a range tighter than this until showdown evidence exists

# First-action decisions use the hand's percentile (0 = worst hand, 1 = best hand)
PREFLOP_OPEN_PCT: float = 0.30           # button raises hands at or above this percentile (top 70%)
PREFLOP_LIMP_PCT: float = 0.08           # button folds below this percentile, limps in between
PREFLOP_BB_RAISE_PCT: float = 0.60       # big blind raises a limp with the top 40%

# Decisions facing a raise use equity against the opponent's estimated range
PREFLOP_3BET_EQUITY_VS_RANGE: float = 0.52   # re-raise (3-bet) when equity vs their range is at least this
PREFLOP_4BET_EQUITY_VS_RANGE: float = 0.60   # re-raise again when facing a 3-bet or more
PREFLOP_CALL_MARGIN: float = 0.00            # extra equity required over pot odds to call
PREFLOP_BIG_BET_MARGIN: float = 0.08         # extra required when the call is a whole stack (scaled by stack fraction)

# Opponent classifier (opponent_model.py)
OPP_FREQ_PRIOR_STRENGTH: int = 20        # pseudo-observations behind the raise-frequency prior
OPP_EVIDENCE_PRIOR_STRENGTH: int = 6     # showdown samples needed for evidence to count about half
OPP_EVIDENCE_MIN_SAMPLES: int = 6        # below this, PREFLOP_MIN_WIDTH_NO_EVIDENCE applies
OPP_EVIDENCE_QUANTILE: float = 0.10      # low quantile of the percentiles of hands they raised with
