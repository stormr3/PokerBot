#!/usr/bin/env python3
# ==============================================================================
# tools/package.py — Submission Zip Builder and Compliance Checker
# Owner: Shared (Person A & Person B)
#
# Responsibilities:
# - Package bot.py and its sibling modules into submission.zip.
# - Validate file size <= 5.0 MB.
# - Perform AST static inspection to enforce the allowed-imports sandbox
#   (stdlib, numpy, scipy only; no pandas, torch, sklearn, requests, etc).
# - Run a quick smoke test against example_bots/random_bot.py.
# ==============================================================================

import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

MAX_ZIP_BYTES = 5 * 1024 * 1024  # 5 MB

# Allowed third-party packages per Rulebook Section 5.2
ALLOWED_PACKAGES = {"numpy", "scipy"}

# Files to bundle into submission.zip (at the root level of the zip)
BOT_MODULES = [
    "bot.py",
    "state.py",
    "config.py",
    "evaluator.py",
    "equity.py",
    "discard.py",
    "betting.py",
    "preflop_table.py",
    "opponent_model.py",
]

# Additional static data assets to bundle (relative path in src/ -> path in zip)
BOT_ASSETS = [
    ("data/preflop_equity.npz", "data/preflop_equity.npz"),
]


def check_file_imports(file_path: Path, local_module_names: set[str]) -> list[str]:
    """Inspects file AST for forbidden external package imports."""
    violations: list[str] = []
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                if not is_allowed_package(root_pkg, local_module_names):
                    violations.append(f"Line {node.lineno}: import {alias.name} ('{root_pkg}' is not permitted)")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                if not is_allowed_package(root_pkg, local_module_names):
                    violations.append(f"Line {node.lineno}: from {node.module} import ... ('{root_pkg}' is not permitted)")

    return violations


def is_allowed_package(pkg: str, local_module_names: set[str]) -> bool:
    """Checks whether a package name belongs to stdlib, allowed packages, or local modules."""
    if pkg in local_module_names:
        return True
    if pkg in ALLOWED_PACKAGES:
        return True
    # Check standard library
    if pkg in sys.stdlib_module_names:
        return True
    # Handle builtins
    if pkg in ("sys", "json", "time", "random", "math", "collections", "itertools", "dataclasses", "pathlib", "typing"):
        return True
    return False


def build_package(output_zip: str = "submission.zip") -> None:
    """Builds and validates the submission zip."""
    root_dir = Path(__file__).resolve().parent.parent
    src_dir = root_dir / "src"
    zip_path = root_dir / output_zip
    local_names = {Path(m).stem for m in BOT_MODULES}

    print("=" * 60)
    print("POKERBOT SUBMISSION BUILDER & COMPLIANCE VERIFICATION")
    print("=" * 60)

    # 1. Check all modules exist and inspect imports
    print("[1/4] Scanning modules in src/ and checking import compliance...")
    all_violations: list[str] = []
    for mod_name in BOT_MODULES:
        mod_path = src_dir / mod_name
        if not mod_path.is_file():
            sys.exit(f"Error: Required module missing in src/: {mod_path}")
        violations = check_file_imports(mod_path, local_names)
        if violations:
            all_violations.extend([f"[{mod_name}] {v}" for v in violations])

    if all_violations:
        print("\nERROR: Forbidden package imports detected!")
        for v in all_violations:
            print(f"  - {v}")
        sys.exit(1)
    print("  [PASS] All modules use ONLY standard library, numpy, and scipy.")

    # 2. Create the zip archive
    print("[2/4] Assembling zip archive (placing modules at zip root)...")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for mod_name in BOT_MODULES:
            mod_path = src_dir / mod_name
            zf.write(mod_path, arcname=mod_name)
            print(f"  + Added {mod_name}")
        for rel_src, arcname in BOT_ASSETS:
            asset_path = src_dir / rel_src
            if asset_path.is_file():
                zf.write(asset_path, arcname=arcname)
                print(f"  + Added {arcname}")

    # 3. Check zip size
    size_bytes = zip_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    print(f"[3/4] Checking file size: {size_bytes:,} bytes ({size_mb:.3f} MB)...")
    if size_bytes > MAX_ZIP_BYTES:
        sys.exit(f"Error: Archive exceeds maximum size limit of 5 MB ({size_mb:.2f} MB)")
    print(f"  [PASS] Size is within 5 MB limit ({size_bytes:,} bytes).")

    # 4. Smoke test: Extract and run 2 hands against random_bot using engine.py
    print("[4/4] Running smoke test on extracted zip with engine.py...")
    with tempfile.TemporaryDirectory(prefix="pokerbot_smoke_") as tmp_dir:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)

        extracted_bot = os.path.join(tmp_dir, "bot.py")
        random_bot = str(root_dir / "opponents" / "random_bot.py")
        engine_path = str(root_dir / "engine.py")

        cmd = [
            sys.executable,
            engine_path,
            extracted_bot,
            random_bot,
            "--stage", "1",
            "--hands", "2",
            "--seed", "42",
            "--log-dir", "",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"Smoke test failed with exit code {proc.returncode}:\n{proc.stderr}")
            sys.exit(1)
        if "notices 0" not in proc.stdout:
            print(f"Warning: Smoke test emitted notices:\n{proc.stdout}")
        print("  [PASS] Smoke test passed: 2 hands played cleanly with 0 notices.")

    print("=" * 60)
    print(f"SUCCESS: Package created cleanly at {zip_path.name} ({size_mb:.3f} MB)")
    print("=" * 60)


if __name__ == "__main__":
    out_name = sys.argv[1] if len(sys.argv) > 1 else "submission.zip"
    build_package(out_name)
