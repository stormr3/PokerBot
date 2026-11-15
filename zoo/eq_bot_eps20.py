#!/usr/bin/env python3
"""EqBot variant with 20% epsilon-random actions."""
from pathlib import Path
import sys

_ZOO_DIR = str(Path(__file__).resolve().parent)
if _ZOO_DIR not in sys.path:
    sys.path.insert(0, _ZOO_DIR)

from eq_bot import main  # noqa: E402

if __name__ == "__main__":
    main(default_eps=0.20)
