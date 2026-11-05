#!/usr/bin/env python3
# ==============================================================================
# tools/make_variant.py — Copy src/ to variants/<name>/ with config overrides
#
# Lets bench.py compare two settings of the SAME bot (e.g. classifier on vs off):
#   python tools/make_variant.py fixed  USE_OPP_CLASSIFIER=False
#   python tools/make_variant.py adapt  USE_OPP_CLASSIFIER=True
#   python tools/bench.py variants/adapt/bot.py variants/fixed/bot.py -n 20
# To compare against an OLDER version of the code, put that old src/ in variants/old/.
# ==============================================================================

import shutil
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: make_variant.py NAME [KEY=VALUE ...]")
    name, overrides = sys.argv[1], sys.argv[2:]
    root = Path(__file__).resolve().parent.parent
    dest = root / "variants" / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(root / "src", dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    lines = ["", "# --- variant overrides (tools/make_variant.py) ---"]
    for item in overrides:
        key, _, value = item.partition("=")
        if not key or not value:
            sys.exit(f"bad override '{item}', expected KEY=VALUE")
        lines.append(f"{key.strip()} = {value.strip()}")
    with open(dest / "config.py", "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"variant '{name}' -> {dest}  overrides: {overrides or 'none'}")


if __name__ == "__main__":
    main()
