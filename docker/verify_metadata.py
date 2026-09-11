#!/usr/bin/env python3
"""Offline integrity checks for the public Docker metadata surface."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def load_jsonl(name: str) -> list[dict[str, Any]]:
    path = ROOT / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def record_hash(record: dict[str, Any]) -> str:
    material = {key: value for key, value in record.items() if key != "record_sha256"}
    encoded = (json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
    return hashlib.sha256(encoded).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"DOCKER_METADATA_STATUS=FAIL\nREASON={message}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if args.archive is not None:
        require(args.archive.is_file(), "archive path does not exist")

    roster = load_jsonl("IMAGE_ROSTER.jsonl")
    configs = load_jsonl("IMAGE_CONFIGURATIONS.jsonl")
    runtime = json.loads((ROOT / "RUNTIME_CONTRACT.json").read_text(encoding="utf-8"))

    require(len(roster) == 60, "roster must contain 60 rows")
    require(len(configs) == 60, "configuration ledger must contain 60 rows")
    require(len({row["task_id"] for row in roster}) == 60, "roster task ids must be unique")
    require({row["task_id"] for row in roster} == {row["task_id"] for row in configs}, "task sets differ")
    require(Counter(row["pool"] for row in roster) == {"primary_30": 30, "extension_30": 30}, "pool counts differ")

    for row in roster + configs:
        require(row.get("record_sha256") == record_hash(row), f"self-hash mismatch for {row.get('task_id')}")
        require(SHA256_RE.match(row.get("frozen_manifest_digest", "")) is not None, "invalid manifest digest")
        require(SHA256_RE.match(row.get("historical_local_image_id", "")) is not None, "invalid local image id")

    for row in configs:
        inspect = row["docker_image_inspect"]
        require(inspect.get("Id") == row["historical_local_image_id"], f"inspect identity mismatch for {row['task_id']}")
        require(inspect.get("Architecture") == "amd64", f"unexpected architecture for {row['task_id']}")
        require(inspect.get("Os") == "linux", f"unexpected OS for {row['task_id']}")
        require((inspect.get("Config") or {}).get("WorkingDir") == "/app", f"unexpected workdir for {row['task_id']}")
        require(len((inspect.get("RootFS") or {}).get("Layers") or []) > 0, f"missing layers for {row['task_id']}")

    require(runtime.get("docker_image_layers_included") is False, "runtime contract must exclude image layers")
    offline = runtime.get("offline_public_replay") or {}
    require(offline.get("network_required_for_offline_replay") is False, "offline replay must not require network")

    print("DOCKER_METADATA_STATUS=PASS")
    print("TASKS=60")
    print("PRIMARY_POOL=30")
    print("EXTENSION_POOL=30")
    print("PLATFORM=linux/amd64")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
