#!/usr/bin/env python3
"""Verify the retained full-transcript prompt-audit report surface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if args.archive is not None and not args.archive.is_file():
        raise SystemExit("PROMPT_AUDIT_REPORTS_STATUS=FAIL\nREASON=archive path does not exist")
    reports = sorted(ROOT.glob("*/*.json"))
    if len(reports) != 5:
        raise SystemExit(f"PROMPT_AUDIT_REPORTS_STATUS=FAIL\nREPORTS={len(reports)}")
    prompts = 0
    for path in reports:
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("failure_count") != 0:
            raise SystemExit(f"PROMPT_AUDIT_REPORTS_STATUS=FAIL\nREPORT={path.name}\nREASON=failure_count")
        if record.get("feedback_leak_audit_failures") != 0:
            raise SystemExit(f"PROMPT_AUDIT_REPORTS_STATUS=FAIL\nREPORT={path.name}\nREASON=feedback_leak")
        if record.get("missing_attempt_prompt_artifacts") not in ([], 0):
            raise SystemExit(f"PROMPT_AUDIT_REPORTS_STATUS=FAIL\nREPORT={path.name}\nREASON=missing_attempt_prompts")
        prompts += int(record.get("prompt_files_scanned", 0))
    print("PROMPT_AUDIT_REPORTS_STATUS=PASS")
    print("REPORTS=5")
    print(f"PROMPT_FILES_SCANNED={prompts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
