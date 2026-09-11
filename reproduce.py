#!/usr/bin/env python3
"""Run the deterministic, offline manuscript reproduction checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PAPER = ROOT / "paper"
if not PAPER.is_dir():
    PAPER = ROOT / "payload" / "paper"


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    run(sys.executable, str(PAPER / "scripts" / "build_derived.py"), "--check-only")
    print("REPRODUCTION_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
