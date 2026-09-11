#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "roadmapbench_deepseek_6method_runner.py"
STAGE_STATE_RE = re.compile(r"<STAGE_STATE_JSON>\s*(.*?)\s*</STAGE_STATE_JSON>", re.DOTALL | re.IGNORECASE)
DEFAULT_TASKS = ["tpl-3.2.0-roadmap", "glz-3.0.0-roadmap"]
DEFAULT_ARMS = ["single_shot_v3", "staged_v4"]
STAGE1_MAX_EXISTING_FILES = 6
STAGE1_MAX_PLANNED_NEW_FILES = 2
STAGE1_DEFAULT_MAX_EDIT_TARGETS = 8
FAL_CAPACITY_MAX_EXISTING_FILES = 32
FAL_CAPACITY_MAX_PLANNED_NEW_FILES = 24
FAL_CAPACITY_MAX_EDIT_TARGETS = 64
STAGE1_MAX_REASON_CHARS = 240
FAL_CAPACITY_REASON_V2_MAX_REASON_CHARS = 512
LARGE_UPGRADE_MAX_EXISTING_FILES = 32
LARGE_UPGRADE_MAX_PLANNED_NEW_FILES = 24
LARGE_UPGRADE_MAX_EDIT_TARGETS = 64
LARGE_UPGRADE_MAX_REASON_CHARS = 512
STAGED_V4_PROFILES = ("frozen", "fal_capacity_diagnostic", "fal_capacity_reason_v2", "large_upgrade_v1", "large_upgrade_v1_mko_contract_fix")
QWEN_CONTRACT_PROFILES = ("none", "strict_json_v1")
FAL_CAPACITY_CONTEXT_PRIORITY_PATHS = [
    "falcon/__init__.py",
    "falcon/api.py",
    "falcon/api_helpers.py",
    "falcon/request.py",
    "falcon/request_helpers.py",
    "falcon/response.py",
    "falcon/response_helpers.py",
    "falcon/errors.py",
    "falcon/http_error.py",
    "falcon/status_codes.py",
    "falcon/routing/__init__.py",
    "falcon/routing/compiled.py",
    "falcon/routing/util.py",
    "falcon/uri.py",
    "falcon/util/uri.py",
    "falcon/util/time.py",
]


def fal_capacity_profile_active(task_id: str, profile: str) -> bool:
    return profile in {"fal_capacity_diagnostic", "fal_capacity_reason_v2"} and task_id.startswith("fal-")


def fal_capacity_reason_v2_active(task_id: str, profile: str) -> bool:
    return profile == "fal_capacity_reason_v2" and task_id.startswith("fal-")


def large_upgrade_profile_active(profile: str) -> bool:
    return profile in {"large_upgrade_v1", "large_upgrade_v1_mko_contract_fix"}


def mko_contract_fix_profile_active(task_id: str, profile: str) -> bool:
    return profile == "large_upgrade_v1_mko_contract_fix" and task_id.startswith("mko-")


def stage1_max_existing_files_for_task(task_id: str, profile: str = "frozen") -> int:
    if large_upgrade_profile_active(profile):
        return LARGE_UPGRADE_MAX_EXISTING_FILES
    if fal_capacity_profile_active(task_id, profile):
        return FAL_CAPACITY_MAX_EXISTING_FILES
    return STAGE1_MAX_EXISTING_FILES


def stage1_max_planned_new_files_for_task(task_id: str, profile: str = "frozen") -> int:
    if large_upgrade_profile_active(profile):
        return LARGE_UPGRADE_MAX_PLANNED_NEW_FILES
    if fal_capacity_profile_active(task_id, profile):
        return FAL_CAPACITY_MAX_PLANNED_NEW_FILES
    return STAGE1_MAX_PLANNED_NEW_FILES


def stage1_max_edit_targets_for_task(task_id: str, profile: str = "frozen") -> int:
    if large_upgrade_profile_active(profile):
        return LARGE_UPGRADE_MAX_EDIT_TARGETS
    if fal_capacity_profile_active(task_id, profile):
        return FAL_CAPACITY_MAX_EDIT_TARGETS
    if task_id.startswith("tpl-"):
        return 10
    return STAGE1_DEFAULT_MAX_EDIT_TARGETS


def stage1_max_reason_chars_for_task(task_id: str, profile: str = "frozen") -> int:
    if large_upgrade_profile_active(profile):
        return LARGE_UPGRADE_MAX_REASON_CHARS
    if fal_capacity_reason_v2_active(task_id, profile):
        return FAL_CAPACITY_REASON_V2_MAX_REASON_CHARS
    return STAGE1_MAX_REASON_CHARS


def profile_context_hints(task_id: str, profile: str) -> str:
    if not (fal_capacity_profile_active(task_id, profile) or (large_upgrade_profile_active(profile) and task_id.startswith("fal-"))):
        return ""
    return "\n".join(FAL_CAPACITY_CONTEXT_PRIORITY_PATHS)


def staged_v4_profile_guidance(task_id: str, profile: str) -> str:
    if large_upgrade_profile_active(profile):
        lines = [
            "# Large-Upgrade V1 Frozen Profile",
            "- This frozen profile applies the same staged planning/action capacity across all selected tasks.",
            "- It keeps strict EDIT_JSON matching and strict source-path rules.",
            f"- Stage 1 may list up to {LARGE_UPGRADE_MAX_EXISTING_FILES} existing files, {LARGE_UPGRADE_MAX_PLANNED_NEW_FILES} planned new files, and {LARGE_UPGRADE_MAX_EDIT_TARGETS} edit targets.",
            f"- Stage 1 reason strings may be up to {LARGE_UPGRADE_MAX_REASON_CHARS} characters.",
            "- Separate existing_files, planned_new_files, and edit_targets explicitly.",
            "- Include real API/export/wiring targets; creating standalone helper files is not enough.",
            "- No fuzzy matching, approximate matching, empty anchors, whole-file rewrites, or automatic path repair is allowed.",
            "- Keep reason strings concise; they are non-executable planning notes, not a place for code or analysis.",
        ]
        if mko_contract_fix_profile_active(task_id, profile):
            lines.extend(
                [
                    "# MKO Stage-1 Contract Fix",
                    "- Treat the Repository File Tree as authoritative for existing files.",
                    "- A path may appear in existing_files only if it is visible in the Repository File Tree and full-context source list.",
                    "- If a needed source path is absent from the visible file tree, put it in planned_new_files and use op=create.",
                    "- Do not put absent paths in existing_files, even if they look like natural barrel or type-module paths.",
                    "- For this task, `lib/types/index.ts` is absent in the base tree; if needed, list it only in planned_new_files with op=create.",
                ]
            )
        return "\n".join(lines)
    if not fal_capacity_profile_active(task_id, profile):
        return ""
    lines = [
        "# FAL Capacity Diagnostic Profile",
        "- This diagnostic profile keeps strict EDIT_JSON matching and strict source-path rules.",
        "- It only increases staged planning/action capacity for FAL; it is not the frozen staged_v4 protocol.",
        f"- Stage 1 may list up to {FAL_CAPACITY_MAX_EXISTING_FILES} existing files, {FAL_CAPACITY_MAX_PLANNED_NEW_FILES} planned new files, and {FAL_CAPACITY_MAX_EDIT_TARGETS} edit targets.",
        "- Separate existing_files, planned_new_files, and edit_targets explicitly.",
        "- Include real API/export/wiring targets; creating standalone helper files is not enough.",
        "- No fuzzy matching, approximate matching, empty anchors, whole-file rewrites, or automatic path repair is allowed.",
        "- Keep reason strings concise; they are non-executable planning notes, not a place for code or analysis.",
    ]
    if fal_capacity_reason_v2_active(task_id, profile):
        lines.append(f"- This v2 profile allows reason strings up to {FAL_CAPACITY_REASON_V2_MAX_REASON_CHARS} characters to avoid rejecting otherwise valid FAL path plans for formatting-only verbosity.")
    return "\n".join(lines)


def qwen_strict_json_guidance(profile: str) -> str:
    if profile != "strict_json_v1":
        return ""
    return "\n".join(
        [
            "# Qwen Strict JSON Contract Profile V1",
            "- This profile changes only output-format instructions. It does not relax scoring, path rules, edit application, or verifier behavior.",
            "- The first non-whitespace characters of the final answer must be `<STATE_JSON>`.",
            "- The final answer must end with `</EDIT_JSON>`.",
            "- Do not output markdown fences, headings, bullet lists, explanations, analysis text, or unified diff text.",
            "- Output exactly one STATE_JSON block followed immediately by exactly one EDIT_JSON block.",
            "- EDIT_JSON must contain a JSON object with an `ops` array. Do not rename this key.",
            "- For each replace op, copy `old` verbatim from the visible source context. The old string must be non-empty and should be a small exact unique anchor.",
            "- Before returning, check each op path against the visible file tree and allowed source path rules.",
            "- If an existing file is not visible in the file tree, do not list it as existing and do not replace it.",
            "- If a new source file is necessary, use a create op under an allowed source root.",
        ]
    )


def qwen_stage1_guidance(profile: str) -> str:
    if profile != "strict_json_v1":
        return ""
    return "\n".join(
        [
            "# Qwen Stage-1 Contract Profile V1",
            "- Return only one STAGE_STATE_JSON block. Do not include any text before or after it.",
            "- existing_files must be copied exactly from the Repository File Tree and visible full-context source list.",
            "- planned_new_files must contain only paths that are absent from the Repository File Tree.",
            "- edit_targets must be exactly the files you intend Stage 2 to edit or create.",
            "- Every replace target must also be in existing_files. Every create target must also be in planned_new_files.",
            "- Do not invent index files, barrel files, type files, helper files, or config files unless they are listed as planned_new_files.",
            "- Keep reasons short. Reasons are planning metadata, not code or analysis.",
        ]
    )


def append_qwen_guidance(prompt: str, profile: str, stage: str) -> str:
    if profile == "none":
        return prompt
    if profile != "strict_json_v1":
        raise ValueError(f"unknown qwen contract profile: {profile}")
    if stage == "stage1":
        extra = qwen_stage1_guidance(profile)
    else:
        extra = qwen_strict_json_guidance(profile)
    return prompt + "\n\n" + extra if extra else prompt


def profiled_repo_context(task_dir: Path, max_chars: int, context_mode: str, instruction: str, profile: str) -> dict[str, Any]:
    context_instruction = instruction
    hints = profile_context_hints(task_dir.name, profile)
    if hints:
        context_instruction = instruction + "\n\n# Source path hints for context selection\n" + hints
    return runner.build_repo_context(task_dir, max_chars=max_chars, context_mode=context_mode, instruction=context_instruction)


def staged_v4_allowed_existing_paths_for_task(task_id: str) -> set[str] | None:
    if task_id.startswith("tpl-"):
        return {"BS_thread_pool.hpp"}
    return None


def staged_v4_task_path_guidance(task_id: str) -> str:
    if task_id.startswith("tpl-"):
        return "\n".join(
            [
                "# Staged V4 Task Path Constraints",
                "- For this task, use exactly this existing source target: `BS_thread_pool.hpp`.",
                "- Do not include `BS_thread_pool_test.cpp` in existing_files, planned_new_files, or edit_targets.",
                "- Do not create new files for this task.",
                "- Keep all executable edits in `BS_thread_pool.hpp`; verification will run tests externally.",
            ]
        )
    if task_id.startswith("glz-"):
        return "\n".join(
            [
                "# Staged V4 Task Path Constraints",
                "- Keep the final edit small enough for exact sequential anchors; use at most 8 EDIT_JSON ops.",
                "- Prefer this target set: `include/glaze/core/refl.hpp`, `include/glaze/core/common.hpp`, `include/glaze/core/opts.hpp`, and `include/glaze/json/write.hpp`.",
                "- Avoid editing broad umbrella/export headers unless a required symbol is otherwise unreachable.",
                "- Avoid many repeated broad replacements in `include/glaze/core/common.hpp`; use short exact anchors that appear once.",
            ]
        )
    return ""


def load_runner():
    spec = importlib.util.spec_from_file_location("roadmap_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def write_json(path: Path, obj: Any) -> None:
    runner.write_json(path, obj)


def read_json(path: Path) -> Any:
    return runner.read_json(path)


def method_stage_instruction(method: str) -> str:
    if method == "loop_only":
        return "Use only the compact stage schema. Select the smallest directly editable source targets."
    if method == "rolling_summary":
        return "Use only the compact stage schema. Put any summary only in short edit target reasons."
    if method == "rolling_visible_carry_forward":
        return "Use only the compact stage schema. Represent visible carry-forward as allowed file paths and edit targets."
    if method == "rolling_visible_fields_only":
        return "Use only the compact stage schema. Do not add OUT, ALW, NO, G, or other extra fields."
    if method == "ssr_no_visible_carry":
        return "Use only the compact stage schema. Carry forward only final source-scope path conclusions."
    if method == "mature_ssr_loop":
        return "Use only the compact stage schema. Do not add LOOP, CK, notes, or hidden reasoning fields."
    raise ValueError(f"unknown method: {method}")


def render_stage1_prompt(
    task_dir: Path,
    method: str,
    budget: int,
    max_context_chars: int,
    context_mode: str,
    staged_v4_profile: str,
    qwen_contract_profile: str = "none",
) -> tuple[str, dict[str, Any]]:
    instruction = (task_dir / "instruction.md").read_text(encoding="utf-8", errors="replace")
    context = profiled_repo_context(task_dir, max_context_chars, context_mode, instruction, staged_v4_profile)
    max_existing_files = stage1_max_existing_files_for_task(task_dir.name, staged_v4_profile)
    max_planned_new_files = stage1_max_planned_new_files_for_task(task_dir.name, staged_v4_profile)
    max_edit_targets = stage1_max_edit_targets_for_task(task_dir.name, staged_v4_profile)
    max_reason_chars = stage1_max_reason_chars_for_task(task_dir.name, staged_v4_profile)
    prompt = "\n\n".join(
        [
            "# RoadmapBench Staged V4 Planning Task",
            f"Task id: {task_dir.name}",
            f"Staged V4 profile: {staged_v4_profile}",
            "Stage 1 only: identify existing source files, planned new source files, and edit targets, then produce a compact repair plan. Do not produce code edits in this stage.",
            "",
            "# Roadmap / Instruction",
            instruction,
            "",
            "# Repository File Tree",
            context["tree"],
            "",
            "# Visibility Boundary",
            "- Do not use or mention solution/changes.patch.",
            "- Do not use or mention tests/ verifier files.",
            "- Do not edit benchmark metadata, task.toml, solution files, verifier tests, logs, or generated results.",
            "- Stage 1 is planning only; do not quote source code and do not propose concrete code snippets.",
            runner.editable_path_rules(context),
            runner.strict_edit_json_path_scope(context, "edit_json"),
            runner.task_specific_guidance(task_dir.name),
            staged_v4_task_path_guidance(task_dir.name),
            staged_v4_profile_guidance(task_dir.name, staged_v4_profile),
            runner.method_text(method, budget),
            "# Staged V4 Method Behavior",
            method_stage_instruction(method),
            "",
            "# Stage 1 Output Contract",
            "Return exactly one tagged JSON block and no prose outside it:",
            "<STAGE_STATE_JSON>",
            "{",
            '  "existing_files": ["relative/existing/source_or_config_file"],',
            '  "planned_new_files": ["relative/new/source_or_config_file"],',
            '  "edit_targets": [',
            '    {"path": "relative/existing/source_or_config_file", "op": "replace", "reason": "why this existing file must change"},',
            '    {"path": "relative/new/source_or_config_file", "op": "create", "reason": "why this new file is needed"}',
            "  ]",
            "}",
            "</STAGE_STATE_JSON>",
            "",
            "Rules:",
            "- The JSON must be valid and compact. No keys other than existing_files, planned_new_files, and edit_targets are allowed.",
            f"- existing_files must contain at most {max_existing_files} paths.",
            f"- planned_new_files must contain at most {max_planned_new_files} paths.",
            f"- edit_targets must contain 1 to {max_edit_targets} objects.",
            f"- Each reason must be {max_reason_chars} characters or fewer.",
            "- Each reason should be one concise sentence; do not include implementation details or code.",
            "- Return only the tagged JSON block. Do not include analysis, markdown, code snippets, or prose outside the block.",
            "- existing_files must contain only visible existing source/config paths from the full-context source list.",
            "- planned_new_files may contain required new source/config paths that do not exist yet, but they must be under allowed editable source roots.",
            "- edit_targets must be non-empty and every target path must appear in either existing_files or planned_new_files.",
            "- Use op=create only for planned_new_files. Use op=replace only for existing_files.",
            "- Do not use op=delete in staged_v4 planning.",
            "- Do not include documentation-only files such as README.md as edit targets.",
            "- Do not write boundary/prohibition terms inside the JSON; omit those topics entirely.",
            "- Do not include tests, solution, verifier, logs, results, eval, task.toml, hidden tests, oracle material, or scorer-only material.",
            "- Do not include diffs, code patches, EDIT_JSON, or line-number edits.",
        ]
    )
    prompt = append_qwen_guidance(prompt, qwen_contract_profile, "stage1")
    meta = {k: v for k, v in context.items() if k != "source_context"}
    meta["staged_v4_profile"] = staged_v4_profile
    meta["stage1_max_existing_files"] = max_existing_files
    meta["stage1_max_planned_new_files"] = max_planned_new_files
    meta["stage1_max_edit_targets"] = max_edit_targets
    meta["stage1_max_reason_chars"] = max_reason_chars
    meta["stage1_prompt_chars"] = len(prompt)
    meta["stage1_prompt_sha256"] = runner.sha256_text(prompt)
    meta["qwen_contract_profile"] = qwen_contract_profile
    return prompt, meta


def sanitize_stage_state(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "existing_files": obj.get("existing_files") if isinstance(obj.get("existing_files"), list) else [],
        "planned_new_files": obj.get("planned_new_files") if isinstance(obj.get("planned_new_files"), list) else [],
        "edit_targets": obj.get("edit_targets") if isinstance(obj.get("edit_targets"), list) else [],
    }


def stage_state_forbidden_hits(obj: dict[str, Any]) -> list[str]:
    text = json.dumps(obj, ensure_ascii=False).lower()
    forbidden_regexes = [
        (r"solution\s*/", "solution/"),
        (r"solution\s*/\s*changes\.patch", "solution/changes.patch"),
        (r"tests\s*/", "tests/"),
        (r"test\s*/", "test/"),
        (r"verifier\s*/", "verifier/"),
        (r"logs\s*/", "logs/"),
        (r"results\s*/", "results/"),
        (r"eval\s*/", "eval/"),
        (r"hidden[-_ ]tests?", "hidden test"),
        (r"scorer[-_ ]only", "scorer-only"),
        (r"scorer only", "scorer only"),
        (r"gold patch", "gold patch"),
        (r"oracle", "oracle"),
        (r"task\\.toml", "task.toml"),
        (r"benchmark metadata", "benchmark metadata"),
    ]
    hits = [label for pattern, label in forbidden_regexes if re.search(pattern, text)]
    return sorted(set(hits))


def parse_stage_state(raw: str, task_dir: Path, staged_v4_profile: str = "frozen") -> tuple[dict[str, Any] | None, dict[str, Any]]:
    blocks = [m.group(1).strip() for m in STAGE_STATE_RE.finditer(raw)]
    diag: dict[str, Any] = {"stage_state_blocks": len(blocks), "stage_state_valid": False}
    if len(blocks) != 1:
        diag["failure_reason"] = f"expected_one_stage_state_block_got_{len(blocks)}"
        return None, diag
    try:
        obj = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        diag["failure_reason"] = f"stage_state_json_invalid:{exc}"
        return None, diag
    if not isinstance(obj, dict):
        diag["failure_reason"] = "stage_state_not_object"
        return None, diag
    allowed_keys = {"existing_files", "planned_new_files", "edit_targets"}
    extra_keys = sorted(set(obj) - allowed_keys)
    if extra_keys:
        diag["failure_reason"] = "stage_state_extra_keys"
        diag["extra_keys"] = extra_keys
        return None, diag
    hits = stage_state_forbidden_hits(obj)
    if hits:
        diag["failure_reason"] = "stage_state_forbidden_terms"
        diag["forbidden_hits"] = hits
        return None, diag
    repo = task_dir / "environment" / "repo"
    editable_roots = runner.editable_source_roots_for_task(task_dir)
    allowed_existing_paths = staged_v4_allowed_existing_paths_for_task(task_dir.name)
    max_existing_files = stage1_max_existing_files_for_task(task_dir.name, staged_v4_profile)
    max_planned_new_files = stage1_max_planned_new_files_for_task(task_dir.name, staged_v4_profile)
    max_edit_targets = stage1_max_edit_targets_for_task(task_dir.name, staged_v4_profile)
    max_reason_chars = stage1_max_reason_chars_for_task(task_dir.name, staged_v4_profile)
    diag["staged_v4_profile"] = staged_v4_profile
    diag["max_existing_files"] = max_existing_files
    diag["max_planned_new_files"] = max_planned_new_files
    diag["max_edit_targets"] = max_edit_targets
    diag["max_reason_chars"] = max_reason_chars

    def normalize_stage_path(item: Any, field: str) -> tuple[str | None, dict[str, str] | None]:
        if not isinstance(item, str):
            return None, {"path": str(item), "reason": f"{field}_path_not_string"}
        path, _ = runner.normalize_edit_json_path(item)
        if not runner.is_strict_edit_json_path(path) or not runner.is_claim_bearing_source_path(path):
            return None, {"path": item, "reason": f"{field}_path_not_editable_source"}
        return path, None

    existing_raw = obj.get("existing_files")
    planned_raw = obj.get("planned_new_files")
    targets_raw = obj.get("edit_targets")
    if not isinstance(existing_raw, list):
        diag["failure_reason"] = "stage_state_existing_files_invalid"
        diag["bad_existing_files"] = existing_raw
        return None, diag
    if not isinstance(planned_raw, list):
        diag["failure_reason"] = "stage_state_planned_new_files_invalid"
        diag["bad_planned_new_files"] = planned_raw
        return None, diag
    if not isinstance(targets_raw, list) or not targets_raw:
        diag["failure_reason"] = "stage_state_edit_targets_invalid"
        diag["bad_edit_targets"] = targets_raw
        return None, diag
    if len(existing_raw) > max_existing_files:
        diag["failure_reason"] = "stage_state_too_many_existing_files"
        diag["existing_file_count"] = len(existing_raw)
        diag["max_existing_files"] = max_existing_files
        return None, diag
    if len(planned_raw) > max_planned_new_files:
        diag["failure_reason"] = "stage_state_too_many_planned_new_files"
        diag["planned_new_file_count"] = len(planned_raw)
        diag["max_planned_new_files"] = max_planned_new_files
        return None, diag
    if len(targets_raw) > max_edit_targets:
        diag["failure_reason"] = "stage_state_too_many_edit_targets"
        diag["edit_target_count"] = len(targets_raw)
        diag["max_edit_targets"] = max_edit_targets
        return None, diag

    existing_files: list[str] = []
    planned_new_files: list[str] = []
    bad_existing: list[dict[str, str]] = []
    bad_planned: list[dict[str, str]] = []

    for item in existing_raw:
        path, err = normalize_stage_path(item, "existing")
        if err is not None or path is None:
            bad_existing.append(err or {"path": str(item), "reason": "existing_path_invalid"})
            continue
        src = repo / path
        if (
            not src.exists()
            or not src.is_file()
            or not runner.include_source_file(src)
        ):
            bad_existing.append({"path": item, "reason": "existing_file_not_visible_source"})
            continue
        if allowed_existing_paths is not None and path not in allowed_existing_paths:
            bad_existing.append({"path": item, "reason": "existing_file_not_allowed_for_task"})
            continue
        existing_files.append(path)

    for item in planned_raw:
        path, err = normalize_stage_path(item, "planned_new")
        if err is not None or path is None:
            bad_planned.append(err or {"path": str(item), "reason": "planned_new_path_invalid"})
            continue
        src = repo / path
        if src.exists():
            bad_planned.append({"path": item, "reason": "planned_new_file_already_exists"})
            continue
        if allowed_existing_paths is not None:
            bad_planned.append({"path": item, "reason": "planned_new_file_not_allowed_for_task"})
            continue
        if not runner.path_under_editable_source_roots(path, editable_roots):
            bad_planned.append({"path": item, "reason": "planned_new_path_not_under_editable_source_roots"})
            continue
        planned_new_files.append(path)

    if bad_existing:
        diag["failure_reason"] = "stage_state_existing_files_invalid"
        diag["bad_existing_files"] = bad_existing
        return None, diag
    if bad_planned:
        diag["failure_reason"] = "stage_state_planned_new_files_invalid"
        diag["bad_planned_new_files"] = bad_planned
        return None, diag

    existing_set = set(existing_files)
    planned_set = set(planned_new_files)
    edit_targets: list[dict[str, str]] = []
    bad_targets: list[dict[str, str]] = []
    for idx, target in enumerate(targets_raw):
        if not isinstance(target, dict):
            bad_targets.append({"path": f"<target:{idx}>", "reason": "edit_target_not_object"})
            continue
        op = target.get("op")
        path, err = normalize_stage_path(target.get("path"), "edit_target")
        if err is not None or path is None:
            bad_targets.append(err or {"path": str(target.get("path")), "reason": "edit_target_path_invalid"})
            continue
        if op not in {"create", "replace"}:
            bad_targets.append({"path": path, "reason": f"edit_target_op_invalid:{op}"})
            continue
        if op == "create":
            if path not in planned_set:
                bad_targets.append({"path": path, "reason": "create_target_not_in_planned_new_files"})
                continue
        elif path not in existing_set:
            bad_targets.append({"path": path, "reason": f"{op}_target_not_in_existing_files"})
            continue
        reason = target.get("reason")
        if isinstance(reason, str) and len(reason) > max_reason_chars:
            bad_targets.append({"path": path, "reason": "edit_target_reason_too_long"})
            continue
        edit_targets.append({"path": path, "op": str(op), "reason": reason if isinstance(reason, str) else ""})
    if bad_targets:
        diag["failure_reason"] = "stage_state_edit_targets_invalid"
        diag["bad_edit_targets"] = bad_targets
        return None, diag
    if not existing_files and not planned_new_files:
        diag["failure_reason"] = "stage_state_no_action_files"
        return None, diag

    obj = sanitize_stage_state(
        {
            **obj,
            "existing_files": existing_files,
            "planned_new_files": planned_new_files,
            "edit_targets": edit_targets,
        }
    )
    diag["stage_state_valid"] = True
    diag["stage_state_sha256"] = runner.sha256_text(json.dumps(obj, ensure_ascii=False, sort_keys=True))
    return obj, diag


def render_profiled_repair_prompt(
    task_dir: Path,
    method: str,
    budget: int,
    max_context_chars: int,
    edit_format: str,
    whole_file_max_files: int,
    search_replace_max_edits: int,
    file_op_max_files: int,
    context_mode: str,
    state_contract: str,
    patch_transport: str,
    staged_v4_profile: str,
    qwen_contract_profile: str = "none",
) -> tuple[str, dict[str, Any]]:
    instruction = (task_dir / "instruction.md").read_text(encoding="utf-8", errors="replace")
    context = profiled_repo_context(task_dir, max_context_chars, context_mode, instruction, staged_v4_profile)
    prompt = "\n\n".join(
        [
            "# RoadmapBench Source Repair Task",
            f"Task id: {task_dir.name}",
            f"Staged V4 profile: {staged_v4_profile}",
            "You are given the roadmap/instruction and model-visible base repository source context.",
            "",
            "# Roadmap / Instruction",
            instruction,
            "",
            "# Repository File Tree",
            context["tree"],
            "",
            "# Included Repository Source Files",
            context["source_context"],
            "",
            "# Visibility Boundary",
            "- Do not use or mention solution/changes.patch.",
            "- Do not use or mention tests/ verifier files.",
            "- Edit repository source only, with paths relative to the repository root.",
            "- Do not edit benchmark metadata, task.toml, solution files, verifier tests, logs, or generated results.",
            runner.editable_path_rules(context),
            runner.strict_edit_json_path_scope(context, patch_transport),
            runner.roadmap_coverage_rules(patch_transport if state_contract == "answer_state" else edit_format),
            runner.task_specific_guidance(task_dir.name),
            staged_v4_profile_guidance(task_dir.name, staged_v4_profile),
            runner.method_text(method, budget),
            runner.answer_state_contract(state_contract, patch_transport),
            runner.output_contract(edit_format, whole_file_max_files, search_replace_max_edits, file_op_max_files, state_contract, patch_transport),
        ]
    )
    prompt = append_qwen_guidance(prompt, qwen_contract_profile, "repair")
    meta = {k: v for k, v in context.items() if k != "source_context"}
    meta["edit_format"] = edit_format
    meta["whole_file_max_files"] = whole_file_max_files
    meta["search_replace_max_edits"] = search_replace_max_edits
    meta["file_op_max_files"] = file_op_max_files
    meta["state_contract"] = state_contract
    meta["patch_transport"] = patch_transport
    meta["staged_v4_profile"] = staged_v4_profile
    meta["qwen_contract_profile"] = qwen_contract_profile
    meta["prompt_chars"] = len(prompt)
    meta["prompt_sha256"] = runner.sha256_text(prompt)
    return prompt, meta


def render_stage2_prompt(
    task_dir: Path,
    method: str,
    budget: int,
    max_context_chars: int,
    context_mode: str,
    stage_state: dict[str, Any],
    edit_format: str,
    whole_file_max_files: int,
    search_replace_max_edits: int,
    file_op_max_files: int,
    staged_v4_profile: str,
    qwen_contract_profile: str = "none",
) -> tuple[str, dict[str, Any]]:
    max_edit_targets = stage1_max_edit_targets_for_task(task_dir.name, staged_v4_profile)
    base_prompt, meta = render_profiled_repair_prompt(
        task_dir,
        method,
        budget,
        max_context_chars,
        edit_format,
        whole_file_max_files,
        search_replace_max_edits,
        file_op_max_files,
        context_mode,
        "answer_state",
        "edit_json",
        staged_v4_profile,
        qwen_contract_profile,
    )
    carry = "\n".join(
        [
            "# Staged V4 Carry-In",
            "Use the following source-only planning state as advisory context. If it conflicts with visible source, trust visible source.",
            "In final EDIT_JSON, use create for planned_new_files and use replace only for existing_files.",
            "Do not copy this tag into your final response.",
            "<STAGE_STATE_JSON>",
            json.dumps(stage_state, ensure_ascii=False, sort_keys=True, indent=2),
            "</STAGE_STATE_JSON>",
            "",
            "# Staged V4 Edit Instruction",
            "Now produce the final strict answer-state edit response. Return only <STATE_JSON> and <EDIT_JSON> blocks.",
            f"Use no more than {max_edit_targets} EDIT_JSON ops total.",
            f"Active staged V4 profile: {staged_v4_profile}.",
            "Do not use delete ops in this staged_v4 mode.",
            "Prefer create ops for planned_new_files and small replace anchors for existing_files.",
            "For long existing files, avoid broad block rewrites; use short exact anchors that appear verbatim in the included source.",
            "Do not modify documentation-only files or any file that is not listed as a full-context existing file.",
            staged_v4_task_path_guidance(task_dir.name),
            staged_v4_profile_guidance(task_dir.name, staged_v4_profile),
            qwen_strict_json_guidance(qwen_contract_profile),
        ]
    )
    prompt = base_prompt + "\n\n" + carry
    meta["stage2_prompt_chars"] = len(prompt)
    meta["stage2_prompt_sha256"] = runner.sha256_text(prompt)
    return prompt, meta


def build_tier1_plan(run_dir: Path, args: argparse.Namespace) -> list[dict[str, Any]]:
    prompts_dir = run_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    stage1_dir = run_dir / "stage1_prompts"
    stage1_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    idx = 0
    for task_id in args.tasks:
        task_dir = runner.TASKS_ROOT / task_id
        for arm in args.arms:
            for method in args.methods:
                for rep in range(args.reps):
                    idx += 1
                    run_id = f"tier1__{arm}__{task_id}__{method}__rep{rep}"
                    base = {
                        "row_index": idx,
                        "run_id": run_id,
                        "task_id": task_id,
                        "method": method,
                        "condition": arm,
                        "arm": arm,
                        "repeat_index": rep,
                        "budget": args.budget,
                        "edit_format": "file_ops_json",
                        "patch_transport": "edit_json",
                        "state_contract": "answer_state",
                        "model": args.model,
                    }
                    if arm == "single_shot_v3":
                        prompt, meta = render_profiled_repair_prompt(
                            task_dir,
                            method,
                            args.budget,
                            args.max_context_chars,
                            "file_ops_json",
                            args.whole_file_max_files,
                            args.search_replace_max_edits,
                            args.file_op_max_files,
                            args.context_mode,
                            "answer_state",
                            "edit_json",
                            args.staged_v4_profile,
                            args.qwen_contract_profile,
                        )
                        prompt_path = prompts_dir / f"{run_id}.txt"
                        prompt_path.write_text(prompt, encoding="utf-8")
                        rows.append({**base, "prompt_path": str(prompt_path), **meta})
                    elif arm == "staged_v4":
                        stage1_prompt, stage1_meta = render_stage1_prompt(
                            task_dir,
                            method,
                            args.budget,
                            args.max_context_chars,
                            args.context_mode,
                            args.staged_v4_profile,
                            args.qwen_contract_profile,
                        )
                        stage1_path = stage1_dir / f"{run_id}.txt"
                        stage1_path.write_text(stage1_prompt, encoding="utf-8")
                        placeholder_prompt = (
                            "# Staged V4 row placeholder\n"
                            "The executable edit prompt is generated after Stage 1 planning during execution.\n"
                        )
                        prompt_path = prompts_dir / f"{run_id}.txt"
                        prompt_path.write_text(placeholder_prompt, encoding="utf-8")
                        rows.append({**base, "prompt_path": str(prompt_path), "stage1_prompt_path": str(stage1_path), **stage1_meta})
                    else:
                        raise ValueError(f"unknown arm: {arm}")
    plan = {
        "created_utc": runner.utc_now(),
        "tier": "tier1",
        "rows": rows,
        "tasks": args.tasks,
        "arms": args.arms,
        "methods": args.methods,
        "reps": args.reps,
        "planned_rows": len(rows),
        "api_calls": "single_shot_v3 rows use one call; staged_v4 rows use stage1 plus stage2 plus at most one edit repair call",
        "staged_v4_profile": args.staged_v4_profile,
        "qwen_contract_profile": args.qwen_contract_profile,
    }
    write_json(run_dir / "RUN_PLAN.json", plan)
    (run_dir / "RUN_PLAN.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    return rows


def compact_api_meta(
    body: dict[str, Any],
    prompt: str,
    provider: str,
    url: str,
    api_key_env: str,
    stage: str,
    *,
    prompt_path: str | None = None,
    timeout_seconds: float | None = None,
    api_attempts: int | None = None,
) -> dict[str, Any]:
    return runner.compact_api_request_meta(
        body,
        prompt,
        provider,
        url,
        api_key_env,
        stage=stage,
        prompt_path=prompt_path,
        timeout_seconds=timeout_seconds,
        api_attempts=api_attempts,
    )


def validate_stage2_edit_against_stage_state(row_dir: Path, stage_state: dict[str, Any], task_id: str, staged_v4_profile: str = "frozen") -> dict[str, Any]:
    max_edit_targets = stage1_max_edit_targets_for_task(task_id, staged_v4_profile)
    edit_path = row_dir / "candidate_edit.json"
    diag: dict[str, Any] = {
        "stage2_stage_contract_valid": False,
        "staged_v4_profile": staged_v4_profile,
        "max_ops": max_edit_targets,
        "op_statuses": [],
    }
    if not edit_path.exists():
        diag["failure_reason"] = "candidate_edit_missing"
        return diag
    try:
        payload = json.loads(edit_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        diag["failure_reason"] = f"candidate_edit_json_invalid:{exc}"
        return diag
    ops = payload.get("edit", {}).get("ops") if isinstance(payload, dict) else None
    if not isinstance(ops, list) or not ops:
        diag["failure_reason"] = "candidate_edit_ops_invalid"
        return diag
    if len(ops) > max_edit_targets:
        diag["failure_reason"] = "stage2_too_many_edit_ops"
        diag["op_count"] = len(ops)
        return diag

    existing_set = set(stage_state.get("existing_files") or [])
    planned_set = set(stage_state.get("planned_new_files") or [])
    target_ops: dict[str, set[str]] = defaultdict(set)
    for target in stage_state.get("edit_targets") or []:
        if isinstance(target, dict) and isinstance(target.get("path"), str) and isinstance(target.get("op"), str):
            target_ops[target["path"]].add(target["op"])

    bad: list[dict[str, Any]] = []
    for idx, op_obj in enumerate(ops):
        status: dict[str, Any] = {"index": idx, "status": "pending"}
        if not isinstance(op_obj, dict):
            status.update({"status": "failed", "failure_reason": "op_not_object"})
            bad.append(status)
            diag["op_statuses"].append(status)
            continue
        op = op_obj.get("op")
        raw_path = op_obj.get("path")
        if not isinstance(raw_path, str):
            status.update({"status": "failed", "failure_reason": "path_not_string"})
            bad.append(status)
            diag["op_statuses"].append(status)
            continue
        path, normalized = runner.normalize_edit_json_path(raw_path)
        status.update({"op": op, "path": path, "path_normalized_leading_dot_slash": normalized})
        if op not in {"create", "replace"}:
            status.update({"status": "failed", "failure_reason": f"op_not_allowed:{op}"})
            bad.append(status)
        elif path not in target_ops or op not in target_ops[path]:
            status.update({"status": "failed", "failure_reason": "op_not_in_stage1_edit_targets"})
            bad.append(status)
        elif op == "create" and path not in planned_set:
            status.update({"status": "failed", "failure_reason": "create_path_not_in_planned_new_files"})
            bad.append(status)
        elif op == "replace" and path not in existing_set:
            status.update({"status": "failed", "failure_reason": "replace_path_not_in_existing_files"})
            bad.append(status)
        else:
            status["status"] = "accepted"
        diag["op_statuses"].append(status)

    if bad:
        diag["failure_reason"] = "stage2_edit_outside_stage_state"
        diag["bad_ops"] = bad
        return diag
    diag["stage2_stage_contract_valid"] = True
    diag["op_count"] = len(ops)
    diag["files"] = sorted({item["path"] for item in diag["op_statuses"] if item.get("path")})
    return diag


def fail_result_on_stage2_contract(result: dict[str, Any], diag: dict[str, Any]) -> dict[str, Any]:
    if diag.get("stage2_stage_contract_valid"):
        result["stage2_stage_contract_valid"] = True
        return result
    result.update(
        {
            "stage2_stage_contract_valid": False,
            "stage2_stage_contract_failure": diag.get("failure_reason"),
            "candidate_validate_ok": False,
            "deterministic_edit_apply_success": False,
            "deterministic_patch_generated": False,
            "patch_apply_check_ok": False,
            "candidate_patch_applies": False,
            "docker_scored": False,
            "test_passed": False,
            "answer_success": False,
            "action_governance_success": False,
            "state_governance_success": False,
            "reliable_composite_success": False,
            "failure_step": "stage2_contract_failed",
            "failure_reason": diag.get("failure_reason"),
            "final_failure_category": "stage2_contract_failed",
        }
    )
    return result


def generate_staged_v4(run_dir: Path, row: dict[str, Any], args: argparse.Namespace, provider_info: tuple[str, str, str, str]) -> dict[str, Any]:
    row_dir = runner.row_dir_for(run_dir, row)
    row_dir.mkdir(parents=True, exist_ok=True)
    provider, url, api_key_env, model = provider_info
    task_dir = runner.TASKS_ROOT / row["task_id"]
    stage1_prompt_path = Path(row["stage1_prompt_path"])
    stage1_prompt = stage1_prompt_path.read_text(encoding="utf-8")
    stage1_dir = row_dir / "stage1"
    stage1_dir.mkdir(parents=True, exist_ok=True)
    (stage1_dir / "prompt.txt").write_text(stage1_prompt, encoding="utf-8")
    try:
        body, response = runner.call_model(stage1_prompt, provider, url, api_key_env, model, args.stage1_max_tokens, args.timeout_seconds, args.api_attempts)
        body_for_log = compact_api_meta(
            body,
            stage1_prompt,
            provider,
            url,
            api_key_env,
            "stage1_plan",
            prompt_path=str(stage1_dir / "prompt.txt"),
            timeout_seconds=args.timeout_seconds,
            api_attempts=args.api_attempts,
        )
        write_json(stage1_dir / "api_request_meta.json", body_for_log)
        write_json(stage1_dir / "api_request_body_redacted.json", runner.redacted_api_request_body(body))
        write_json(stage1_dir / "api_response_payload.json", response["payload"])
        write_json(stage1_dir / "api_response_meta.json", response["meta"])
        raw = response["payload"]["choices"][0]["message"]["content"]
        (stage1_dir / "raw_response.txt").write_text(raw, encoding="utf-8")
        response_diag = runner.response_diagnostics(response["payload"])
        stage_state, stage_diag = parse_stage_state(raw, task_dir, args.staged_v4_profile)
        write_json(stage1_dir / "stage_state_diagnostics.json", stage_diag)
        if response_diag.get("finish_reason") == "length" or stage_state is None:
            failure_reason = "stage1_finish_reason_length" if response_diag.get("finish_reason") == "length" else stage_diag.get("failure_reason")
            return {
                **row,
                **{f"stage1_{k}": v for k, v in response_diag.items()},
                "generation_ok": False,
                "extract_ok": False,
                "candidate_validate_ok": False,
                "stage1_success": False,
                "failure_step": "stage1_plan_failed",
                "failure_reason": failure_reason,
                "final_failure_category": "stage1_plan_failed",
                "timestamp_utc": runner.utc_now(),
            }
        write_json(stage1_dir / "stage_state.json", stage_state)
        stage2_prompt, stage2_meta = render_stage2_prompt(
            task_dir,
            row["method"],
            row["budget"],
            args.max_context_chars,
            args.context_mode,
            stage_state,
            "file_ops_json",
            args.whole_file_max_files,
            args.search_replace_max_edits,
            stage1_max_edit_targets_for_task(row["task_id"], args.staged_v4_profile),
            args.staged_v4_profile,
            args.qwen_contract_profile,
        )
        prompt_path = run_dir / "prompts" / f"{row['run_id']}.txt"
        prompt_path.write_text(stage2_prompt, encoding="utf-8")
        row = {**row, **stage2_meta, "prompt_path": str(prompt_path), "stage1_success": True}
        args_for_generate = generation_args(args)
        args_for_generate.repair_attempts = args.v4_repair_attempts
        args_for_generate.file_op_max_files = stage1_max_edit_targets_for_task(row["task_id"], args.staged_v4_profile)
        result = runner.generate_one(run_dir, row, args_for_generate, provider_info)
        stage2_contract_diag = validate_stage2_edit_against_stage_state(row_dir, stage_state, row["task_id"], args.staged_v4_profile)
        write_json(row_dir / "stage2_stage_contract_diagnostics.json", stage2_contract_diag)
        result = fail_result_on_stage2_contract(result, stage2_contract_diag)
        result.update({
            "stage1_success": True,
            "stage1_finish_reason": response_diag.get("finish_reason"),
            "stage1_prompt_tokens": response_diag.get("prompt_tokens"),
            "stage1_completion_tokens": response_diag.get("completion_tokens"),
            "stage1_total_tokens": response_diag.get("total_tokens"),
            "stage1_state_valid": bool(stage_diag.get("stage_state_valid")),
            "stage1_state_sha256": stage_diag.get("stage_state_sha256"),
        })
        return result
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, runner.APINoResponseTimeout):
            write_json(stage1_dir / "api_request_meta.json", exc.meta)
            write_json(stage1_dir / "api_request_body_redacted.json", runner.redacted_api_request_body(exc.body))
        write_json(stage1_dir / "api_error.json", {"timestamp_utc": runner.utc_now(), "error_type": type(exc).__name__, "error": str(exc)})
        failure_step = "api_no_response_timeout" if isinstance(exc, runner.APINoResponseTimeout) else "stage1_generation_failed"
        return {
            **row,
            "generation_ok": False,
            "extract_ok": False,
            "candidate_validate_ok": False,
            "stage1_success": False,
            "deterministic_edit_apply_success": False,
            "deterministic_patch_generated": False,
            "patch_apply_check_ok": False,
            "candidate_patch_applies": False,
            "docker_scored": False,
            "test_passed": False,
            "answer_success": False,
            "action_governance_success": False,
            "state_governance_success": False,
            "reliable_composite_success": False,
            "transport_failure": isinstance(exc, runner.APINoResponseTimeout),
            "model_quality_scored": False if isinstance(exc, runner.APINoResponseTimeout) else None,
            "failure_step": failure_step,
            "failure_reason": str(exc),
            "final_failure_category": failure_step,
            "timestamp_utc": runner.utc_now(),
        }


def generate_row(run_dir: Path, row: dict[str, Any], args: argparse.Namespace, provider_info: tuple[str, str, str, str]) -> dict[str, Any]:
    if row["arm"] == "single_shot_v3":
        args_for_generate = generation_args(args)
        args_for_generate.repair_attempts = args.v3_repair_attempts
        return runner.generate_one(run_dir, row, args_for_generate, provider_info)
    if row["arm"] == "staged_v4":
        return generate_staged_v4(run_dir, row, args, provider_info)
    raise ValueError(f"unknown arm: {row['arm']}")


def generation_args(args: argparse.Namespace) -> argparse.Namespace:
    out = argparse.Namespace(**vars(args))
    out.edit_format = "file_ops_json"
    out.state_contract = "answer_state"
    out.patch_transport = "edit_json"
    return out


def optional_int_arg(value: str) -> int | None:
    if value.lower() in {"none", "null", "omit", "provider"}:
        return None
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be a positive integer or 'none'")
    return parsed


def latest_rows(result_path: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    if not result_path.exists():
        return latest
    for line in result_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["run_id"]] = row
    return latest


def score_rows(run_dir: Path, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    result_path = run_dir / "RESULTS.jsonl"
    latest = latest_rows(result_path)
    for row in rows:
        gen = latest.get(row["run_id"])
        if not gen or not gen.get("candidate_validate_ok"):
            continue
        if gen.get("docker_scored") and not args.force_score:
            continue
        eval_result = runner.evaluate_patch(run_dir, row, gen, args.skip_docker_on_invalid_patch)
        merged = {**gen, **eval_result, "timestamp_utc": runner.utc_now()}
        runner.append_jsonl(result_path, merged)
        print(
            json.dumps(
                {
                    "stage": "scored",
                    "run_id": row["run_id"],
                    "arm": row["arm"],
                    "reward": eval_result.get("reward"),
                    "passed": eval_result.get("test_passed"),
                    "applies": eval_result.get("candidate_patch_applies"),
                    "patch_check": eval_result.get("patch_apply_check_ok"),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )


def summarize(run_dir: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    vals = list(latest_rows(run_dir / "RESULTS.jsonl").values())
    row_lookup = {row["run_id"]: row for row in rows}
    for item in vals:
        item.update({k: v for k, v in row_lookup.get(item["run_id"], {}).items() if k not in item})

    def count(items: list[dict[str, Any]], key: str) -> int:
        return sum(1 for item in items if item.get(key))

    by_arm: dict[str, dict[str, Any]] = {}
    by_task_arm: dict[str, dict[str, Any]] = {}
    by_method_arm: dict[str, dict[str, Any]] = {}
    for arm in sorted({row.get("arm") for row in vals if row.get("arm")}):
        items = [row for row in vals if row.get("arm") == arm]
        by_arm[arm] = aggregate_items(items)
    for task in sorted({row.get("task_id") for row in vals if row.get("task_id")}):
        for arm in sorted({row.get("arm") for row in vals if row.get("arm")}):
            items = [row for row in vals if row.get("task_id") == task and row.get("arm") == arm]
            by_task_arm[f"{task}__{arm}"] = aggregate_items(items)
    for method in sorted({row.get("method") for row in vals if row.get("method")}):
        for arm in sorted({row.get("arm") for row in vals if row.get("arm")}):
            items = [row for row in vals if row.get("method") == method and row.get("arm") == arm]
            by_method_arm[f"{method}__{arm}"] = aggregate_items(items)
    summary = {
        "updated_utc": runner.utc_now(),
        "planned_rows": len(rows),
        "result_rows": len(vals),
        "generation_ok": count(vals, "generation_ok"),
        "extract_ok": count(vals, "extract_ok"),
        "candidate_validate_ok": count(vals, "candidate_validate_ok"),
        "patch_apply_check_ok": count(vals, "patch_apply_check_ok"),
        "candidate_applies": count(vals, "candidate_patch_applies"),
        "docker_scored": count(vals, "docker_scored"),
        "test_passed": count(vals, "test_passed"),
        "answer_success": sum(1 for row in vals if row.get("answer_success") or row.get("test_passed")),
        "state_contract_valid": count(vals, "state_contract_valid"),
        "action_governance_success": sum(1 for row in vals if row.get("action_governance_success") or row.get("state_governance_success")),
        "reliable_composite_success": count(vals, "reliable_composite_success"),
        "length_finished": sum(1 for row in vals if row.get("finish_reason") == "length" or row.get("stage1_finish_reason") == "length"),
        "failure_steps": dict(Counter(str(row.get("failure_step")) for row in vals if row.get("failure_step"))),
        "arms": dict(Counter(str(row.get("arm")) for row in vals if row.get("arm"))),
        "by_arm": by_arm,
        "by_task_arm": by_task_arm,
        "by_method_arm": by_method_arm,
    }
    write_json(run_dir / "SUMMARY.json", summary)
    write_summary_md(run_dir, summary)
    return summary


def aggregate_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {
            "rows": 0,
            "generation_ok": 0,
            "extract_ok": 0,
            "patch_apply_check_ok": 0,
            "candidate_applies": 0,
            "docker_scored": 0,
            "test_passed": 0,
            "answer_success": 0,
            "state_contract_valid": 0,
            "action_governance_success": 0,
            "reliable_composite_success": 0,
            "avg_reward": 0.0,
        }
    return {
        "rows": len(items),
        "generation_ok": sum(1 for row in items if row.get("generation_ok")),
        "extract_ok": sum(1 for row in items if row.get("extract_ok")),
        "patch_apply_check_ok": sum(1 for row in items if row.get("patch_apply_check_ok")),
        "candidate_applies": sum(1 for row in items if row.get("candidate_patch_applies")),
        "docker_scored": sum(1 for row in items if row.get("docker_scored")),
        "test_passed": sum(1 for row in items if row.get("test_passed")),
        "answer_success": sum(1 for row in items if row.get("answer_success") or row.get("test_passed")),
        "state_contract_valid": sum(1 for row in items if row.get("state_contract_valid")),
        "action_governance_success": sum(1 for row in items if row.get("action_governance_success") or row.get("state_governance_success")),
        "reliable_composite_success": sum(1 for row in items if row.get("reliable_composite_success")),
        "avg_reward": round(sum((row.get("reward") or 0.0) for row in items) / len(items), 4),
    }


def write_summary_md(run_dir: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# RoadmapBench Tier 1 Matched V3/V4 Summary",
        "",
        f"Updated: {summary['updated_utc']}",
        "",
        "## Aggregate",
        "",
        f"- Planned rows: {summary['planned_rows']}",
        f"- Result rows: {summary['result_rows']}",
        f"- Generation ok: {summary['generation_ok']}",
        f"- Extract ok: {summary['extract_ok']}",
        f"- Candidate validate ok: {summary['candidate_validate_ok']}",
        f"- Patch apply-check ok: {summary['patch_apply_check_ok']}",
        f"- Candidate applies: {summary['candidate_applies']}",
        f"- Docker scored: {summary['docker_scored']}",
        f"- Test passed / answer success: {summary['answer_success']}",
        f"- State contract valid: {summary['state_contract_valid']}",
        f"- Action governance success: {summary['action_governance_success']}",
        f"- Reliable composite success: {summary['reliable_composite_success']}",
        f"- Finish reason length count: {summary['length_finished']}",
        "",
        "## By Arm",
        "",
        "| Arm | Rows | Generated | Extracted | Apply-check | Applies | Docker | Answer | State contract | Action gov | Reliable | Avg reward |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, item in summary["by_arm"].items():
        lines.append(
            f"| `{arm}` | {item['rows']} | {item['generation_ok']} | {item['extract_ok']} | {item['patch_apply_check_ok']} | "
            f"{item['candidate_applies']} | {item['docker_scored']} | {item['answer_success']} | {item['state_contract_valid']} | "
            f"{item['action_governance_success']} | {item['reliable_composite_success']} | {item['avg_reward']} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is a RoadmapBench/SWE-EVO-style external real-code diagnostic.",
            "- This is not an official SWE-bench result.",
            "- This is not a PCG replication.",
            "- The six labels are prompt variants unless a later implementation proves behaviorally distinct multi-turn methods.",
        ]
    )
    (run_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(run_dir: Path, summary: dict[str, Any], prompt_audit: dict[str, Any] | None = None) -> Path:
    outputs = ROOT / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    report_path = outputs / "ROADMAPBENCH_TIER1_MATCHED_V3_V4_48ROW_REPORT_20260705.md"
    lines = [
        "# RoadmapBench Tier 1 Matched V3/V4 48-Row Report",
        "",
        "Date: 2026-07-05",
        "",
        "## Design",
        "",
        "- Tasks: `tpl-3.2.0-roadmap`, `glz-3.0.0-roadmap`.",
        "- Arms: matched single-shot V3 baseline and staged V4.",
        "- Prompt variants: six labels, descriptive only.",
        "- Repeats: 2 per task x arm x prompt variant cell.",
        "- Planned rows: 48.",
        "- Provider route: direct DeepSeek, not OpenRouter.",
        "",
        "## Aggregate Counts",
        "",
        f"- planned_rows: {summary['planned_rows']}",
        f"- result_rows: {summary['result_rows']}",
        f"- generation_ok: {summary['generation_ok']}",
        f"- extract_ok: {summary['extract_ok']}",
        f"- patch_apply_check_ok: {summary['patch_apply_check_ok']}",
        f"- candidate_applies: {summary['candidate_applies']}",
        f"- docker_scored: {summary['docker_scored']}",
        f"- answer_success: {summary['answer_success']}",
        f"- state_contract_valid: {summary['state_contract_valid']}",
        f"- action_governance_success: {summary['action_governance_success']}",
        f"- reliable_composite_success: {summary['reliable_composite_success']}",
        f"- finish_reason_length_count: {summary['length_finished']}",
        "",
        "## By Arm",
        "",
        "| Arm | Rows | Generated | Extracted | Apply-check | Docker | Answer | Action gov | Reliable | Avg reward |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, item in summary["by_arm"].items():
        lines.append(
            f"| `{arm}` | {item['rows']} | {item['generation_ok']} | {item['extract_ok']} | {item['patch_apply_check_ok']} | "
            f"{item['docker_scored']} | {item['answer_success']} | {item['action_governance_success']} | {item['reliable_composite_success']} | {item['avg_reward']} |"
        )
    if prompt_audit is not None:
        lines.extend(
            [
                "",
                "## Prompt Visibility Audit",
                "",
                f"- prompt_files_scanned: {prompt_audit.get('prompt_files_scanned')}",
                f"- initial_prompts_scanned: {prompt_audit.get('initial_prompts_scanned')}",
                f"- attempt_prompts_scanned: {prompt_audit.get('attempt_prompts_scanned')}",
                f"- missing_attempt_prompt_artifacts: {len(prompt_audit.get('missing_attempt_prompt_artifacts') or [])}",
                f"- failure_count: {prompt_audit.get('failure_count')}",
                f"- feedback_leak_audit_failures: {prompt_audit.get('feedback_leak_audit_failures')}",
            ]
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This is a RoadmapBench/SWE-EVO-style external real-code diagnostic. It is not an official SWE-bench result, not a PCG replication, and not a method-superiority claim. The six labels are reported as prompt variants unless their multi-turn behavior is separately implemented and validated.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", default="roadmapbench_tier1_matched_v3_v4_48row_20260705")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--provider", choices=["auto", "deepseek", "openrouter", "dashscope"], default="deepseek")
    parser.add_argument("--model", default=runner.DEFAULT_MODEL)
    parser.add_argument("--tasks", nargs="*", default=DEFAULT_TASKS)
    parser.add_argument("--arms", nargs="*", default=DEFAULT_ARMS)
    parser.add_argument("--methods", nargs="*", default=runner.METHODS)
    parser.add_argument("--reps", type=int, default=2)
    parser.add_argument("--budget", type=int, default=600)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--context-mode", choices=["full", "targeted"], default="targeted")
    parser.add_argument("--max-context-chars", type=int, default=140000)
    parser.add_argument("--max-tokens", type=optional_int_arg, default=32768)
    parser.add_argument("--stage1-max-tokens", type=optional_int_arg, default=8192)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--api-attempts", type=int, default=5)
    parser.add_argument("--whole-file-max-files", type=int, default=3)
    parser.add_argument("--search-replace-max-edits", type=int, default=6)
    parser.add_argument("--file-op-max-files", type=int, default=8)
    parser.add_argument("--v3-repair-attempts", type=int, default=0)
    parser.add_argument("--v4-repair-attempts", type=int, default=1)
    parser.add_argument("--staged-v4-profile", choices=STAGED_V4_PROFILES, default="frozen")
    parser.add_argument("--qwen-contract-profile", choices=QWEN_CONTRACT_PROFILES, default="none")
    parser.add_argument("--skip-docker-on-invalid-patch", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--force-score", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if set(args.methods) - set(runner.METHODS):
        raise SystemExit(f"unknown methods: {sorted(set(args.methods) - set(runner.METHODS))}")
    if set(args.arms) - set(DEFAULT_ARMS):
        raise SystemExit(f"unknown arms: {sorted(set(args.arms) - set(DEFAULT_ARMS))}")
    if args.reps < 1:
        raise SystemExit("--reps must be >= 1")
    if args.staged_v4_profile in {"fal_capacity_diagnostic", "fal_capacity_reason_v2"}:
        non_fal_tasks = [task for task in args.tasks if not task.startswith("fal-")]
        non_staged_arms = [arm for arm in args.arms if arm != "staged_v4"]
        if non_fal_tasks or non_staged_arms:
            raise SystemExit(
                f"--staged-v4-profile {args.staged_v4_profile} is restricted to FAL staged_v4 diagnostic runs; "
                f"non_fal_tasks={non_fal_tasks}, non_staged_arms={non_staged_arms}"
            )

    runner.load_env_file(args.env_file)
    provider_info = runner.resolve_provider(args.provider, args.model)
    provider, url, api_key_env, resolved_model = provider_info
    run_dir = runner.RUNS_ROOT / args.run_name
    if run_dir.exists() and not (args.resume or args.score_only or args.dry_run):
        raise SystemExit(f"run directory exists; pass --resume or choose another --run-name: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    runner.ensure_tmp_tasks(args.tasks)
    plan_path = run_dir / "RUN_PLAN.json"
    if plan_path.exists():
        rows = read_json(plan_path)["rows"]
    else:
        rows = build_tier1_plan(run_dir, args)
    run_config = {
        "created_utc": runner.utc_now(),
        "run_name": args.run_name,
        "tier": "tier1",
        "tasks": args.tasks,
        "tasks_root": str(runner.TASKS_ROOT),
        "tmp_task_root": str(runner.TMP_TASK_ROOT),
        "arms": args.arms,
        "methods": args.methods,
        "reps": args.reps,
        "planned_rows": len(rows),
        "jobs": args.jobs,
        "provider": provider,
        "api_key_env": api_key_env,
        "model": resolved_model,
        "route_resolution": runner.route_resolution_metadata(provider, url, api_key_env, resolved_model),
        "env_key_present": bool(__import__("os").getenv(api_key_env)),
        "env_file_used": bool(args.env_file),
        "env_file_path_redacted": bool(args.env_file),
        "state_contract": "answer_state",
        "patch_transport": "edit_json",
        "edit_format": "file_ops_json",
        "budget": args.budget,
        "context_mode": args.context_mode,
        "max_context_chars": args.max_context_chars,
        "whole_file_max_files": args.whole_file_max_files,
        "search_replace_max_edits": args.search_replace_max_edits,
        "file_op_max_files": args.file_op_max_files,
        "v3_repair_attempts": args.v3_repair_attempts,
        "v4_repair_attempts": args.v4_repair_attempts,
        "staged_v4_profile": args.staged_v4_profile,
        "qwen_contract_profile": args.qwen_contract_profile,
        "max_tokens": args.max_tokens,
        "stage1_max_tokens": args.stage1_max_tokens,
        "timeout_seconds": args.timeout_seconds,
        "api_attempts": args.api_attempts,
        "api_request_surface": runner.api_request_surface_for_config(provider, resolved_model, args.max_tokens),
        "stage1_api_request_surface": runner.api_request_surface_for_config(provider, resolved_model, args.stage1_max_tokens),
        "skip_docker_on_invalid_patch": args.skip_docker_on_invalid_patch,
    }
    write_json(run_dir / "RUN_CONFIG.json", run_config)
    write_json(run_dir / "ROUTE_RESOLUTION.json", run_config["route_resolution"])
    runner.append_jsonl(run_dir / "RUN_INVOCATIONS.jsonl", run_config)
    print(json.dumps({"stage": "planned", "run_dir": str(run_dir), "planned_rows": len(rows)}, ensure_ascii=False), flush=True)
    if args.dry_run:
        summarize(run_dir, rows)
        return 0
    if not args.score_only:
        if not __import__("os").getenv(api_key_env):
            raise SystemExit(f"{api_key_env} is not set; pass --env-file or export it before running")
        result_path = run_dir / "RESULTS.jsonl"
        latest = latest_rows(result_path) if args.resume else {}
        # Resume must only fill rows with no recorded result. Failed rows are
        # claim-bearing outcomes, not invitations for another model draw.
        generation_rows = [row for row in rows if row["run_id"] not in latest]
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
            futures = [executor.submit(generate_row, run_dir, row, args, provider_info) for row in generation_rows]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                runner.append_jsonl(result_path, result)
                print(
                    json.dumps(
                        {
                            "stage": "generated",
                            "run_id": result["run_id"],
                            "arm": result.get("arm"),
                            "ok": result.get("candidate_validate_ok"),
                            "finish_reason": result.get("finish_reason"),
                            "failure": result.get("failure_step"),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    score_rows(run_dir, rows, args)
    summary = summarize(run_dir, rows)
    print(json.dumps({"stage": "summary", **{k: summary[k] for k in ("planned_rows", "result_rows", "answer_success", "action_governance_success", "length_finished")}}, ensure_ascii=False), flush=True)
    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
