#!/usr/bin/env python3
"""Render a matched V3/V4 rerun command from a retained run config.

This utility never calls a provider or Docker. It makes historical settings
visible and leaves external task paths, credentials, and execution to the user.
"""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "scripts" / "roadmapbench_tier1_matched_v3_v4_runner.py"


def add(parts: list[str], flag: str, value: object | None) -> None:
    if value is not None:
        parts.extend([flag, str(value)])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path, help="retained RUN_CONFIG.json")
    parser.add_argument("--tasks-root", default="/path/to/roadmapbench/tasks")
    parser.add_argument("--run-name", default="independent_rerun")
    parser.add_argument("--execute", action="store_true", help="render an execution command instead of --dry-run")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    required = ("tasks", "arms", "methods", "reps", "provider", "model")
    missing = [key for key in required if key not in config]
    if missing:
        raise SystemExit("CONFIG_STATUS=FAIL\nMISSING=" + ",".join(missing))

    parts = [
        "env",
        f"ROADMAPBENCH_TASKS_ROOT={args.tasks_root}",
        "python3",
        str(RUNNER),
        "--run-name",
        args.run_name,
        "--provider",
        str(config["provider"]),
        "--model",
        str(config["model"]),
        "--tasks",
        *[str(value) for value in config["tasks"]],
        "--arms",
        *[str(value) for value in config["arms"]],
        "--methods",
        *[str(value) for value in config["methods"]],
        "--reps",
        str(config["reps"]),
    ]
    for flag, key in (
        ("--budget", "budget"),
        ("--jobs", "jobs"),
        ("--context-mode", "context_mode"),
        ("--max-context-chars", "max_context_chars"),
        ("--max-tokens", "max_tokens"),
        ("--stage1-max-tokens", "stage1_max_tokens"),
        ("--timeout-seconds", "timeout_seconds"),
        ("--api-attempts", "api_attempts"),
        ("--file-op-max-files", "file_op_max_files"),
        ("--v3-repair-attempts", "v3_repair_attempts"),
        ("--v4-repair-attempts", "v4_repair_attempts"),
        ("--staged-v4-profile", "staged_v4_profile"),
    ):
        add(parts, flag, config.get(key))
    parts.append("--skip-docker-on-invalid-patch")
    if not args.execute:
        parts.append("--dry-run")

    print("RERUN_COMMAND_MODE=" + ("execute" if args.execute else "dry-run"))
    print("CONFIG_STATUS=PASS")
    print(" ".join(shlex.quote(part) for part in parts))
    if args.execute:
        print("NOTICE=This command can call a hosted model and Docker; review it before running.")
    else:
        print("NOTICE=No API call or Docker execution was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
