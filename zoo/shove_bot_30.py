#!/usr/bin/env python3
"""ShoveBot variant: preflop jams top 30% of hands."""
from pathlib import Path
import sys

_ZOO_DIR = str(Path(__file__).resolve().parent)
if _ZOO_DIR not in sys.path:
    sys.path.insert(0, _ZOO_DIR)

from shove_bot import main  # noqa: E402

if __name__ == "__main__":
    main(default_top_x=30.0)
