"""
Run project validation checks in one command.

Usage:
  python run_checks.py
  python run_checks.py --skip-openenv

Behavior:
1. Runs local deterministic requirement checks.
2. Runs `openenv validate .` unless skipped.
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def run_command(cmd: list[str], label: str) -> int:
    print(f"\n[RUN] {label}: {' '.join(cmd)}")
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        print(f"[FAIL] {label} (exit={completed.returncode})")
    else:
        print(f"[PASS] {label}")
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local + OpenEnv checks")
    parser.add_argument(
        "--skip-openenv",
        action="store_true",
        help="Skip openenv validate step",
    )
    args = parser.parse_args()

    rc = run_command([sys.executable, "verify_requirements.py"], "local requirement checks")
    if rc != 0:
        return rc

    if args.skip_openenv:
        print("\n[INFO] Skipping OpenEnv validation by request (--skip-openenv).")
        return 0

    try:
        rc = run_command(["openenv", "validate", "."], "openenv validate")
        return rc
    except FileNotFoundError:
        print("\n[WARN] `openenv` CLI not found on PATH.")
        print("[HINT] Install/configure OpenEnv tooling, then re-run: python run_checks.py")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
