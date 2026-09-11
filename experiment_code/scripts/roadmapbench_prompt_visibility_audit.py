#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_FILE_HEADER_RE = re.compile(
    r"^--- FILE: (?P<path>(?:tests?|solution|logs|results|verifier|eval)/[^ \n]+|task\.toml)\s*---$",
    re.MULTILINE,
)
FORBIDDEN_DIFF_RE = re.compile(r"^diff --git a/(?:tests?|solution|logs|results|verifier|eval)/", re.MULTILINE)
SOLUTION_PATCH_RE = re.compile(r"^diff --git a/.*\nindex [0-9a-f]+\.\.[0-9a-f]+", re.MULTILINE)
BOUNDARY_TERMS = (
    "solution/changes.patch",
    "tests/",
    "test/",
    "verifier/",
    "task.toml",
    "benchmark metadata",
    "<STATE_JSON>",
    "<EDIT_JSON>",
    "<PATCH>",
)
FEEDBACK_LEAK_PATTERNS = {
    "hidden_or_oracle_term": re.compile(r"\b(hidden[-_ ]?test|oracle|gold|solution/changes\.patch|scorer[-_ ]?only)\b", re.IGNORECASE),
    "test_file_path": re.compile(r"\b(?:tests?|/tests)/[^ \n\"']+", re.IGNORECASE),
    "assertion_payload": re.compile(r"\b(AssertionError|assert\s+|expected\s*[:=]|actual\s*[:=]|Expected\s*[:=]|Actual\s*[:=])"),
    "pytest_or_unittest_trace": re.compile(r"\b(pytest|unittest|Traceback \(most recent call last\)|FAILED tests?/)", re.IGNORECASE),
    "reward_or_verifier_payload": re.compile(r"\b(reward\.json|reward\.txt|/logs/verifier|verifier output)\b", re.IGNORECASE),
}


def sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_prompt_files(run_dir: Path) -> list[dict[str, Any]]:
    prompts: list[dict[str, Any]] = []
    for prompt_path in sorted((run_dir / "stage1_prompts").glob("*.txt")):
        prompts.append({
            "scope": "stage1_plan_prompt",
            "turn_index": 0,
            "prompt_path": prompt_path,
            "run_id": prompt_path.stem,
        })
    for prompt_path in sorted((run_dir / "prompts").glob("*.txt")):
        prompts.append({
            "scope": "initial_prompt",
            "turn_index": 0,
            "prompt_path": prompt_path,
            "run_id": prompt_path.stem,
        })
    for prompt_path in sorted((run_dir / "rows").glob("*/stage1/prompt.txt")):
        row_name = prompt_path.parents[1].name
        run_id = row_name.split("_", 1)[1] if "_" in row_name else row_name
        prompts.append({
            "scope": "stage1_plan_prompt",
            "turn_index": 0,
            "prompt_path": prompt_path,
            "run_id": run_id,
        })
    for prompt_path in sorted((run_dir / "rows").glob("*/attempts/attempt_*/prompt.txt")):
        attempt_name = prompt_path.parent.name
        match = re.search(r"attempt_(\d+)$", attempt_name)
        row_name = prompt_path.parents[2].name
        run_id = row_name.split("_", 1)[1] if "_" in row_name else row_name
        prompts.append({
            "scope": "attempt_prompt",
            "turn_index": int(match.group(1)) if match else None,
            "prompt_path": prompt_path,
            "run_id": run_id,
        })
    return prompts


def missing_attempt_prompt_artifacts(run_dir: Path) -> list[str]:
    missing: list[str] = []
    for attempt_dir in sorted((run_dir / "rows").glob("*/attempts/attempt_*")):
        if (attempt_dir / "api_request_meta.json").exists() and not (attempt_dir / "prompt.txt").exists():
            missing.append(rel(attempt_dir))
    return missing


def feedback_section(text: str) -> str:
    marker = "# Failure Summary"
    if marker not in text:
        return ""
    section = text.split(marker, 1)[1]
    next_marker = "\n# Corrected Output Reminder"
    if next_marker in section:
        section = section.split(next_marker, 1)[0]
    return section.strip()


def audit_prompt(item: dict[str, Any]) -> dict[str, Any]:
    path = item["prompt_path"]
    text = path.read_text(encoding="utf-8", errors="replace")
    findings: list[dict[str, Any]] = []
    for match in FORBIDDEN_FILE_HEADER_RE.finditer(text):
        findings.append({
            "category": "forbidden_file_header",
            "path": match.group("path"),
            "line": text[: match.start()].count("\n") + 1,
        })
    if FORBIDDEN_DIFF_RE.search(text):
        findings.append({"category": "forbidden_diff_path"})
    if "solution/changes.patch" in text and SOLUTION_PATCH_RE.search(text):
        findings.append({"category": "possible_solution_patch_content"})
    feedback = feedback_section(text)
    feedback_findings: list[dict[str, Any]] = []
    if feedback:
        for category, pattern in FEEDBACK_LEAK_PATTERNS.items():
            hits = sorted({m.group(0)[:160] for m in pattern.finditer(feedback)})
            if hits:
                feedback_findings.append({"category": category, "hits": hits[:10]})
        findings.extend(
            {"category": "feedback_leak_risk", "feedback_category": finding["category"], "hits": finding["hits"]}
            for finding in feedback_findings
        )
    return {
        "scope": item["scope"],
        "turn_index": item["turn_index"],
        "run_id": item["run_id"],
        "prompt_path": rel(path),
        "prompt_sha256": sha256_text(text),
        "prompt_chars": len(text),
        "boundary_term_mentions": {term: text.count(term) for term in BOUNDARY_TERMS},
        "feedback_section_present": bool(feedback),
        "findings": findings,
    }


def write_markdown(path: Path, run_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# RoadmapBench Full-Transcript Prompt Visibility Audit",
        "",
        f"Run dir: `{rel(run_dir)}`",
        "",
        "## Scope",
        "",
        "This audit scans initial prompts and any saved repair/feedback attempt prompts. It is designed for staged or bounded-repair runs where later turns can introduce new leakage risk.",
        "",
        "Boundary-only mentions such as `solution/changes.patch`, `tests/`, and `task.toml` are allowed when used as prohibitions. The audit flags forbidden file headers, forbidden diff paths, possible solution patch payloads, and verifier/test feedback payloads in repair-turn failure summaries.",
        "",
        "## Counts",
        "",
        f"- prompt_files_scanned: {result['prompt_files_scanned']}",
        f"- stage1_plan_prompts_scanned: {result['stage1_plan_prompts_scanned']}",
        f"- initial_prompts_scanned: {result['initial_prompts_scanned']}",
        f"- attempt_prompts_scanned: {result['attempt_prompts_scanned']}",
        f"- missing_attempt_prompt_artifacts: {len(result['missing_attempt_prompt_artifacts'])}",
        f"- failure_count: {result['failure_count']}",
        f"- feedback_leak_audit_failures: {result['feedback_leak_audit_failures']}",
        "",
        "## Finding Categories",
        "",
    ]
    if result["finding_categories"]:
        for category, count in sorted(result["finding_categories"].items()):
            lines.append(f"- `{category}`: {count}")
    else:
        lines.append("- none")
    if result["missing_attempt_prompt_artifacts"]:
        lines.extend(["", "## Missing Attempt Prompt Artifacts", ""])
        for item in result["missing_attempt_prompt_artifacts"]:
            lines.append(f"- `{item}`")
    if result["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in result["failures"]:
            lines.append(f"- `{failure['prompt_path']}` ({failure['scope']}, turn={failure['turn_index']}): `{failure['findings']}`")
    lines.extend(
        [
            "",
            "## V4 Gate Use",
            "",
            "For staged-agent V4, this audit should be a hard gate over the full transcript, not only the first prompt. A V4 run should require `failure_count=0`, `feedback_leak_audit_failures=0`, and no missing attempt prompt artifacts.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    parser.add_argument("--require-attempt-prompts", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    if not run_dir.exists():
        raise SystemExit(f"run directory not found: {run_dir}")

    prompt_items = collect_prompt_files(run_dir)
    prompt_findings = [audit_prompt(item) for item in prompt_items]
    failures = [item for item in prompt_findings if item["findings"]]
    finding_counter: Counter[str] = Counter()
    feedback_failures = 0
    for item in failures:
        for finding in item["findings"]:
            category = str(finding.get("category"))
            finding_counter[category] += 1
            if category == "feedback_leak_risk":
                feedback_failures += 1
    missing_attempts = missing_attempt_prompt_artifacts(run_dir)
    if args.require_attempt_prompts:
        for item in missing_attempts:
            failures.append({
                "scope": "attempt_prompt",
                "turn_index": None,
                "run_id": None,
                "prompt_path": item,
                "findings": [{"category": "missing_attempt_prompt_artifact"}],
            })
            finding_counter["missing_attempt_prompt_artifact"] += 1
    result = {
        "run_dir": rel(run_dir),
        "prompt_files_scanned": len(prompt_findings),
        "stage1_plan_prompts_scanned": sum(1 for item in prompt_findings if item["scope"] == "stage1_plan_prompt"),
        "initial_prompts_scanned": sum(1 for item in prompt_findings if item["scope"] == "initial_prompt"),
        "attempt_prompts_scanned": sum(1 for item in prompt_findings if item["scope"] == "attempt_prompt"),
        "missing_attempt_prompt_artifacts": missing_attempts,
        "failure_count": len(failures),
        "feedback_leak_audit_failures": feedback_failures,
        "finding_categories": dict(finding_counter),
        "prompt_findings": prompt_findings,
        "failures": failures,
    }
    output_json = Path(args.output_json) if args.output_json else ROOT / "outputs" / "PROMPT_VISIBILITY_AUDIT_FULL_TRANSCRIPT_20260705.json"
    output_md = Path(args.output_md) if args.output_md else ROOT / "outputs" / "PROMPT_VISIBILITY_AUDIT_FULL_TRANSCRIPT_20260705.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    write_markdown(output_md, run_dir, result)
    print(json.dumps({
        "output_json": rel(output_json),
        "output_md": rel(output_md),
        "failure_count": result["failure_count"],
        "feedback_leak_audit_failures": result["feedback_leak_audit_failures"],
        "prompt_files_scanned": result["prompt_files_scanned"],
    }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
