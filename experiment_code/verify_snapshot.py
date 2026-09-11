#!/usr/bin/env python3
"""Static, no-API verification for the retained experiment-code snapshot."""

from __future__ import annotations

import argparse
import os
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if args.archive is not None and not args.archive.is_file():
        raise SystemExit("EXPERIMENT_CODE_STATUS=FAIL\nREASON=archive path does not exist")

    files = (
        sorted(ROOT.glob("*.py"))
        + sorted((ROOT / "scripts").glob("*.py"))
        + sorted((ROOT / "tests").glob("*.py"))
    )
    if not files:
        raise SystemExit("EXPERIMENT_CODE_STATUS=FAIL\nREASON=no Python files found")
    with tempfile.TemporaryDirectory(prefix="experiment-code-verify-") as temporary:
        temporary_root = Path(temporary)
        for index, path in enumerate(files):
            py_compile.compile(str(path), cfile=str(temporary_root / f"{index}.pyc"), doraise=True)
    test = ROOT / "tests" / "test_answer_state_contract.py"
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, str(test)], cwd=ROOT, env=environment)
    if proc.returncode != 0:
        raise SystemExit("EXPERIMENT_CODE_STATUS=FAIL\nREASON=contract test failed")
    print("EXPERIMENT_CODE_STATUS=PASS")
    print(f"PYTHON_FILES={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
