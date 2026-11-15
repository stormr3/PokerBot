#!/usr/bin/env python3
"""Seed-changed frozen self-play copy of bot_v_prev."""

import os
from pathlib import Path
import random
import sys

_PREV_DIR = str(Path(__file__).resolve().parent / "bot_v_prev")
if _PREV_DIR not in sys.path:
    sys.path.insert(0, _PREV_DIR)

# Seed RNG differently from candidate so self-play paths diverge deterministically when seeded.
_seed_val = int(os.environ.get("ZOO_SELFPLAY_SEED", "987654321"))
random.seed(_seed_val)

import bot  # noqa: E402

if __name__ == "__main__":
    bot.main()
