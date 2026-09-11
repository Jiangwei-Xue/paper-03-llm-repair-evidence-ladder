#!/usr/bin/env python3
"""Replay the public H5/E5/VCR and manuscript-analysis checks offline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PAPER = ROOT / "paper"
EVIDENCE = ROOT / "evidence"
if not PAPER.is_dir():
    PAPER = ROOT / "payload" / "paper"
    EVIDENCE = ROOT / "payload" / "public_evidence"
elif (ROOT / "public_evidence").is_dir():
    EVIDENCE = ROOT / "public_evidence"

EXPECTED = {
    "E5_VCR_MAINMATRIX_V2_30TASK_8REP_TOKEN32768_8192_POSTRUN_20260707": 960,
    "E5_VCR_RANDOM30_EXTENSION_DEEPSEEK_30TASK_8REP_960ROW_POSTRUN_20260710": 960,
    "E5_VCR_GLM52_BAILIAN_30TASK_8REP_480ROW_POSTRUN_20260709": 480,
}

EXPECTED_CLAIMS = {
    "deepseek_clean": {"rows": 960, "cells": 120, "actions": 199, "passes": 14},
    "deepseek_extension": {"rows": 960, "cells": 120, "actions": 204, "passes": 14},
    "glm_supplementary": {"rows": 480, "cells": 60, "actions": 86, "passes": 0},
}


def canonical_hash(record: dict, hash_field: str) -> str:
    body = dict(record)
    body.pop(hash_field)
    encoded = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_and_check(path: Path, hash_field: str, expected: int) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            record = json.loads(line)
            observed = canonical_hash(record, hash_field)
            if observed != record.get(hash_field):
                raise AssertionError(f"self-hash mismatch: {path}:{line_number}")
            records.append(record)
    if len(records) != expected:
        raise AssertionError(f"row-count mismatch: {path}: {len(records)} != {expected}")
    return records


def check_e5_vcr() -> None:
    root = EVIDENCE / "03_E5_VCR"
    total_rows = 0
    total_replay = 0
    for stem, expected in EXPECTED.items():
        rows = load_and_check(root / f"{stem}_ROW_LEDGER.jsonl", "row_ledger_sha256", expected)
        replay = load_and_check(
            root / f"{stem}_REPLAY_INDEX.jsonl", "replay_record_sha256", expected
        )
        row_hashes = {record["row_ledger_sha256"] for record in rows}
        missing_links = [
            record["row_ledger_sha256"]
            for record in replay
            if record["row_ledger_sha256"] not in row_hashes
        ]
        if missing_links:
            raise AssertionError(f"replay-to-ledger links missing for {stem}")
        total_rows += len(rows)
        total_replay += len(replay)
    if (total_rows, total_replay) != (2400, 2400):
        raise AssertionError("E5/VCR total mismatch")
    print("E5_LEDGER_ROWS=2400")
    print("VCR_REPLAY_ROWS=2400")


def check_canonical_structure() -> None:
    rows_path = PAPER / "data" / "row_level_master_original.csv"
    claim_path = PAPER / "data" / "row_level_claim_view.csv"
    cells_path = PAPER / "data" / "cell_manifest.csv"
    with rows_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with claim_path.open(newline="", encoding="utf-8") as handle:
        claims = list(csv.DictReader(handle))
    with cells_path.open(newline="", encoding="utf-8") as handle:
        cells = list(csv.DictReader(handle))
    if len(rows) != 2400:
        raise AssertionError(f"canonical row count is {len(rows)}, expected 2400")
    if len(cells) != 300:
        raise AssertionError(f"cell count is {len(cells)}, expected 300")
    if len({row["row_id"] for row in rows}) != 2400:
        raise AssertionError("canonical row identifiers are not unique")
    if len(claims) != 2400:
        raise AssertionError(f"claim-view row count is {len(claims)}, expected 2400")
    for canonical, claim in zip(rows, claims, strict=True):
        if canonical["row_id"] != claim["canonical_row_id"]:
            raise AssertionError("claim-view/canonical row order mismatch")
        harmonized = int(
            canonical["action_governance_success"] == "1"
            and canonical["deterministic_edit_apply_success"] == "1"
            and canonical["patch_apply_check_ok"] == "1"
        )
        if harmonized != int(claim["action_harmonized"]):
            raise AssertionError(f"harmonized-action mismatch: {canonical['row_id']}")
        if int(canonical["answer_success"] == "1") != int(claim["verifier_pass"]):
            raise AssertionError(f"verifier-pass mismatch: {canonical['row_id']}")

    computed_crosstab = Counter()
    for row in claims:
        computed_crosstab[(row["stratum"], row["action_harmonized"], row["verifier_pass"])] += 1
    for stratum in EXPECTED_CLAIMS:
        for action in ("0", "1"):
            for passed in ("0", "1"):
                computed_crosstab.setdefault((stratum, action, passed), 0)
    with (PAPER / "data" / "action_pass_crosstab_by_stratum.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        released_crosstab = {
            (row["stratum"], row["action_harmonized"], row["verifier_pass"]): int(row["count"])
            for row in csv.DictReader(handle)
        }
    if dict(computed_crosstab) != released_crosstab:
        raise AssertionError("released action-pass crosstab does not match canonical rows")

    for stratum, expected in EXPECTED_CLAIMS.items():
        subset = [row for row in claims if row["stratum"] == stratum]
        observed = {
            "rows": len(subset),
            "cells": len({row["cell_id"] for row in subset}),
            "actions": sum(int(row["action_harmonized"]) for row in subset),
            "passes": sum(int(row["verifier_pass"]) for row in subset),
        }
        if observed != expected:
            raise AssertionError(f"claim metric mismatch for {stratum}: {observed} != {expected}")
    print("CANONICAL_ROWS=2400")
    print("FIXED_CELLS=300")
    print("CLAIM_METRICS_AND_CROSSTAB=PASS")


def verify_archive(path: Path) -> None:
    verifier_candidates = (
        ROOT / "tools" / "VERIFY_ARCHIVE.py",
        ROOT.parent / "tools" / "VERIFY_ARCHIVE.py",
    )
    verifier = next((candidate for candidate in verifier_candidates if candidate.is_file()), None)
    if verifier is not None:
        command = [
            sys.executable,
            str(verifier),
            "verify",
            "--archive",
            str(path),
            "--public",
        ]
    else:
        release_tool = shutil.which("experiment-release")
        if release_tool is None:
            raise AssertionError("canonical archive verifier is unavailable")
        command = [release_tool, "verify", "--archive", str(path), "--public"]
    subprocess.run(command, cwd=ROOT, check=True)


def check_scientific_file_integrity() -> None:
    summary_path = EVIDENCE / "05_VALIDATION" / "E5_VCR_PUBLIC_VALIDATION_V10.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("evidence_rows") != 2400 or summary.get("replay_rows") != 2400:
        raise AssertionError("public E5/VCR validation summary has unexpected counts")
    for item in summary.get("files", []):
        path = EVIDENCE / "03_E5_VCR" / item["file"]
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        if observed != item["file_sha256"]:
            raise AssertionError("public evidence file checksum mismatch: " + item["file"])
        if item.get("self_hashes_valid") is not True:
            raise AssertionError("public evidence self-hash status is not valid")
    for line in (PAPER / "SHA256SUMS.txt").read_text().splitlines():
        expected, rel = line.split("  ", 1)
        if hashlib.sha256((PAPER / rel).read_bytes()).hexdigest() != expected:
            raise AssertionError("Paper file checksum mismatch: " + rel)
    print("PUBLIC_SCIENTIFIC_EVIDENCE_INTEGRITY=PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, help="also verify the downloaded release archive")
    args = parser.parse_args()
    if args.archive:
        verify_archive(args.archive.resolve())
    check_scientific_file_integrity()
    check_e5_vcr()
    check_canonical_structure()
    print("H5_E5_VCR_REPLAY_STATUS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
