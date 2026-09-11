#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import hashlib
import http.client
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
TASKS_ROOT = Path(os.environ.get("ROADMAPBENCH_TASKS_ROOT", ROOT / "data" / "roadmapbench_10")).expanduser()
ROADMAPBENCH_ROOT = ROOT / "RoadmapBench"
RUNS_ROOT = ROOT / "runs"
TMP_TASK_ROOT = Path(
    os.environ.get("ROADMAPBENCH_TMP_TASK_ROOT", str(Path(tempfile.gettempdir()) / "roadmapbench_10_deepseek"))
).expanduser()

METHODS = [
    "loop_only",
    "rolling_summary",
    "rolling_visible_carry_forward",
    "rolling_visible_fields_only",
    "ssr_no_visible_carry",
    "mature_ssr_loop",
]

DEFAULT_TASKS = [
    "tpl-3.2.0-roadmap",
    "fal-1.3.0-roadmap",
    "mko-3.0.0-roadmap",
    "opt-2.0.0-roadmap",
    "glz-3.0.0-roadmap",
]

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_OPENROUTER_MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
FENCE_RE = re.compile(r"```(?:diff|patch)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
STATE_JSON_BLOCK_RE = re.compile(r"<STATE_JSON>\s*(.*?)\s*</STATE_JSON>", re.DOTALL | re.IGNORECASE)
PATCH_BLOCK_RE = re.compile(r"<PATCH>\s*(.*?)\s*</PATCH>", re.DOTALL | re.IGNORECASE)
EDIT_JSON_BLOCK_RE = re.compile(r"<EDIT_JSON>\s*(.*?)\s*</EDIT_JSON>", re.DOTALL | re.IGNORECASE)
JSONL_LOCK = Lock()


class APINoResponseTimeout(TimeoutError):
    def __init__(self, message: str, *, body: dict[str, Any], meta: dict[str, Any]):
        super().__init__(message)
        self.body = body
        self.meta = meta

SOURCE_EXTS = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hpp",
    ".hh",
    ".hxx",
    ".java",
    ".kt",
    ".scala",
    ".rb",
    ".php",
    ".cs",
    ".m",
    ".mm",
    ".swift",
)
CONFIG_EXTS = (".toml", ".json", ".yaml", ".yml", ".cfg", ".ini", ".cmake")
TEXT_EXTS = SOURCE_EXTS + CONFIG_EXTS + (".md", ".rst", ".txt")
SOURCE_FILENAMES = {"CMakeLists.txt", "Makefile", "Dockerfile"}
FORBIDDEN_PATH_PREFIXES = (
    "tests/",
    "test/",
    "solution/",
    "logs/",
    "results/",
    "verifier/",
    "eval/",
    ".git/",
    "__pycache__/",
)
FORBIDDEN_PATH_NAMES = {"task.toml"}
OUTPUT_BEARING_STATE_FIELDS = ("OUT", "ALW", "G", "CK")
EXCLUSION_STATE_FIELDS = ("NO", "B")
STATE_CONFLICT_TOKENS = (
    "tests/",
    "test/",
    "solution/",
    "solution/changes.patch",
    "logs/",
    "results/",
    "verifier/",
    "eval/",
    "task.toml",
    "benchmark metadata",
)
LEAKAGE_TERMS = (
    "gold",
    "oracle",
    "solution",
    "hidden-test",
    "hidden test",
    "hidden_tests",
    "scorer-only",
    "scorer only",
)
ANSWER_STATE_FAILURE_STEPS = {
    "generation_failed",
    "finish_reason_length",
    "state_json_missing",
    "state_json_invalid",
    "edit_json_missing",
    "edit_json_invalid",
    "edit_ops_empty",
    "edit_path_disallowed",
    "edit_anchor_not_found",
    "edit_anchor_ambiguous",
    "edit_apply_failed",
    "deterministic_patch_generation_failed",
    "patch_block_missing",
    "patch_diff_missing",
    "patch_file_scope_invalid",
    "patch_apply_failed",
    "docker_verifier_failed",
    "test_failed",
    "test_passed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def serialized_api_request_body(body: dict[str, Any]) -> bytes:
    """Match the HTTP request body serialization used by call_model."""
    return json.dumps(body).encode("utf-8")


def infer_base_url_region(url: str) -> str | None:
    host = urlparse(url).netloc
    match = re.search(r"\b((?:cn|us|eu|ap|me|sa|af)-[a-z]+(?:-[a-z]+)*(?:-\d+)?)\b", host)
    if match:
        return match.group(1)
    if "deepseek.com" in host:
        return "deepseek_direct"
    if "openrouter.ai" in host:
        return "openrouter"
    return None


def provider_cache_policy(provider: str) -> dict[str, Any]:
    if provider == "dashscope":
        return {
            "cache_mode": "implicit_only",
            "explicit_cache": False,
            "cache_as_treatment_variable": False,
        }
    if provider == "deepseek":
        return {
            "cache_mode": "implicit_provider_side",
            "explicit_cache": False,
            "cache_as_treatment_variable": False,
        }
    return {
        "cache_mode": "provider_default_or_not_exposed",
        "explicit_cache": False,
        "cache_as_treatment_variable": False,
    }


def planned_api_request_body(provider: str, model: str, max_tokens: int | None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": "<ROW_PROMPT_PLACEHOLDER>"}],
        "temperature": 0,
        "stream": False,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if provider == "deepseek":
        body["thinking"] = {"type": "disabled"}
    if provider == "dashscope":
        body["enable_thinking"] = False
    return body


def request_parameter_surface(body: dict[str, Any], provider: str) -> dict[str, Any]:
    candidates = (
        "temperature",
        "top_p",
        "top_k",
        "repetition_penalty",
        "frequency_penalty",
        "presence_penalty",
        "reasoning_effort",
        "seed",
        "stop",
        "logit_bias",
        "response_format",
        "tools",
        "tool_choice",
        "stream",
        "max_tokens",
        "thinking",
        "enable_thinking",
    )
    sent = {key: body[key] for key in candidates if key in body}
    not_sent = {
        key: "not_sent_by_protocol/provider_default"
        for key in candidates
        if key not in body
    }
    if provider == "dashscope" and "enable_thinking" in body:
        not_sent["reasoning_effort"] = "not_sent_by_protocol/enable_thinking_false_controls_reasoning"
    if provider == "deepseek" and "thinking" in body:
        not_sent["reasoning_effort"] = "not_sent_by_protocol/thinking_disabled_controls_reasoning"
    return {
        "sent_parameters": sent,
        "not_sent_parameters": not_sent,
    }


def api_request_surface_for_config(provider: str, model: str, max_tokens: int | None) -> dict[str, Any]:
    body = planned_api_request_body(provider, model, max_tokens)
    return {
        "request_body_template_redacted": body,
        **request_parameter_surface(body, provider),
        **provider_cache_policy(provider),
    }


def _redact_route_host(host: str) -> str:
    if host.endswith(".cn-beijing.maas.aliyuncs.com"):
        return "<workspace-id>.cn-beijing.maas.aliyuncs.com"
    if host.endswith(".maas.aliyuncs.com"):
        return "<workspace-id>.maas.aliyuncs.com"
    return host


def route_resolution_metadata(provider: str, url: str, api_key_env: str, model: str) -> dict[str, Any]:
    parsed = urlparse(url)
    base_url_source = "not_applicable"
    if provider == "dashscope":
        for key in ("DASHSCOPE_BASE_URL", "BAILIAN_BASE_URL", "QWEN_BASE_URL"):
            if os.getenv(key):
                base_url_source = key
                break
        else:
            base_url_source = "DEFAULT_DASHSCOPE_BASE_URL"
    region = infer_base_url_region(url)
    return {
        "provider": provider,
        "provider_route": provider,
        "model": model,
        "api_key_env": api_key_env,
        "url_scheme": parsed.scheme,
        "url_host_redacted": _redact_route_host(parsed.netloc),
        "url_host_sha256": sha256_text(parsed.netloc),
        "url_path": parsed.path,
        "base_url_region": region,
        "base_url_source": base_url_source,
        "base_url_env_present": {
            "DASHSCOPE_BASE_URL": bool(os.getenv("DASHSCOPE_BASE_URL")),
            "BAILIAN_BASE_URL": bool(os.getenv("BAILIAN_BASE_URL")),
            "QWEN_BASE_URL": bool(os.getenv("QWEN_BASE_URL")),
        },
        "api_key_env_present": bool(os.getenv(api_key_env)),
        "openrouter_forbidden_for_glm_claim": provider == "dashscope",
        "route_closed_for_glm_claim": provider == "dashscope" and region == "cn-beijing",
        "notes": "Public-lite route artifact redacts workspace host; private raw execution metadata remains local-only.",
    }


def compact_api_request_meta(
    body: dict[str, Any],
    prompt: str,
    provider: str,
    url: str,
    api_key_env: str,
    *,
    stage: str | None = None,
    prompt_path: str | None = None,
    repair_attempt: int | None = None,
    timeout_seconds: float | None = None,
    api_attempts: int | None = None,
) -> dict[str, Any]:
    body_for_log = {k: v for k, v in body.items() if k != "messages"}
    serialized_body = serialized_api_request_body(body)
    body_for_log.update(
        {
            "messages_sha256": sha256_text(json.dumps(body["messages"], ensure_ascii=False)),
            "prompt_sha256": sha256_text(prompt),
            "prompt_prefix_sha256": sha256_text(prompt[:20000]),
            "prompt_chars": len(prompt),
            "provider": provider,
            "provider_route": provider,
            "url_host": urlparse(url).netloc,
            "base_url_region": infer_base_url_region(url),
            "api_key_env": api_key_env,
            "request_body_sha256": sha256_bytes(serialized_body),
            "request_body_serialization": "python_json_dumps_default",
            "timeout_seconds": timeout_seconds,
            "api_attempts_max": api_attempts,
            **provider_cache_policy(provider),
            **request_parameter_surface(body, provider),
        }
    )
    if stage is not None:
        body_for_log["stage"] = stage
    if prompt_path is not None:
        body_for_log["prompt_path"] = prompt_path
    if repair_attempt is not None:
        body_for_log["repair_attempt"] = repair_attempt
    return body_for_log


def redacted_api_request_body(body: dict[str, Any]) -> dict[str, Any]:
    # The request body does not contain secrets. Keep the exact logical payload
    # so future audits can inspect prompt text and sent parameters directly.
    return body


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text_exact_utf8(path: Path) -> str:
    """Read source text without universal-newline or whitespace normalization."""
    return path.read_bytes().decode("utf-8")


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with JSONL_LOCK:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        out[key] = value
    return out


def load_env_file(path: str | None) -> None:
    if not path:
        return
    for key, value in parse_env_file(Path(path)).items():
        os.environ.setdefault(key, value)


def is_binary(path: Path) -> bool:
    try:
        data = path.read_bytes()[:4096]
    except OSError:
        return True
    return b"\0" in data


def include_source_file(path: Path) -> bool:
    parts = set(path.parts)
    if ".git" in parts or "__pycache__" in parts or "node_modules" in parts or "target" in parts:
        return False
    if any(part in {"tests", "test", "solution", "logs", "results", "verifier", "eval"} for part in path.parts):
        return False
    if path.name in FORBIDDEN_PATH_NAMES:
        return False
    if any(part.startswith(".") and part not in {".github"} for part in path.parts):
        return False
    if path.suffix.lower() in {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".pdf",
        ".zip",
        ".gz",
        ".tar",
        ".woff",
        ".ttf",
        ".ico",
        ".lock",
    }:
        return False
    if "CHANGELOG" in path.name.upper() or path.name in {"LICENSE", "LICENSE.txt", "CITATION.cff", "CITATION.bib"}:
        return False
    if is_binary(path):
        return False
    return True


def is_probable_text_edit_path(path: str) -> bool:
    name = Path(path).name
    suffix = Path(path).suffix.lower()
    return suffix in TEXT_EXTS or name in SOURCE_FILENAMES


def is_claim_bearing_source_path(path: str) -> bool:
    name = Path(path).name
    suffix = Path(path).suffix.lower()
    return suffix in SOURCE_EXTS or suffix in CONFIG_EXTS or name in SOURCE_FILENAMES


def file_priority(rel: str) -> tuple[int, int, str]:
    lower = rel.lower()
    if lower.endswith(SOURCE_EXTS) and "/test" not in lower and "test_" not in lower:
        group = 0
    elif lower.endswith(SOURCE_EXTS):
        group = 1
    elif lower.endswith(CONFIG_EXTS):
        group = 2
    elif lower.endswith((".md", ".rst", ".txt")):
        group = 3
    else:
        group = 4
    return (group, len(rel), rel)


def extract_instruction_path_hints(instruction: str, existing_files: set[str]) -> set[str]:
    hints: set[str] = set()
    token_re = re.compile(r"[\w@.+/:-]+\.(?:py|ts|tsx|js|jsx|go|rs|c|cc|cpp|cxx|h|hpp|hh|hxx|java|toml|json|yaml|yml|ini|cfg|cmake|md|rst|txt)")
    for token in token_re.findall(instruction):
        cleaned = token.strip("`'\"()[]{}.,;:")
        if cleaned in existing_files:
            hints.add(cleaned)
    for rel in existing_files:
        if rel in instruction:
            hints.add(rel)
    return hints


def source_roots_from_files(files: list[tuple[str, Path, int]]) -> list[str]:
    roots: set[str] = set()
    for rel, _, _ in files:
        if not is_claim_bearing_source_path(rel):
            continue
        if rel.startswith(FORBIDDEN_PATH_PREFIXES):
            continue
        if rel.startswith(".github/"):
            continue
        parts = rel.split("/")
        if len(parts) > 1:
            roots.add(parts[0] + "/")
        else:
            roots.add("")
    preferred = ["falcon/", "include/", "lib/", "src/", "optuna/", ""]
    ordered = [root for root in preferred if root in roots]
    ordered.extend(sorted(root for root in roots if root not in set(ordered)))
    return ordered[:20]


def editable_source_roots_for_task(task_dir: Path) -> list[str]:
    repo = task_dir / "environment" / "repo"
    files: list[tuple[str, Path, int]] = []
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo).as_posix()
        if not include_source_file(path):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        files.append((rel, path, size))
    return source_roots_from_files(files)


def path_under_editable_source_roots(path: str, roots: list[str]) -> bool:
    return any(("/" not in path) if root == "" else path.startswith(root) for root in roots)


def targeted_context_key(rel: str, instruction: str, hints: set[str]) -> tuple[int, tuple[int, int, str]]:
    score = 0
    lower = rel.lower()
    name = Path(rel).name
    priority_paths = {
        "bs_thread_pool.hpp": 900,
        "include/glaze/core/common.hpp": 880,
        "include/glaze/core/opts.hpp": 860,
        "include/glaze/json/write.hpp": 840,
        "include/glaze/json/schema.hpp": 820,
        "include/glaze/json/read.hpp": 760,
        "include/glaze/json.hpp": 700,
        "include/glaze/glaze.hpp": 680,
    }
    score += priority_paths.get(lower, 0)
    if rel in hints:
        score += 1000
    if name and name in instruction:
        score += 120
    if any(part in lower for part in ("/test", "test_", "/tests/")):
        score -= 250
    if lower.endswith(SOURCE_EXTS):
        score += 50
    if lower.endswith(CONFIG_EXTS):
        score += 10
    return (-score, file_priority(rel))


def build_repo_context(task_dir: Path, max_chars: int, context_mode: str = "full", instruction: str = "") -> dict[str, Any]:
    repo = task_dir / "environment" / "repo"
    files: list[tuple[str, Path, int]] = []
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo).as_posix()
        if not include_source_file(path):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        files.append((rel, path, size))
    existing_files = {rel for rel, _, _ in files}
    path_hints = extract_instruction_path_hints(instruction, existing_files)
    if context_mode == "targeted":
        files.sort(key=lambda item: targeted_context_key(item[0], instruction, path_hints))
    else:
        files.sort(key=lambda item: file_priority(item[0]))
    tree = "\n".join(rel for rel, _, _ in files)
    chunks: list[str] = []
    used = 0
    included: list[str] = []
    full_context_files: list[str] = []
    truncated_files: list[str] = []
    skipped_count = 0
    for rel, path, size in files:
        try:
            text = read_text_exact_utf8(path)
        except (OSError, UnicodeDecodeError):
            skipped_count += 1
            continue
        header = f"\n--- FILE: {rel} ---\n"
        block = header + text
        if not block.endswith("\n"):
            block += "\n"
        per_file_cap = 24000
        if context_mode == "targeted":
            per_file_cap = 80000 if (rel in path_hints or path.suffix.lower() in SOURCE_EXTS or path.name in SOURCE_FILENAMES) else 24000
        truncated = False
        if len(block) > per_file_cap:
            block = header + text[:per_file_cap]
            if not block.endswith("\n"):
                block += "\n"
            block += "...[TRUNCATED]\n"
            truncated = True
        if used + len(block) > max_chars:
            skipped_count += 1
            continue
        chunks.append(block)
        included.append(rel)
        if truncated:
            truncated_files.append(rel)
        else:
            full_context_files.append(rel)
        used += len(block)
    return {
        "tree": tree,
        "source_context": "".join(chunks),
        "included_files": included,
        "full_context_files": full_context_files,
        "truncated_files": truncated_files,
        "strict_edit_existing_files": [rel for rel in full_context_files if is_claim_bearing_source_path(rel)],
        "included_count": len(included),
        "candidate_file_count": len(files),
        "skipped_count": skipped_count,
        "context_chars": used,
        "context_mode": context_mode,
        "path_hints": sorted(path_hints),
        "editable_source_roots": source_roots_from_files(files),
    }


def method_text(method: str, budget: int) -> str:
    body = {
        "loop_only": (
            "Method id: loop_only\n"
            "Solve directly from the roadmap and base repository source. Do not create rolling summaries, visible carry notes, or SSR reasoning fields. "
            "If the output contract requires a final state object, fill it only as a compact scorer-facing action-surface summary."
        ),
        "rolling_summary": (
            "Method id: rolling_summary\n"
            "Maintain a concise rolling summary of model-visible facts and implementation constraints before producing the final patch."
        ),
        "rolling_visible_carry_forward": (
            "Method id: rolling_visible_carry_forward\n"
            "Use visible carry-forward notes with this shape: visible_note=<roadmap facts>; editable_scope=<source files>; goal=<patch goal>; boundary=<what not to edit>."
        ),
        "rolling_visible_fields_only": (
            "Method id: rolling_visible_fields_only\n"
            "Use only visible structured fields OUT=<roadmap facts>, ALW=<editable source files>, NO=<forbidden categories>, G=<patch goal>."
        ),
        "ssr_no_visible_carry": (
            "Method id: ssr_no_visible_carry\n"
            "Use schema-aware source reasoning internally, but do not expose a rolling carry-forward note. "
            "If the output contract requires a final state object, include only that compact final action-surface state with the patch operations."
        ),
        "mature_ssr_loop": (
            "Method id: mature_ssr_loop\n"
            "Use bounded state fields OUT=<source-relevant facts>; ALW=<editable source files>; NO=<forbidden categories>; B=<boundary>; G=<goal>; N=<next concern>; CK=<source-only check>; LOOP=<final guard check>."
        ),
    }[method]
    return "\n".join(
        [
            "# Method Condition",
            f"State budget condition: {budget} tokens. This controls method-state notes, not output max_tokens.",
            body,
        ]
    )


def answer_state_contract(state_contract: str, patch_transport: str = "unified_diff") -> str:
    if state_contract == "none":
        return ""
    state_lines = [
        "# Answer-State Contract",
        "Return exactly two tagged blocks and no prose outside the two blocks:",
        "<STATE_JSON>",
        "{",
        '  "OUT": ["active source facts needed by the repair"],',
        '  "ALW": ["relative/source/file/or/source/root/"],',
        '  "NO": [],',
        '  "B": [],',
        '  "G": "concise repair goal",',
        '  "CK": ["visible source-only checks, including each touched source file"]',
        "}",
        "</STATE_JSON>",
        "",
        "STATE_JSON rules:",
        "- STATE_JSON must be valid JSON and must not contain edit operations or diff hunks.",
        "- OUT or CK must be non-empty.",
        "- ALW must be non-empty and must include every touched source file or a source root covering it, unless CK explicitly names every touched source file.",
        "- NO and B must not list any actively touched source file.",
        "- Do not mention tests, test, solution, verifier, logs, results, eval, task.toml, or any benchmark-private evaluator material anywhere in STATE_JSON.",
        "",
    ]
    if patch_transport == "edit_json":
        state_lines.extend(
            [
                "<EDIT_JSON>",
                "{",
                '  "ops": [',
                '    {"op": "replace", "path": "relative/source/file.py", "old": "exact old text from the current working copy at this op", "new": "replacement text"},',
                '    {"op": "create", "path": "relative/source/new_file.py", "content": "complete new source file content"}',
                "  ]",
                "}",
                "</EDIT_JSON>",
                "",
                "EDIT_JSON rules:",
                "- EDIT_JSON must be valid JSON and must contain a non-empty ops list.",
                "- Supported strict ops are create, replace, and delete.",
                "- path must be a relative allowed source path.",
                '- A leading "./" in path is allowed and will be normalized exactly once; no other path repair is allowed.',
                "- create may only create a non-existing source-like file path, and content must be the complete non-empty new source file content.",
                "- replace may only modify an existing source file; old must match exactly once in the current working copy at the moment that op is applied.",
                "- replace old must be non-empty, must not equal new, and must not be the entire file content.",
                "- delete may only remove an existing source file.",
                "- Do not use whole-file rewrites, fuzzy matching, approximate line matching, line numbers, markdown fences, or prose.",
                "- Multiple ops are applied sequentially to the working copy; any failed op fails the row closed and Docker verification is skipped.",
                "- For multiple ops on the same file, order them top-to-bottom and make each later old anchor match the file after earlier ops have already been applied. Avoid overlapping anchors.",
                "- The runner will apply EDIT_JSON locally and generate the unified diff deterministically.",
            ]
        )
    else:
        state_lines.extend(
            [
                "<PATCH>",
                "diff --git ...",
                "</PATCH>",
                "",
                "PATCH rules:",
                "- PATCH must contain a unified diff beginning with diff --git.",
                "- PATCH must touch only allowed source files.",
                "- PATCH must not contain JSON, STATE_JSON, solution text, or benchmark-private evaluator material.",
            ]
        )
    state_lines.extend(
        [
            "",
            "The runner separately scores state_contract_valid, action_governance_success, answer_success, and reliable_composite_success.",
        ]
    )
    return "\n".join(state_lines)


def output_contract(
    edit_format: str,
    whole_file_max_files: int,
    search_replace_max_edits: int,
    file_op_max_files: int,
    state_contract: str = "none",
    patch_transport: str = "unified_diff",
) -> str:
    if state_contract == "answer_state":
        if patch_transport == "edit_json":
            return "\n".join(
                [
                    "# Tagged Edit Output Contract",
                    "Return exactly one <STATE_JSON> block followed by exactly one <EDIT_JSON> block.",
                    "No markdown fences. No explanation. No text before, between, or after the two blocks except whitespace.",
                    "Do not return a unified diff when --patch-transport edit_json is active.",
                    "Do not return file_ops JSON outside the required <EDIT_JSON> block.",
                    "Use only strict create/replace/delete ops. For replace, use exact non-empty old/new anchors against the current sequential working copy; no whole-file rewrites, no empty old anchors, no fuzzy matching, and no path repair beyond a leading ./ prefix.",
                ]
            )
        return "\n".join(
            [
                "# Tagged Patch Output Contract",
                "Return exactly one <STATE_JSON> block followed by exactly one <PATCH> block.",
                "No markdown fences. No explanation. No text before, between, or after the two blocks except whitespace.",
                "The PATCH block must contain a valid unified diff. Do not return file_ops JSON when this answer_state contract is active.",
            ]
        )
    state_prefix = '"state":{"OUT":["..."],"ALW":["relative/source/file"],"NO":["tests/","solution/"],"G":"...","CK":["..."]},'
    if edit_format == "unified_diff":
        return "\n".join(
            [
                "# Patch Output Contract",
                "Return exactly one unified diff beginning with `diff --git`.",
                "No markdown fences, no explanation, no text before or after the diff.",
            ]
        )
    if edit_format == "whole_file_json":
        return "\n".join(
            [
                "# Edit Output Contract",
                "Return exactly one JSON object and nothing else.",
                f"Rewrite at most {whole_file_max_files} existing repository source files.",
                f'The JSON shape must be {{{state_prefix if state_contract != "none" else ""}"edits":[{{"path":"relative/source/file","content":"full new file content"}}]}}.',
                "Each path must be relative to the repository root and must already exist in the included source context.",
                "The content value must contain the complete new file content, not a diff, not a fragment, and not prose.",
            ]
        )
    if edit_format == "search_replace_json":
        return "\n".join(
            [
                "# Edit Output Contract",
                "Return exactly one JSON object and nothing else.",
                f"Return at most {search_replace_max_edits} exact search/replace edits.",
                f'The JSON shape must be {{{state_prefix if state_contract != "none" else ""}"replacements":[{{"path":"relative/source/file","old":"exact old text","new":"exact new text"}}]}}.',
                "Each path must be relative to the repository root and must already exist in the included source context.",
                "Each old value must be an exact contiguous substring of the current file content.",
                "Do not use line numbers, unified diff hunks, markdown fences, or prose.",
            ]
        )
    if edit_format == "file_ops_json":
        return "\n".join(
            [
                "# Edit Output Contract",
                "Return exactly one JSON object and nothing else.",
                f"Return at most {file_op_max_files} source file operations.",
                f'The JSON shape must be {{{state_prefix if state_contract != "none" else ""}"ops":[{{"op":"write","path":"relative/source/file","content":"full new file content"}}]}}.',
                "Allowed ops: write, delete, append, replace, insert_before, insert_after.",
                "Use op=write to create a new source file or rewrite a small existing source file.",
                "Use op=delete only for existing source files that should be removed.",
                "Use op=append with content to append to an existing source file.",
                "Use op=replace with old and new when old is an exact unique substring of an existing source file.",
                "Use op=insert_before or op=insert_after with anchor and content when anchor is an exact unique substring of an existing source file.",
                "For write operations, content must be the complete new file content, not a diff, not a fragment, and not prose.",
                "Do not use line numbers, unified diff hunks, markdown fences, or explanation.",
            ]
        )
    raise ValueError(f"unknown edit format: {edit_format}")


def flatten_state_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(flatten_state_strings(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(flatten_state_strings(item))
        return out
    return []


def has_nonempty_state_value(value: Any) -> bool:
    return any(text.strip() for text in flatten_state_strings(value))


def state_conflict_hits(strings: list[str]) -> list[str]:
    hits: list[str] = []
    for text in strings:
        lower = text.lower()
        for token in STATE_CONFLICT_TOKENS:
            if token in lower and token not in hits:
                hits.append(token)
    return hits


def leakage_hits(text: str) -> list[str]:
    lower = text.lower()
    return [term for term in LEAKAGE_TERMS if term in lower]


def normalize_state_paths(value: Any) -> list[str]:
    paths: list[str] = []
    for text in flatten_state_strings(value):
        item = text.strip().strip("`'\"")
        if item:
            paths.append(item)
    return paths


def is_safe_state_alw_entry(path: str) -> bool:
    if path.endswith("/"):
        return is_safe_repo_path(path + "__placeholder__.txt")
    return is_safe_repo_path(path) and is_probable_text_edit_path(path)


def alw_entry_covers_path(entry: str, path: str) -> bool:
    if entry == path:
        return True
    return entry.endswith("/") and path.startswith(entry)


def state_entry_mentions_path(entry: str, path: str) -> bool:
    entry = entry.strip()
    if not entry:
        return False
    return path in entry or (entry.endswith("/") and path.startswith(entry))


def score_state_governance(
    payload: dict[str, Any] | None,
    state_contract: str,
    candidate_files: list[str],
    raw_text: str = "",
    patch_text: str = "",
    transport_valid: bool = False,
    patch_applies: bool = False,
) -> dict[str, Any]:
    if state_contract == "none":
        return {"state_contract": "none"}
    reasons: list[str] = []
    state = payload.get("state") if isinstance(payload, dict) else None
    if not isinstance(state, dict):
        return {
            "state_contract": state_contract,
            "state_parse_success": False,
            "state_contract_valid": False,
            "action_governance_success": False,
            "state_governance_success": False,
            "state_failure_reasons": ["state_missing_or_not_object"],
            "state_output_bearing_present": False,
            "state_paths_cover_patch": False,
            "state_forbidden_output_hits": [],
            "state_forbidden_state_hits": [],
            "state_raw_or_patch_leakage_hits": [],
            "state_allowed_paths": [],
            "state_json_valid": False,
        }

    out_texts = flatten_state_strings(state.get("OUT"))
    ck_texts = flatten_state_strings(state.get("CK"))
    output_texts = out_texts + ck_texts + flatten_state_strings(state.get("G")) + flatten_state_strings(state.get("ALW"))
    output_present = any(text.strip() for text in out_texts + ck_texts)
    if not output_present:
        reasons.append("OUT_or_CK_empty")

    hits = state_conflict_hits(output_texts)
    if hits:
        reasons.append("forbidden_token_in_output_bearing_state")

    state_json_text = json.dumps(state, ensure_ascii=False, sort_keys=True)
    full_state_hits = sorted(set(state_conflict_hits(flatten_state_strings(state)) + [f"leak:{hit}" for hit in leakage_hits(state_json_text)]))
    if full_state_hits:
        reasons.append("forbidden_or_leakage_token_in_state")

    raw_or_patch_hits = sorted(set([f"raw:{hit}" for hit in leakage_hits(raw_text)] + [f"patch:{hit}" for hit in leakage_hits(patch_text)]))
    if raw_or_patch_hits:
        reasons.append("raw_or_patch_leakage")

    allowed_paths = normalize_state_paths(state.get("ALW"))
    if not allowed_paths:
        reasons.append("ALW_empty")
    bad_allowed = [path for path in allowed_paths if not is_safe_state_alw_entry(path)]
    if bad_allowed:
        reasons.append("invalid_alw_path")

    unique_candidate_files = sorted({path for path in candidate_files if path})
    ck_values = normalize_state_paths(state.get("CK"))
    uncovered = [
        path
        for path in unique_candidate_files
        if not any(alw_entry_covers_path(entry, path) for entry in allowed_paths)
        and not any(path in ck for ck in ck_values)
    ]
    paths_cover_patch = bool(unique_candidate_files) and not uncovered
    if not unique_candidate_files:
        reasons.append("no_valid_patch_action_surface")
    elif uncovered:
        reasons.append("alw_or_ck_does_not_cover_patch_files")

    no_boundary_entries = normalize_state_paths(state.get("NO")) + normalize_state_paths(state.get("B"))
    patched_files_in_no_or_b = [
        path
        for path in unique_candidate_files
        if any(state_entry_mentions_path(entry, path) for entry in no_boundary_entries)
    ]
    if patched_files_in_no_or_b:
        reasons.append("patched_file_listed_in_NO_or_B")

    state_contract_valid = (
        output_present
        and not hits
        and not full_state_hits
        and not raw_or_patch_hits
        and not bad_allowed
        and bool(allowed_paths)
    )
    action_governance_success = (
        state_contract_valid
        and transport_valid
        and patch_applies
        and paths_cover_patch
        and not patched_files_in_no_or_b
    )
    return {
        "state_contract": state_contract,
        "state_parse_success": True,
        "state_json_valid": True,
        "state_contract_valid": state_contract_valid,
        "action_governance_success": action_governance_success,
        "state_governance_success": action_governance_success,
        "state_failure_reasons": sorted(set(reasons)),
        "state_output_bearing_present": output_present,
        "state_paths_cover_patch": paths_cover_patch,
        "state_forbidden_output_hits": hits,
        "state_forbidden_state_hits": full_state_hits,
        "state_raw_or_patch_leakage_hits": raw_or_patch_hits,
        "state_allowed_paths": allowed_paths,
        "state_uncovered_patch_files": uncovered,
        "state_invalid_alw_paths": bad_allowed,
        "state_patched_files_in_no_or_b": patched_files_in_no_or_b,
    }


def add_answer_state_outcomes(row: dict[str, Any], state_source: dict[str, Any] | None = None) -> dict[str, Any]:
    out = dict(row)
    answer_success = bool(out.get("test_passed"))
    out["answer_success"] = answer_success
    source = state_source or out
    if source.get("state_contract") == "answer_state" or "action_governance_success" in source or "state_governance_success" in source:
        action_success = bool(source.get("action_governance_success", source.get("state_governance_success")))
        out["action_governance_success"] = action_success
        out["state_governance_success"] = action_success
        if "state_contract_valid" in source:
            out["state_contract_valid"] = bool(source.get("state_contract_valid"))
        out["reliable_composite_success"] = answer_success and action_success
    return out


def editable_path_rules(context: dict[str, Any]) -> str:
    roots = context.get("editable_source_roots") or []
    root_text = ", ".join(root or "<repo root>" for root in roots) if roots else "existing source directories"
    return "\n".join(
        [
            "# Editable Path Rules",
            f"- You may modify existing source files listed in the repository file tree.",
            f"- You may create new source files only under these source roots when required: {root_text}.",
            "- Do not edit or create files under tests/, test/, solution/, logs/, results/, verifier/, eval/, .git/, or __pycache__.",
            "- Do not edit task.toml or benchmark metadata.",
            "- Paths must be relative to the repository root.",
        ]
    )


def strict_edit_json_path_scope(context: dict[str, Any], patch_transport: str) -> str:
    if patch_transport != "edit_json":
        return ""
    existing = context.get("strict_edit_existing_files") or []
    roots = context.get("editable_source_roots") or []
    root_text = ", ".join(root or "<repo root>" for root in roots) if roots else "existing source directories"
    lines = [
        "# Strict EDIT_JSON Path Scope",
        "- replace and delete may target only existing files whose complete source text is included below.",
        "- Do not use replace anchors from truncated files, skipped files, the repository file tree, line numbers, or memory.",
        "- Never include the literal marker ...[TRUNCATED] inside old, new, or content.",
        f"- create may add a new source-like file only under these source roots when required: {root_text}.",
        "- Full-context existing files allowed for replace/delete:",
    ]
    if existing:
        lines.extend(f"  - {path}" for path in existing)
    else:
        lines.append("  - <none>")
    return "\n".join(lines)


def roadmap_coverage_rules(edit_format: str) -> str:
    lines = [
        "# Roadmap Coverage Gate",
        "- The roadmap contains multiple Targets. Produce one coherent repair that covers every Target needed for completion, not only Target 1.",
        "- Wire new public APIs into existing import/export and runtime paths; creating helper files alone is not enough.",
        "- When an existing file is large, prefer a small anchored edit instead of rewriting the full file.",
    ]
    if edit_format in {"file_ops_json", "edit_json"}:
        lines.append("- For large existing files, prefer small exact anchored edits. If you use multiple edits on one file, avoid overlapping anchors and order them so each later anchor exists after earlier edits.")
    return "\n".join(lines)


def task_specific_guidance(task_id: str) -> str:
    if task_id.startswith("tpl-"):
        return "\n".join(
            [
                "# Task-Specific Implementation Guidance",
                "- For member function task submission, use std::invoke and std::invoke_result_t so member function pointers with object pointers work correctly.",
                "- Include <functional> if std::invoke is used.",
                "- Keep the blocks, push_loop, zero-start parallelize_loop, stream manipulator, and multi_future<void> changes in the same patch.",
            ]
        )
    if task_id.startswith("fal-"):
        return "\n".join(
            [
                "# Task-Specific Implementation Guidance",
                "- Cover all five roadmap targets: media framework, URI converters, Forwarded proxy attributes, request/header helpers, and 5xx error classes.",
                "- Creating media modules alone is insufficient; wire new APIs into request.py, response.py, api/options, routing exports, error exports, and top-level falcon exports.",
                "- Use anchored edits for large existing files instead of rewriting them.",
            ]
        )
    if task_id.startswith("glz-"):
        return "\n".join(
            [
                "# Task-Specific Implementation Guidance",
                "- Creating refl.hpp alone is insufficient; wire it into the existing core headers and update opts/read/write key handling as required by the roadmap.",
                "- For escaped unicode key conversion, add the option to the existing opts struct and make read-side key matching respect it.",
                "- Prefer small anchored edits to the existing headers rather than broad rewrites.",
            ]
        )
    return ""


def render_prompt(
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
) -> tuple[str, dict[str, Any]]:
    instruction = (task_dir / "instruction.md").read_text(encoding="utf-8", errors="replace")
    context = build_repo_context(task_dir, max_chars=max_context_chars, context_mode=context_mode, instruction=instruction)
    prompt = "\n\n".join(
        [
            "# RoadmapBench Source Repair Task",
            f"Task id: {task_dir.name}",
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
            editable_path_rules(context),
            strict_edit_json_path_scope(context, patch_transport),
            roadmap_coverage_rules(patch_transport if state_contract == "answer_state" else edit_format),
            task_specific_guidance(task_dir.name),
            method_text(method, budget),
            answer_state_contract(state_contract, patch_transport),
            output_contract(edit_format, whole_file_max_files, search_replace_max_edits, file_op_max_files, state_contract, patch_transport),
        ]
    )
    meta = {k: v for k, v in context.items() if k != "source_context"}
    meta["edit_format"] = edit_format
    meta["whole_file_max_files"] = whole_file_max_files
    meta["search_replace_max_edits"] = search_replace_max_edits
    meta["file_op_max_files"] = file_op_max_files
    meta["state_contract"] = state_contract
    meta["patch_transport"] = patch_transport
    meta["prompt_chars"] = len(prompt)
    meta["prompt_sha256"] = sha256_text(prompt)
    return prompt, meta


def resolve_provider(provider_arg: str, model_arg: str) -> tuple[str, str, str, str]:
    if provider_arg == "deepseek":
        return "deepseek", "https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY", model_arg
    if provider_arg == "openrouter":
        model = DEFAULT_OPENROUTER_MODEL if model_arg == DEFAULT_MODEL else model_arg
        return "openrouter", "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", model
    if provider_arg == "dashscope":
        base_url = (
            os.getenv("DASHSCOPE_BASE_URL")
            or os.getenv("BAILIAN_BASE_URL")
            or os.getenv("QWEN_BASE_URL")
            or DEFAULT_DASHSCOPE_BASE_URL
        )
        base_url = base_url.rstrip("/")
        url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
        return "dashscope", url, "DASHSCOPE_API_KEY", model_arg
    if os.getenv("DEEPSEEK_API_KEY"):
        return "deepseek", "https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY", model_arg
    if os.getenv("OPENROUTER_API_KEY"):
        model = DEFAULT_OPENROUTER_MODEL if model_arg == DEFAULT_MODEL else model_arg
        return "openrouter", "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", model
    return "deepseek", "https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY", model_arg


def call_model(prompt: str, provider: str, url: str, api_key_env: str, model: str, max_tokens: int | None, timeout: float, attempts: int) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise RuntimeError(f"{api_key_env} is not set")
    body = planned_api_request_body(provider, model, max_tokens)
    body["messages"] = [{"role": "user", "content": prompt}]
    data = serialized_api_request_body(body)
    retry_events: list[dict[str, Any]] = []
    overall_started = time.time()
    overall_started_utc = utc_now()
    deadline = overall_started + timeout if timeout else None

    def no_response_timeout_meta(attempt: int, last_error: BaseException | None = None) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "provider": provider,
            "url": url,
            "url_host": urlparse(url).netloc,
            "base_url_region": infer_base_url_region(url),
            "api_key_env": api_key_env,
            "status": None,
            "headers": {},
            "request_started_utc": overall_started_utc,
            "request_completed_utc": utc_now(),
            "elapsed_seconds": round(time.time() - overall_started, 3),
            "attempt": attempt,
            "api_attempts_max": attempts,
            "retry_count": max(0, attempt - 1),
            "retry_events": retry_events,
            "timeout_seconds": timeout,
            "total_timeout_seconds": timeout,
            "request_body_sha256": sha256_bytes(data),
            "request_id": None,
            "response_id": None,
            "resolved_model": model,
            "failure_step": "api_no_response_timeout",
            "failure_reason": "provider call did not produce a response within timeout_seconds",
            **provider_cache_policy(provider),
        }
        if last_error is not None:
            meta["last_error_type"] = type(last_error).__name__
            meta["last_error"] = str(last_error)
        return meta

    for attempt in range(1, attempts + 1):
        started = time.time()
        request_started_utc = utc_now()
        request_timeout = timeout
        if deadline is not None:
            remaining = deadline - time.time()
            if remaining <= 0:
                meta = no_response_timeout_meta(attempt)
                raise APINoResponseTimeout(meta["failure_reason"], body=body, meta=meta)
            request_timeout = max(1.0, min(timeout, remaining))
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if provider == "openrouter":
            headers.update({"HTTP-Referer": "https://localhost/roadmapbench-deepseek", "X-Title": "roadmapbench-deepseek-6method"})
        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=request_timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                response_headers = dict(resp.headers)
                return body, {
                    "payload": payload,
                    "meta": {
                        "provider": provider,
                        "url": url,
                        "url_host": urlparse(url).netloc,
                        "base_url_region": infer_base_url_region(url),
                        "api_key_env": api_key_env,
                        "status": resp.status,
                        "headers": response_headers,
                        "request_started_utc": request_started_utc,
                        "request_completed_utc": utc_now(),
                        "elapsed_seconds": round(time.time() - started, 3),
                        "attempt": attempt,
                        "api_attempts_max": attempts,
                        "retry_count": attempt - 1,
                        "retry_events": retry_events,
                        "timeout_seconds": timeout,
                        "request_timeout_seconds": request_timeout,
                        "total_timeout_seconds": timeout,
                        "request_body_sha256": sha256_bytes(data),
                        "request_id": response_headers.get("x-request-id") or response_headers.get("X-Request-Id") or payload.get("id"),
                        "response_id": payload.get("id"),
                        "resolved_model": payload.get("model") or model,
                        **provider_cache_policy(provider),
                    },
                }
        except Exception as exc:  # noqa: BLE001
            retryable = isinstance(
                exc,
                (
                    urllib.error.URLError,
                    urllib.error.HTTPError,
                    http.client.RemoteDisconnected,
                    http.client.IncompleteRead,
                    ConnectionResetError,
                    TimeoutError,
                    ssl.SSLError,
                ),
            )
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in {408, 409, 425, 429, 500, 502, 503, 504}:
                retryable = False
            if deadline is not None and time.time() >= deadline:
                meta = no_response_timeout_meta(attempt, exc)
                raise APINoResponseTimeout(meta["failure_reason"], body=body, meta=meta) from exc
            if attempt >= attempts or not retryable:
                raise
            sleep_seconds = min(30, 2**attempt)
            retry_events.append({"attempt": attempt, "timestamp_utc": utc_now(), "error_type": type(exc).__name__, "sleep_seconds": sleep_seconds})
            if deadline is not None and time.time() + sleep_seconds >= deadline:
                meta = no_response_timeout_meta(attempt, exc)
                raise APINoResponseTimeout(meta["failure_reason"], body=body, meta=meta) from exc
            time.sleep(sleep_seconds)
    raise RuntimeError("unreachable retry loop")


def response_diagnostics(payload: dict[str, Any]) -> dict[str, Any]:
    choice = payload.get("choices", [{}])[0] if isinstance(payload.get("choices"), list) and payload.get("choices") else {}
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    return {
        "finish_reason": choice.get("finish_reason"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }


def extract_patch(raw: str) -> tuple[str | None, dict[str, Any]]:
    raw_norm = raw.replace("\r\n", "\n").replace("\r", "\n")
    fenced = [m.group(1).strip() for m in FENCE_RE.finditer(raw_norm) if "diff --git " in m.group(1)]
    diag: dict[str, Any] = {
        "raw_response_sha256": sha256_text(raw),
        "fenced_diff_blocks": len(fenced),
        "ok": False,
        "strategy": None,
        "failure_reason": None,
    }
    if len(fenced) > 1:
        diag["failure_reason"] = "ambiguous_multiple_diff_blocks"
        return None, diag
    if fenced:
        patch = fenced[0].strip() + "\n"
        diag["strategy"] = "single_fenced_diff_block"
    else:
        idx = raw_norm.find("diff --git ")
        if idx < 0:
            diag["failure_reason"] = "no_unified_diff_found"
            return None, diag
        patch = raw_norm[idx:].strip() + "\n"
        diag["strategy"] = "plain_unified_diff_from_first_header"
    diag["ok"] = True
    diag["patch_sha256"] = sha256_text(patch)
    diag["patch_bytes"] = len(patch.encode("utf-8"))
    return patch, diag


def patch_files(patch: str) -> list[str]:
    files: list[str] = []
    seen: set[str] = set()
    for line in patch.splitlines():
        if not line.startswith("diff --git "):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        path = parts[3][2:] if parts[3].startswith("b/") else parts[3]
        if path not in seen:
            seen.add(path)
            files.append(path)
    return files


def is_safe_repo_path(path: str) -> bool:
    lower = path.lower()
    return (
        bool(path)
        and not path.startswith("/")
        and ".." not in path.split("/")
        and not lower.startswith(FORBIDDEN_PATH_PREFIXES)
        and Path(path).name not in FORBIDDEN_PATH_NAMES
    )


def normalize_edit_json_path(path: str) -> tuple[str, bool]:
    if path.startswith("./"):
        return path[2:], True
    return path, False


def is_strict_edit_json_path(path: str) -> bool:
    parts = path.split("/")
    return (
        is_safe_repo_path(path)
        and "\\" not in path
        and "" not in parts
        and "." not in parts
        and not path.startswith("./")
    )


def file_mode_line(path: Path) -> str:
    try:
        mode = path.stat().st_mode
    except OSError:
        return "100644"
    return "100755" if mode & 0o111 else "100644"


def validate_patch(patch: str) -> dict[str, Any]:
    files = patch_files(patch)
    bad = []
    for path in files:
        if not is_safe_repo_path(path):
            bad.append({"path": path, "reason": "benchmark_or_verifier_path"})
    return {"ok": bool(files) and not bad, "files": files, "bad_files": bad}


def extract_json_payload(raw: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    raw_norm = raw.replace("\r\n", "\n").replace("\r", "\n")
    candidates = [m.group(1).strip() for m in JSON_FENCE_RE.finditer(raw_norm)]
    if not candidates:
        start = raw_norm.find("{")
        end = raw_norm.rfind("}")
        if start >= 0 and end > start:
            candidates = [raw_norm[start : end + 1].strip()]
    diag: dict[str, Any] = {
        "raw_response_sha256": sha256_text(raw),
        "json_candidates": len(candidates),
        "ok": False,
        "failure_reason": None,
    }
    if len(candidates) != 1:
        diag["failure_reason"] = "expected_single_json_object"
        return None, diag
    try:
        payload = json.loads(candidates[0])
    except json.JSONDecodeError as exc:
        diag["failure_reason"] = f"json_decode_failed: {exc}"
        return None, diag
    if not isinstance(payload, dict):
        diag["failure_reason"] = "json_payload_not_object"
        return None, diag
    diag["ok"] = True
    diag["json_sha256"] = sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return payload, diag


def extract_tagged_state_block(raw_norm: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    state_blocks = [m.group(1).strip() for m in STATE_JSON_BLOCK_RE.finditer(raw_norm)]
    diag: dict[str, Any] = {"state_blocks": len(state_blocks), "state_json_valid": False}
    if len(state_blocks) != 1:
        diag["failure_reason"] = "state_json_missing"
        diag["detail"] = f"expected_one_state_json_block_got_{len(state_blocks)}"
        return None, diag
    state_text = state_blocks[0]
    if "diff --git " in state_text or re.search(r"^@@", state_text, re.MULTILINE):
        diag["failure_reason"] = "state_json_invalid"
        diag["detail"] = "state_json_contains_diff_hunk"
        return None, diag
    try:
        state_obj = json.loads(state_text)
    except json.JSONDecodeError as exc:
        diag["failure_reason"] = "state_json_invalid"
        diag["detail"] = str(exc)
        return None, diag
    if not isinstance(state_obj, dict):
        diag["failure_reason"] = "state_json_invalid"
        diag["detail"] = "state_json_not_object"
        return None, diag
    diag["state_json_valid"] = True
    diag["state_json_sha256"] = sha256_text(json.dumps(state_obj, ensure_ascii=False, sort_keys=True))
    return state_obj, diag


def validate_and_apply_edit_json(
    task_dir: Path,
    edit_obj: Any,
    allowed_existing_paths: set[str] | None = None,
) -> tuple[str | None, dict[str, Any]]:
    repo = task_dir / "environment" / "repo"
    diag: dict[str, Any] = {
        "edit_json_valid": False,
        "deterministic_edit_apply_success": False,
        "deterministic_patch_generated": False,
        "files": [],
        "created_files": [],
        "deleted_files": [],
        "modified_files": [],
        "failure_reason": None,
        "line_ending_normalization": False,
        "whitespace_normalization": False,
        "source_text_matching": "exact_utf8_bytes_decode_no_newline_translation",
        "op_statuses": [],
    }

    def fail_op(idx: int, status: dict[str, Any], failure_reason: str, detail: str | None = None) -> tuple[None, dict[str, Any]]:
        status["status"] = "failed"
        status["failure_reason"] = failure_reason
        if detail is not None:
            status["detail"] = detail
        diag["op_statuses"].append(status)
        any_prior_applied = any(item.get("status") == "applied" for item in diag["op_statuses"])
        if failure_reason == "edit_json_invalid":
            diag["edit_json_valid"] = False
        diag["failure_reason"] = "edit_apply_failed" if any_prior_applied else failure_reason
        if any_prior_applied:
            diag["underlying_failure_reason"] = failure_reason
        diag["detail"] = detail if detail is not None else f"op_{idx}_failed"
        return None, diag

    def line_ending_kind(text: str) -> str:
        if "\r\n" in text:
            return "CRLF"
        if "\r" in text:
            return "CR"
        return "LF_or_none"

    if not isinstance(edit_obj, dict):
        diag["failure_reason"] = "edit_json_invalid"
        diag["detail"] = "edit_json_not_object"
        return None, diag
    ops = edit_obj.get("ops")
    if not isinstance(ops, list):
        diag["failure_reason"] = "edit_json_invalid"
        diag["detail"] = "ops_not_list"
        return None, diag
    if not ops:
        diag["failure_reason"] = "edit_ops_empty"
        return None, diag
    diag["edit_json_valid"] = True

    contents: dict[str, str | None] = {}
    original: dict[str, str | None] = {}
    original_line_endings: dict[str, str] = {}
    touched: list[str] = []
    editable_roots = editable_source_roots_for_task(task_dir)

    def ensure_loaded(rel: str) -> tuple[bool, str | None, str | None]:
        if rel in contents:
            return True, contents[rel], None
        src = repo / rel
        if not src.exists():
            original[rel] = None
            contents[rel] = None
            return True, None, None
        if not src.is_file() or is_binary(src):
            return False, None, "binary_or_non_file_source"
        try:
            text = read_text_exact_utf8(src)
        except UnicodeDecodeError as exc:
            return False, None, f"non_utf8_source:{exc}"
        original[rel] = text
        contents[rel] = text
        original_line_endings[rel] = line_ending_kind(text)
        return True, text, None

    for idx, op_obj in enumerate(ops):
        status: dict[str, Any] = {"index": idx, "status": "pending"}
        if not isinstance(op_obj, dict):
            return fail_op(idx, status, "edit_json_invalid", f"op_{idx}_not_object")
        status["op"] = op_obj.get("op")
        if op_obj.get("op") not in {"create", "replace", "delete"}:
            return fail_op(idx, status, "edit_json_invalid", f"unsupported_op:{op_obj.get('op')}")
        path = op_obj.get("path")
        status["input_path"] = path
        if not isinstance(path, str):
            return fail_op(idx, status, "edit_json_invalid", f"op_{idx}_path_invalid")
        path, normalized_leading_dot_slash = normalize_edit_json_path(path)
        status["path"] = path
        status["path_normalized_leading_dot_slash"] = normalized_leading_dot_slash
        if not is_strict_edit_json_path(path) or not is_claim_bearing_source_path(path):
            return fail_op(idx, status, "edit_path_disallowed", path)

        loaded, current, load_error = ensure_loaded(path)
        if not loaded:
            return fail_op(idx, status, "edit_path_disallowed", f"{path}:{load_error}")

        op = op_obj.get("op")
        if op == "create":
            content = op_obj.get("content")
            if not isinstance(content, str):
                return fail_op(idx, status, "edit_json_invalid", f"op_{idx}_content_invalid")
            status["content_sha256"] = sha256_text(content)
            status["content_bytes"] = len(content.encode("utf-8"))
            if not content:
                return fail_op(idx, status, "edit_json_invalid", "create_content_empty")
            if current is not None:
                return fail_op(idx, status, "edit_path_disallowed", "create_target_already_exists")
            if not path_under_editable_source_roots(path, editable_roots):
                return fail_op(idx, status, "edit_path_disallowed", "create_path_not_under_editable_source_roots")
            contents[path] = content
        elif op == "delete":
            if allowed_existing_paths is not None and path not in allowed_existing_paths:
                return fail_op(idx, status, "edit_path_disallowed", "delete_path_not_in_full_context")
            if current is None:
                return fail_op(idx, status, "edit_path_disallowed", "delete_target_missing")
            contents[path] = None
        else:
            if allowed_existing_paths is not None and path not in allowed_existing_paths:
                return fail_op(idx, status, "edit_path_disallowed", "replace_path_not_in_full_context")
            old = op_obj.get("old")
            new = op_obj.get("new")
            if not isinstance(old, str) or not isinstance(new, str):
                return fail_op(idx, status, "edit_json_invalid", f"op_{idx}_old_new_invalid")
            status["old_sha256"] = sha256_text(old)
            status["new_sha256"] = sha256_text(new)
            status["old_bytes"] = len(old.encode("utf-8"))
            status["new_bytes"] = len(new.encode("utf-8"))
            if current is None:
                return fail_op(idx, status, "edit_path_disallowed", "replace_target_missing")
            if not old:
                return fail_op(idx, status, "edit_json_invalid", "old_text_empty")
            if old == new:
                return fail_op(idx, status, "deterministic_patch_generation_failed", "op_no_actual_source_change")
            if old == current:
                return fail_op(idx, status, "edit_json_invalid", "whole_file_rewrite_not_allowed")
            count = current.count(old)
            status["old_occurrence_count"] = count
            if count == 0:
                return fail_op(idx, status, "edit_anchor_not_found", "old_text_occurrence_count:0")
            if count > 1:
                return fail_op(idx, status, "edit_anchor_ambiguous", f"old_text_occurrence_count:{count}")
            contents[path] = current.replace(old, new, 1)
        status["status"] = "applied"
        status["working_copy_order"] = len(diag["op_statuses"])
        diag["op_statuses"].append(status)
        touched.append(path)

    diag["touched_files_in_order"] = touched
    diag["original_line_endings"] = original_line_endings
    patch_parts: list[str] = []
    changed_files: list[str] = []
    created_files: list[str] = []
    deleted_files: list[str] = []
    modified_files: list[str] = []
    for rel in sorted(contents):
        old_text = original.get(rel)
        new_text = contents[rel]
        if old_text == new_text:
            continue
        src = repo / rel
        if old_text is None:
            diff_lines = list(
                difflib.unified_diff(
                    [],
                    (new_text or "").splitlines(keepends=True),
                    fromfile="/dev/null",
                    tofile=f"b/{rel}",
                    n=3,
                )
            )
            if not diff_lines:
                continue
            part = f"diff --git a/{rel} b/{rel}\n"
            part += "new file mode 100644\n"
            part += "".join(diff_lines)
            created_files.append(rel)
        elif new_text is None:
            diff_lines = list(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    [],
                    fromfile=f"a/{rel}",
                    tofile="/dev/null",
                    n=3,
                )
            )
            if not diff_lines:
                continue
            part = f"diff --git a/{rel} b/{rel}\n"
            part += f"deleted file mode {file_mode_line(src)}\n"
            part += "".join(diff_lines)
            deleted_files.append(rel)
        else:
            diff_lines = list(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=f"a/{rel}",
                    tofile=f"b/{rel}",
                    n=3,
                )
            )
            if not diff_lines:
                continue
            part = f"diff --git a/{rel} b/{rel}\n" + "".join(diff_lines)
            modified_files.append(rel)
        if part and not part.endswith("\n"):
            part += "\n"
        patch_parts.append(part)
        changed_files.append(rel)
    patch = "".join(patch_parts) if patch_parts else None
    patch_diag = {
        "ok": bool(patch_parts),
        "files": changed_files,
        "created_files": created_files,
        "deleted_files": deleted_files,
        "modified_files": modified_files,
        "failure_reason": None if patch_parts else "no_file_content_changes",
    }
    if patch is not None:
        patch_diag["patch_sha256"] = sha256_text(patch)
        patch_diag["patch_bytes"] = len(patch.encode("utf-8"))
    diag["patch_generation"] = patch_diag
    if patch is None:
        diag["failure_reason"] = "deterministic_patch_generation_failed"
        diag["detail"] = patch_diag.get("failure_reason")
        if patch_diag.get("failure_reason") == "no_file_content_changes":
            diag["no_actual_source_change"] = True
        return None, diag
    validation = validate_patch(patch)
    diag["candidate_patch_validator"] = validation
    if not validation["ok"]:
        diag["failure_reason"] = "edit_path_disallowed"
        diag["detail"] = validation.get("bad_files")
        return None, diag
    diag["deterministic_edit_apply_success"] = True
    diag["deterministic_patch_generated"] = True
    diag["files"] = validation["files"]
    diag["created_files"] = created_files
    diag["deleted_files"] = deleted_files
    diag["modified_files"] = modified_files
    diag["patch_sha256"] = sha256_text(patch)
    diag["patch_bytes"] = len(patch.encode("utf-8"))
    diag["failure_reason"] = None
    return patch, diag


def extract_tagged_answer_state(
    raw: str,
    task_dir: Path,
    patch_transport: str,
    allowed_existing_paths: set[str] | None = None,
) -> tuple[str | None, dict[str, Any], dict[str, Any] | None]:
    raw_norm = raw
    state_obj, state_diag = extract_tagged_state_block(raw_norm)
    if patch_transport == "edit_json":
        edit_blocks = [m.group(1).strip() for m in EDIT_JSON_BLOCK_RE.finditer(raw_norm)]
        diag: dict[str, Any] = {
            "raw_response_sha256": sha256_text(raw),
            "edit_format": "answer_state_two_block",
            "patch_transport": patch_transport,
            "line_ending_normalization": False,
            "whitespace_normalization": False,
            **state_diag,
            "edit_json_blocks": len(edit_blocks),
            "ok": False,
            "failure_reason": None,
        }
        outside = STATE_JSON_BLOCK_RE.sub("", raw_norm)
        outside = EDIT_JSON_BLOCK_RE.sub("", outside).strip()
        if outside:
            diag["failure_reason"] = "edit_json_invalid"
            diag["detail"] = "prose_or_extra_text_outside_required_blocks"
            return None, diag, {"state": state_obj} if state_obj is not None else None
        if state_obj is None:
            diag["failure_reason"] = state_diag.get("failure_reason") or "state_json_invalid"
            return None, diag, None
        if len(edit_blocks) != 1:
            diag["failure_reason"] = "edit_json_missing"
            diag["detail"] = f"expected_one_edit_json_block_got_{len(edit_blocks)}"
            return None, diag, {"state": state_obj}
        edit_text = edit_blocks[0]
        if "diff --git " in edit_text or re.search(r"^@@", edit_text, re.MULTILINE):
            diag["failure_reason"] = "edit_json_invalid"
            diag["detail"] = "edit_json_contains_diff_hunk"
            return None, diag, {"state": state_obj}
        try:
            edit_obj = json.loads(edit_text)
        except json.JSONDecodeError as exc:
            diag["failure_reason"] = "edit_json_invalid"
            diag["detail"] = str(exc)
            return None, diag, {"state": state_obj}
        patch, edit_diag = validate_and_apply_edit_json(task_dir, edit_obj, allowed_existing_paths=allowed_existing_paths)
        diag["edit_validation"] = edit_diag
        diag["edit_json_valid"] = edit_diag.get("edit_json_valid", False)
        diag["deterministic_edit_apply_success"] = edit_diag.get("deterministic_edit_apply_success", False)
        diag["deterministic_patch_generated"] = edit_diag.get("deterministic_patch_generated", False)
        diag["files"] = edit_diag.get("files", [])
        if patch is None:
            diag["failure_reason"] = edit_diag.get("failure_reason") or "deterministic_patch_generation_failed"
            return None, diag, {"state": state_obj, "edit": edit_obj}
        diag["ok"] = True
        diag["failure_reason"] = None
        diag["patch_sha256"] = edit_diag.get("patch_sha256")
        diag["patch_bytes"] = edit_diag.get("patch_bytes")
        return patch, diag, {"state": state_obj, "edit": edit_obj}

    patch_blocks = [m.group(1).strip() for m in PATCH_BLOCK_RE.finditer(raw_norm)]
    diag: dict[str, Any] = {
        "raw_response_sha256": sha256_text(raw),
        "edit_format": "answer_state_two_block",
        "patch_transport": patch_transport,
        "line_ending_normalization": False,
        "whitespace_normalization": False,
        **state_diag,
        "patch_blocks": len(patch_blocks),
        "ok": False,
        "failure_reason": None,
    }
    outside = STATE_JSON_BLOCK_RE.sub("", raw_norm)
    outside = PATCH_BLOCK_RE.sub("", outside).strip()
    if outside:
        diag["failure_reason"] = "state_json_invalid"
        diag["detail"] = "prose_or_extra_text_outside_required_blocks"
        return None, diag, None
    if state_obj is None:
        diag["failure_reason"] = state_diag.get("failure_reason") or "state_json_invalid"
        return None, diag, None
    if len(patch_blocks) != 1:
        diag["failure_reason"] = "patch_block_missing"
        diag["detail"] = f"expected_one_patch_block_got_{len(patch_blocks)}"
        return None, diag, {"state": state_obj}
    patch_text = patch_blocks[0]
    if "<STATE_JSON>" in patch_text or "</STATE_JSON>" in patch_text:
        diag["failure_reason"] = "patch_diff_missing"
        diag["detail"] = "patch_block_contains_state_json_tag"
        return None, diag, {"state": state_obj}
    if patch_text.lstrip().startswith("{") and "diff --git " not in patch_text:
        diag["failure_reason"] = "patch_diff_missing"
        diag["detail"] = "patch_block_looks_like_json"
        return None, diag, {"state": state_obj}
    patch, patch_diag = extract_patch(patch_text)
    diag["patch_extraction"] = patch_diag
    if patch is None:
        diag["failure_reason"] = "patch_diff_missing"
        diag["detail"] = patch_diag.get("failure_reason")
        return None, diag, {"state": state_obj}
    validation = validate_patch(patch)
    diag["candidate_patch_validator"] = validation
    if not validation["ok"]:
        diag["failure_reason"] = "patch_file_scope_invalid"
        diag["detail"] = validation.get("bad_files")
        return None, diag, {"state": state_obj}
    diag["ok"] = True
    diag["failure_reason"] = None
    diag["patch_sha256"] = sha256_text(patch)
    diag["patch_bytes"] = len(patch.encode("utf-8"))
    diag["files"] = validation["files"]
    return patch, diag, {"state": state_obj}


def validate_whole_file_edits(task_dir: Path, payload: dict[str, Any], max_files: int) -> tuple[list[dict[str, str]], dict[str, Any]]:
    repo = task_dir / "environment" / "repo"
    edits_raw = payload.get("edits")
    bad: list[dict[str, str]] = []
    edits: list[dict[str, str]] = []
    if not isinstance(edits_raw, list):
        return [], {"ok": False, "failure_reason": "edits_not_list", "files": [], "bad_files": []}
    if len(edits_raw) > max_files:
        bad.append({"path": "", "reason": f"too_many_edits:{len(edits_raw)}>{max_files}"})
    seen: set[str] = set()
    for idx, item in enumerate(edits_raw):
        if not isinstance(item, dict):
            bad.append({"path": f"<edit:{idx}>", "reason": "edit_not_object"})
            continue
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not isinstance(content, str):
            bad.append({"path": str(path), "reason": "path_or_content_not_string"})
            continue
        if path in seen:
            bad.append({"path": path, "reason": "duplicate_path"})
            continue
        seen.add(path)
        if not is_safe_repo_path(path):
            bad.append({"path": path, "reason": "unsafe_or_forbidden_path"})
            continue
        src = repo / path
        if not src.exists() or not src.is_file():
            bad.append({"path": path, "reason": "file_does_not_exist"})
            continue
        if is_binary(src):
            bad.append({"path": path, "reason": "binary_file"})
            continue
        edits.append({"path": path, "content": content})
    return edits, {"ok": bool(edits) and not bad, "files": [edit["path"] for edit in edits], "bad_files": bad}


def whole_file_edits_to_patch(task_dir: Path, edits: list[dict[str, str]]) -> tuple[str | None, dict[str, Any]]:
    repo = task_dir / "environment" / "repo"
    patch_parts: list[str] = []
    changed_files: list[str] = []
    for edit in edits:
        rel = edit["path"]
        old_text = read_text_exact_utf8(repo / rel)
        new_text = edit["content"]
        if old_text == new_text:
            continue
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        diff_lines = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
                n=3,
            )
        )
        if not diff_lines:
            continue
        patch_parts.append(f"diff --git a/{rel} b/{rel}\n" + "".join(diff_lines))
        if patch_parts[-1] and not patch_parts[-1].endswith("\n"):
            patch_parts[-1] += "\n"
        changed_files.append(rel)
    diag = {
        "ok": bool(patch_parts),
        "files": changed_files,
        "failure_reason": None if patch_parts else "no_file_content_changes",
    }
    if not patch_parts:
        return None, diag
    patch = "".join(patch_parts)
    diag["patch_sha256"] = sha256_text(patch)
    diag["patch_bytes"] = len(patch.encode("utf-8"))
    return patch, diag


def validate_search_replace_edits(task_dir: Path, payload: dict[str, Any], max_edits: int) -> tuple[list[dict[str, str]], dict[str, Any]]:
    repo = task_dir / "environment" / "repo"
    replacements_raw = payload.get("replacements")
    bad: list[dict[str, str]] = []
    replacements: list[dict[str, str]] = []
    if not isinstance(replacements_raw, list):
        return [], {"ok": False, "failure_reason": "replacements_not_list", "files": [], "bad_files": []}
    if len(replacements_raw) > max_edits:
        bad.append({"path": "", "reason": f"too_many_replacements:{len(replacements_raw)}>{max_edits}"})
    for idx, item in enumerate(replacements_raw):
        if not isinstance(item, dict):
            bad.append({"path": f"<replacement:{idx}>", "reason": "replacement_not_object"})
            continue
        path = item.get("path")
        old = item.get("old")
        new = item.get("new")
        if not isinstance(path, str) or not isinstance(old, str) or not isinstance(new, str):
            bad.append({"path": str(path), "reason": "path_old_or_new_not_string"})
            continue
        if not old:
            bad.append({"path": path, "reason": "old_text_empty"})
            continue
        if not is_safe_repo_path(path):
            bad.append({"path": path, "reason": "unsafe_or_forbidden_path"})
            continue
        src = repo / path
        if not src.exists() or not src.is_file():
            bad.append({"path": path, "reason": "file_does_not_exist"})
            continue
        if is_binary(src):
            bad.append({"path": path, "reason": "binary_file"})
            continue
        replacements.append({"path": path, "old": old, "new": new})
    return replacements, {"ok": bool(replacements) and not bad, "files": sorted({item["path"] for item in replacements}), "bad_files": bad}


def search_replace_edits_to_patch(task_dir: Path, replacements: list[dict[str, str]]) -> tuple[str | None, dict[str, Any]]:
    repo = task_dir / "environment" / "repo"
    contents: dict[str, str] = {}
    bad: list[dict[str, str]] = []
    for repl in replacements:
        rel = repl["path"]
        if rel not in contents:
            contents[rel] = (repo / rel).read_text(encoding="utf-8", errors="replace")
        count = contents[rel].count(repl["old"])
        if count != 1:
            bad.append({"path": rel, "reason": f"old_text_occurrence_count:{count}"})
            continue
        contents[rel] = contents[rel].replace(repl["old"], repl["new"], 1)
    if bad:
        return None, {"ok": False, "files": sorted(contents), "bad_replacements": bad, "failure_reason": "search_replace_validation_failed"}
    edits = [{"path": rel, "content": text} for rel, text in sorted(contents.items())]
    patch, diag = whole_file_edits_to_patch(task_dir, edits)
    diag["source_format"] = "search_replace_json"
    return patch, diag


def validate_file_ops(task_dir: Path, payload: dict[str, Any], max_files: int) -> tuple[list[dict[str, str]], dict[str, Any]]:
    repo = task_dir / "environment" / "repo"
    ops_raw = payload.get("ops")
    bad: list[dict[str, str]] = []
    ops: list[dict[str, str]] = []
    created: list[str] = []
    deleted: list[str] = []
    modified: list[str] = []
    if not isinstance(ops_raw, list):
        return [], {"ok": False, "failure_reason": "ops_not_list", "files": [], "bad_files": []}
    if len(ops_raw) > max_files:
        bad.append({"path": "", "reason": f"too_many_ops:{len(ops_raw)}>{max_files}"})
    write_or_delete_paths: set[str] = set()
    for idx, item in enumerate(ops_raw):
        if not isinstance(item, dict):
            bad.append({"path": f"<op:{idx}>", "reason": "op_not_object"})
            continue
        op = item.get("op")
        path = item.get("path")
        content = item.get("content")
        if op not in {"write", "delete", "append", "replace", "insert_before", "insert_after"}:
            bad.append({"path": str(path), "reason": "unknown_op"})
            continue
        if not isinstance(path, str):
            bad.append({"path": str(path), "reason": "path_not_string"})
            continue
        if op in {"write", "delete"} and path in write_or_delete_paths:
            bad.append({"path": path, "reason": "duplicate_write_or_delete_path"})
            continue
        if op in {"write", "delete"}:
            write_or_delete_paths.add(path)
        if not is_safe_repo_path(path):
            bad.append({"path": path, "reason": "unsafe_or_forbidden_path"})
            continue
        src = repo / path
        exists = src.exists() and src.is_file()
        if op == "delete":
            if not exists:
                bad.append({"path": path, "reason": "delete_file_does_not_exist"})
                continue
            if is_binary(src):
                bad.append({"path": path, "reason": "binary_file"})
                continue
            ops.append({"op": "delete", "path": path})
            deleted.append(path)
            continue
        if op == "write":
            if not isinstance(content, str):
                bad.append({"path": path, "reason": "write_content_not_string"})
                continue
            if exists and is_binary(src):
                bad.append({"path": path, "reason": "binary_file"})
                continue
            if not exists and not is_probable_text_edit_path(path):
                bad.append({"path": path, "reason": "new_file_not_source_like"})
                continue
            ops.append({"op": "write", "path": path, "content": content})
            if exists:
                modified.append(path)
            else:
                created.append(path)
            continue
        if not exists:
            bad.append({"path": path, "reason": f"{op}_file_does_not_exist"})
            continue
        if is_binary(src):
            bad.append({"path": path, "reason": "binary_file"})
            continue
        if op == "append":
            if not isinstance(content, str):
                bad.append({"path": path, "reason": "append_content_not_string"})
                continue
            ops.append({"op": "append", "path": path, "content": content})
            modified.append(path)
            continue
        if op == "replace":
            old = item.get("old")
            new = item.get("new")
            if new is None and isinstance(content, str):
                new = content
            if not isinstance(old, str) or not isinstance(new, str) or not old:
                bad.append({"path": path, "reason": "replace_old_or_new_invalid"})
                continue
            ops.append({"op": "replace", "path": path, "old": old, "new": new})
            modified.append(path)
            continue
        anchor = item.get("anchor")
        if not isinstance(content, str):
            bad.append({"path": path, "reason": f"{op}_content_not_string"})
            continue
        if not isinstance(anchor, str) or not anchor:
            bad.append({"path": path, "reason": f"{op}_anchor_invalid"})
            continue
        ops.append({"op": op, "path": path, "anchor": anchor, "content": content})
        modified.append(path)
    return ops, {
        "ok": bool(ops) and not bad,
        "files": [op["path"] for op in ops],
        "bad_files": bad,
        "created_files": created,
        "deleted_files": deleted,
        "modified_files": modified,
    }


def file_ops_to_patch(task_dir: Path, ops: list[dict[str, str]]) -> tuple[str | None, dict[str, Any]]:
    repo = task_dir / "environment" / "repo"
    original: dict[str, str | None] = {}
    contents: dict[str, str | None] = {}
    bad: list[dict[str, str]] = []
    created_files: list[str] = []
    deleted_files: list[str] = []
    modified_files: list[str] = []

    def ensure_loaded(rel: str) -> str | None:
        if rel in contents:
            return contents[rel]
        src = repo / rel
        if src.exists():
            text = src.read_text(encoding="utf-8", errors="replace")
            original[rel] = text
            contents[rel] = text
            return text
        original[rel] = None
        contents[rel] = None
        return None

    for op in ops:
        rel = op["path"]
        current = ensure_loaded(rel)
        if op["op"] == "delete":
            if current is None:
                bad.append({"path": rel, "reason": "delete_target_missing_after_prior_ops"})
                continue
            contents[rel] = None
            continue
        if op["op"] == "write":
            contents[rel] = op["content"]
            continue
        if current is None:
            bad.append({"path": rel, "reason": f"{op['op']}_target_missing_after_prior_ops"})
            continue
        if op["op"] == "append":
            contents[rel] = current + op["content"]
            continue
        if op["op"] == "replace":
            count = current.count(op["old"])
            if count != 1:
                bad.append({"path": rel, "reason": f"replace_old_occurrence_count:{count}"})
                continue
            contents[rel] = current.replace(op["old"], op["new"], 1)
            continue
        anchor = op["anchor"]
        count = current.count(anchor)
        if count != 1:
            bad.append({"path": rel, "reason": f"{op['op']}_anchor_occurrence_count:{count}"})
            continue
        if op["op"] == "insert_before":
            contents[rel] = current.replace(anchor, op["content"] + anchor, 1)
        elif op["op"] == "insert_after":
            contents[rel] = current.replace(anchor, anchor + op["content"], 1)

    if bad:
        return None, {"ok": False, "files": sorted(contents), "bad_ops": bad, "failure_reason": "file_op_application_failed"}

    patch_parts: list[str] = []
    changed_files: list[str] = []
    for rel in sorted(contents):
        old_text = original.get(rel)
        new_text = contents[rel]
        if old_text == new_text:
            continue
        src = repo / rel
        if old_text is None:
            diff_lines = list(
                difflib.unified_diff(
                    [],
                    (new_text or "").splitlines(keepends=True),
                    fromfile="/dev/null",
                    tofile=f"b/{rel}",
                    n=3,
                )
            )
            if not diff_lines:
                continue
            part = f"diff --git a/{rel} b/{rel}\n"
            part += "new file mode 100644\n"
            part += "".join(diff_lines)
            created_files.append(rel)
        elif new_text is None:
            diff_lines = list(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    [],
                    fromfile=f"a/{rel}",
                    tofile="/dev/null",
                    n=3,
                )
            )
            if not diff_lines:
                continue
            part = f"diff --git a/{rel} b/{rel}\n"
            part += f"deleted file mode {file_mode_line(src)}\n"
            part += "".join(diff_lines)
            deleted_files.append(rel)
        else:
            diff_lines = list(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=f"a/{rel}",
                    tofile=f"b/{rel}",
                    n=3,
                )
            )
            if not diff_lines:
                continue
            part = f"diff --git a/{rel} b/{rel}\n" + "".join(diff_lines)
            modified_files.append(rel)
        if part and not part.endswith("\n"):
            part += "\n"
        patch_parts.append(part)
        changed_files.append(rel)
    diag = {
        "ok": bool(patch_parts),
        "files": changed_files,
        "created_files": created_files,
        "deleted_files": deleted_files,
        "modified_files": modified_files,
        "failure_reason": None if patch_parts else "no_file_content_changes",
    }
    if not patch_parts:
        return None, diag
    patch = "".join(patch_parts)
    diag["patch_sha256"] = sha256_text(patch)
    diag["patch_bytes"] = len(patch.encode("utf-8"))
    return patch, diag


def extract_candidate(
    raw: str,
    task_dir: Path,
    edit_format: str,
    whole_file_max_files: int,
    search_replace_max_edits: int,
    file_op_max_files: int,
    state_contract: str = "none",
    patch_transport: str = "unified_diff",
    allowed_existing_paths: set[str] | None = None,
) -> tuple[str | None, dict[str, Any], dict[str, Any] | None]:
    if state_contract == "answer_state":
        return extract_tagged_answer_state(raw, task_dir, patch_transport, allowed_existing_paths=allowed_existing_paths)
    if edit_format == "unified_diff":
        patch, diag = extract_patch(raw)
        diag["edit_format"] = edit_format
        return patch, diag, None
    if edit_format == "whole_file_json":
        payload, json_diag = extract_json_payload(raw)
        json_diag["edit_format"] = edit_format
        if payload is None:
            return None, json_diag, None
        edits, validation = validate_whole_file_edits(task_dir, payload, whole_file_max_files)
        patch, patch_diag = whole_file_edits_to_patch(task_dir, edits) if validation["ok"] else (None, {"ok": False, "failure_reason": "edit_validation_failed"})
        diag = {**json_diag, "edit_validation": validation, "patch_generation": patch_diag}
        if patch is None:
            diag["ok"] = False
            diag["failure_reason"] = validation.get("failure_reason") or patch_diag.get("failure_reason") or "whole_file_patch_generation_failed"
        return patch, diag, payload
    if edit_format == "search_replace_json":
        payload, json_diag = extract_json_payload(raw)
        json_diag["edit_format"] = edit_format
        if payload is None:
            return None, json_diag, None
        replacements, validation = validate_search_replace_edits(task_dir, payload, search_replace_max_edits)
        patch, patch_diag = search_replace_edits_to_patch(task_dir, replacements) if validation["ok"] else (None, {"ok": False, "failure_reason": "replacement_validation_failed"})
        diag = {**json_diag, "replacement_validation": validation, "patch_generation": patch_diag}
        if patch is None:
            diag["ok"] = False
            diag["failure_reason"] = validation.get("failure_reason") or patch_diag.get("failure_reason") or "search_replace_patch_generation_failed"
        return patch, diag, payload
    if edit_format == "file_ops_json":
        payload, json_diag = extract_json_payload(raw)
        json_diag["edit_format"] = edit_format
        if payload is None:
            return None, json_diag, None
        ops, validation = validate_file_ops(task_dir, payload, file_op_max_files)
        patch, patch_diag = file_ops_to_patch(task_dir, ops) if validation["ok"] else (None, {"ok": False, "failure_reason": "file_op_validation_failed"})
        diag = {**json_diag, "file_op_validation": validation, "patch_generation": patch_diag}
        if patch is None:
            diag["ok"] = False
            diag["failure_reason"] = validation.get("failure_reason") or patch_diag.get("failure_reason") or "file_ops_patch_generation_failed"
        return patch, diag, payload
    raise ValueError(f"unknown edit format: {edit_format}")


def ensure_tmp_tasks(task_ids: list[str]) -> None:
    TMP_TASK_ROOT.mkdir(parents=True, exist_ok=True)
    for task_id in task_ids:
        src = TASKS_ROOT / task_id
        dst = TMP_TASK_ROOT / task_id
        if dst.exists():
            continue
        shutil.copytree(src, dst, symlinks=True)


def ensure_image(task_id: str) -> dict[str, Any]:
    image = f"roadmapbench-{task_id}"
    if subprocess.run(["docker", "image", "inspect", image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        return {"image": image, "source": "local"}
    sources = [f"znpt/{image}", f"docker.1ms.run/znpt/{image}"]
    for source in sources:
        proc = subprocess.run(["docker", "pull", "--platform", "linux/amd64", source], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0:
            subprocess.run(["docker", "tag", source, image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"image": image, "source": source}
    task_dir = TMP_TASK_ROOT / task_id
    proc = subprocess.run(["docker", "build", "-t", image, str(task_dir / "environment")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        return {"image": image, "source": "build_failed", "stderr": proc.stderr[-2000:]}
    return {"image": image, "source": "local_build"}


def classify_patch_failure(finish_reason: str | None, stderr: str, patch_text: str = "") -> str | None:
    first = stderr.strip().splitlines()[0] if stderr.strip() else ""
    if finish_reason == "length":
        return "likely_output_truncated"
    if "--- FILE:" in patch_text:
        return "malformed_diff_hunk_or_pseudo_header"
    if "only garbage" in first:
        return "garbage_diff_skeleton"
    if "fragment without header" in first:
        return "malformed_diff_hunk_or_pseudo_header"
    if "corrupt patch" in first:
        return "malformed_diff_hunk_or_pseudo_header"
    if "patch failed" in first or "patch does not apply" in first:
        return "context_mismatch_or_stale_hunk"
    if first:
        return "other_patch_apply_failure"
    return None


def local_patch_apply_check(
    run_dir: Path,
    row: dict[str, Any],
    finish_reason: str | None,
    patch_path_override: Path | None = None,
    check_subdir: str | None = None,
) -> dict[str, Any]:
    task_id = row["task_id"]
    patch_path = patch_path_override or run_dir / "rows" / f"{row['row_index']:03d}_{row['run_id']}" / "candidate.patch"
    task_dir = TMP_TASK_ROOT / task_id
    repo = task_dir / "environment" / "repo"
    out_dir = run_dir / "patch_checks" / row["run_id"]
    if check_subdir:
        out_dir = out_dir / check_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    if not repo.exists():
        return {
            "patch_apply_check_ok": None,
            "patch_apply_check_returncode": None,
            "patch_failure_category": "repo_unavailable_for_patch_check",
            "patch_apply_check_dir": str(out_dir),
        }
    patch_text = patch_path.read_text(encoding="utf-8", errors="replace") if patch_path.exists() else ""
    proc = subprocess.run(
        ["git", "-C", str(repo), "apply", "--check", str(patch_path.resolve())],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    (out_dir / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (out_dir / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
    ok = proc.returncode == 0
    return {
        "patch_apply_check_ok": ok,
        "patch_apply_check_returncode": proc.returncode,
        "patch_failure_category": None if ok else classify_patch_failure(finish_reason, proc.stderr, patch_text),
        "patch_apply_check_dir": str(out_dir),
    }


def evaluate_patch(run_dir: Path, row: dict[str, Any], generated_row: dict[str, Any] | None = None, skip_invalid_patch: bool = False) -> dict[str, Any]:
    task_id = row["task_id"]
    patch_path = run_dir / "rows" / f"{row['row_index']:03d}_{row['run_id']}" / "candidate.patch"
    out_dir = run_dir / "eval" / row["run_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    finish_reason = (generated_row or row).get("finish_reason")
    local_check = local_patch_apply_check(run_dir, row, finish_reason)
    if skip_invalid_patch and local_check.get("patch_apply_check_ok") is False:
        failure_step = "patch_apply_failed" if (generated_row or row).get("state_contract") == "answer_state" else "patch_invalid"
        return add_answer_state_outcomes({
            **local_check,
            "docker_scored": False,
            "docker_returncode": None,
            "reward": None,
            "test_passed": False,
            "candidate_patch_applies": False,
            "apply_exit": "",
            "eval_output_dir": None,
            "failure_step": failure_step,
            "failure_reason": local_check.get("patch_failure_category"),
        }, generated_row)
    tmp_eval = Path(tempfile.gettempdir()) / "roadmapbench_deepseek_eval" / run_dir.name / row["run_id"]
    if tmp_eval.exists():
        shutil.rmtree(tmp_eval)
    tmp_eval.mkdir(parents=True, exist_ok=True)
    tmp_patch = tmp_eval / "candidate.patch"
    tmp_out = tmp_eval / "out"
    tmp_out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(patch_path, tmp_patch)
    image_info = ensure_image(task_id)
    image = image_info["image"]
    if image_info.get("source") == "build_failed":
        failure_step = "docker_verifier_failed" if (generated_row or row).get("state_contract") == "answer_state" else "image_unavailable"
        return add_answer_state_outcomes(
            {**local_check, "docker_scored": False, "failure_step": failure_step, "failure_reason": image_info.get("stderr", "")},
            generated_row,
        )
    task_dir = TMP_TASK_ROOT / task_id
    timeout_sec = 1800
    task_toml = (task_dir / "task.toml").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"timeout_sec\s*=\s*(\d+)", task_toml)
    if m:
        timeout_sec = int(m.group(1))
    cmd = [
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "-v",
        f"{(task_dir / 'tests').resolve()}:/tests:ro",
        "-v",
        f"{tmp_patch.resolve()}:/patch.diff:ro",
        "-v",
        f"{tmp_out.resolve()}:/logs/verifier",
        image,
        "bash",
        "-c",
        (
            "cd /app\n"
            "git apply --check /patch.diff >/logs/verifier/apply_check.stdout 2>/logs/verifier/apply_check.stderr\n"
            "APPLY_CHECK=$?\n"
            "if [ \"$APPLY_CHECK\" -eq 0 ]; then git apply /patch.diff >/logs/verifier/apply.stdout 2>/logs/verifier/apply.stderr; APPLY=$?; "
            "else patch -p1 < /patch.diff >/logs/verifier/patch_apply.stdout 2>/logs/verifier/patch_apply.stderr; APPLY=$?; fi\n"
            "echo \"$APPLY_CHECK\" >/logs/verifier/apply_check.exit\n"
            "echo \"$APPLY\" >/logs/verifier/apply.exit\n"
            "bash /tests/test.sh\n"
        ),
    ]
    started = utc_now()
    with (tmp_out / "docker.stdout").open("w", encoding="utf-8") as stdout, (tmp_out / "docker.stderr").open("w", encoding="utf-8") as stderr:
        try:
            proc = subprocess.run(cmd, stdout=stdout, stderr=stderr, cwd=ROOT, timeout=timeout_sec + 60)
        except subprocess.TimeoutExpired as exc:
            if out_dir.exists():
                shutil.rmtree(out_dir)
            shutil.copytree(tmp_out, out_dir)
            failure_step = "docker_verifier_failed" if (generated_row or row).get("state_contract") == "answer_state" else "docker_timeout"
            return add_answer_state_outcomes({
                **local_check,
                "docker_scored": True,
                "docker_returncode": None,
                "reward": None,
                "test_passed": False,
                "candidate_patch_applies": None,
                "apply_exit": "",
                "image": image,
                "image_source": image_info.get("source"),
                "eval_output_dir": str(out_dir),
                "eval_start_utc": started,
                "eval_end_utc": utc_now(),
                "failure_step": failure_step,
                "failure_reason": str(exc),
            }, generated_row)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(tmp_out, out_dir)
    reward_path = out_dir / "reward.txt"
    reward = None
    if reward_path.exists():
        try:
            reward = float(reward_path.read_text(encoding="utf-8", errors="replace").strip())
        except ValueError:
            reward = None
    apply_exit = (out_dir / "apply.exit").read_text(encoding="utf-8", errors="replace").strip() if (out_dir / "apply.exit").exists() else ""
    passed = reward is not None and reward >= 0.9999
    if (generated_row or row).get("state_contract") == "answer_state":
        failure_step = "test_passed" if passed else "test_failed"
    else:
        failure_step = None if passed else "test_failed_or_partial_reward"
    result = {
        **local_check,
        "docker_scored": True,
        "docker_returncode": proc.returncode,
        "reward": reward,
        "test_passed": passed,
        "candidate_patch_applies": apply_exit == "0",
        "apply_exit": apply_exit,
        "image": image,
        "image_source": image_info.get("source"),
        "eval_output_dir": str(out_dir),
        "eval_start_utc": started,
        "eval_end_utc": utc_now(),
        "failure_step": failure_step,
    }
    return add_answer_state_outcomes(result, generated_row)


def compact_failure_for_repair(
    response_diag: dict[str, Any],
    extract_diag: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    local_check: dict[str, Any] | None,
) -> dict[str, Any]:
    failure: dict[str, Any] = {
        "finish_reason": response_diag.get("finish_reason"),
        "failure_reason": extract_diag.get("failure_reason") if extract_diag else None,
    }
    if extract_diag:
        for key in ("edit_validation", "replacement_validation", "file_op_validation", "patch_generation", "patch_extraction"):
            if key in extract_diag:
                failure[key] = extract_diag[key]
    if validation and not validation.get("ok"):
        failure["patch_validator"] = validation
    if local_check and local_check.get("patch_apply_check_ok") is False:
        failure["patch_apply_check"] = {
            "category": local_check.get("patch_failure_category"),
            "returncode": local_check.get("patch_apply_check_returncode"),
        }
        check_dir = local_check.get("patch_apply_check_dir")
        if check_dir:
            stderr_path = Path(check_dir) / "stderr.txt"
            if stderr_path.exists():
                failure["patch_apply_stderr_tail"] = stderr_path.read_text(encoding="utf-8", errors="replace")[-2000:]
    return failure


def render_repair_prompt(original_prompt: str, edit_format: str, failure: dict[str, Any], state_contract: str = "none", patch_transport: str = "unified_diff") -> str:
    repair_lines = [
        "# Repair Attempt",
        "Your previous response failed local extraction or patch validation.",
        "Do not explain. Return only one corrected response in the same output format.",
        "Use fewer files if needed, but each create content must be complete and valid.",
        "If a required source file does not exist, create it with a create operation instead of referencing it as an existing file.",
        "Never use tests/, solution/, logs/, results/, verifier/, eval/, task.toml, or benchmark metadata paths.",
        "",
        "# Failure Summary",
        json.dumps(failure, ensure_ascii=False, sort_keys=True)[:12000],
    ]
    if state_contract == "answer_state" and patch_transport == "edit_json":
        repair_lines.extend(
            [
                "",
                "# Corrected Output Reminder",
                "Return exactly one <STATE_JSON> block and one <EDIT_JSON> block.",
                "EDIT_JSON must be valid JSON with a non-empty ops list; supported strict ops are create, replace, and delete.",
                "For replace, old must match exactly once in the current sequential working copy at that op.",
                "Do not return a unified diff or file_ops JSON outside the required tags.",
            ]
        )
    elif state_contract == "answer_state":
        repair_lines.extend(
            [
                "",
                "# Corrected Output Reminder",
                "Return exactly one <STATE_JSON> block and one <PATCH> block.",
                "PATCH must contain a valid unified diff beginning with diff --git.",
            ]
        )
    elif edit_format == "file_ops_json":
        repair_lines.extend(
            [
                "",
                "# Corrected Output Reminder",
                'Return exactly {"ops":[...]} using write/delete/append/replace/insert_before/insert_after operations.',
                "For replace use old/new. For insert_before or insert_after use anchor/content. Anchors and old strings must occur exactly once.",
            ]
        )
    return original_prompt + "\n\n" + "\n".join(repair_lines)


def file_change_stats_from_diag(diag: dict[str, Any]) -> dict[str, Any]:
    validation = diag.get("file_op_validation") if isinstance(diag.get("file_op_validation"), dict) else {}
    edit_validation = diag.get("edit_validation") if isinstance(diag.get("edit_validation"), dict) else {}
    patch_generation = diag.get("patch_generation") if isinstance(diag.get("patch_generation"), dict) else {}
    return {
        "created_files": patch_generation.get("created_files") or edit_validation.get("created_files") or validation.get("created_files") or [],
        "deleted_files": patch_generation.get("deleted_files") or edit_validation.get("deleted_files") or validation.get("deleted_files") or [],
        "modified_files": patch_generation.get("modified_files") or edit_validation.get("modified_files") or validation.get("modified_files") or [],
    }


def answer_state_transport_stats_from_diag(diag: dict[str, Any], patch_transport: str) -> dict[str, Any]:
    edit_validation = diag.get("edit_validation") if isinstance(diag.get("edit_validation"), dict) else {}
    return {
        "patch_transport": patch_transport,
        "edit_json_valid": bool(diag.get("edit_json_valid") or edit_validation.get("edit_json_valid")),
        "deterministic_edit_apply_success": bool(
            diag.get("deterministic_edit_apply_success") or edit_validation.get("deterministic_edit_apply_success")
        ),
        "deterministic_patch_generated": bool(
            diag.get("deterministic_patch_generated") or edit_validation.get("deterministic_patch_generated")
        ),
        "edit_op_statuses": edit_validation.get("op_statuses") or diag.get("op_statuses") or [],
        "edit_touched_files_in_order": edit_validation.get("touched_files_in_order") or diag.get("touched_files_in_order") or [],
        "edit_line_ending_normalization": bool(
            diag.get("line_ending_normalization") or edit_validation.get("line_ending_normalization")
        ),
        "edit_whitespace_normalization": bool(
            diag.get("whitespace_normalization") or edit_validation.get("whitespace_normalization")
        ),
    }


def normalize_answer_state_failure_step(finish_reason: str | None, failure_reason: str | None, fallback: str) -> str:
    if finish_reason == "length":
        return "finish_reason_length"
    if failure_reason in ANSWER_STATE_FAILURE_STEPS:
        return str(failure_reason)
    return fallback


def fail_closed_for_finish_reason_length(state_score: dict[str, Any]) -> dict[str, Any]:
    out = dict(state_score)
    out["action_governance_success"] = False
    out["state_governance_success"] = False
    out["answer_success"] = False
    out["reliable_composite_success"] = False
    reasons = list(out.get("state_failure_reasons") or [])
    reasons.append("finish_reason_length")
    out["state_failure_reasons"] = sorted(set(reasons))
    return out


def generate_one(run_dir: Path, row: dict[str, Any], args: argparse.Namespace, provider_info: tuple[str, str, str, str]) -> dict[str, Any]:
    row_dir = run_dir / "rows" / f"{row['row_index']:03d}_{row['run_id']}"
    row_dir.mkdir(parents=True, exist_ok=True)
    base_prompt = (run_dir / "prompts" / f"{row['run_id']}.txt").read_text(encoding="utf-8")
    raw_path = row_dir / "raw_response.txt"
    patch_path = row_dir / "candidate.patch"
    edit_json_path = row_dir / "candidate_edit.json"
    task_dir = TASKS_ROOT / row["task_id"]
    edit_format = row.get("edit_format", args.edit_format)
    provider, url, api_key_env, model = provider_info
    repair_events: list[dict[str, Any]] = []
    prompt = base_prompt
    try:
        for attempt in range(args.repair_attempts + 1):
            attempt_dir = row_dir / "attempts" / f"attempt_{attempt}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            attempt_prompt_path = attempt_dir / "prompt.txt"
            attempt_prompt_path.write_text(prompt, encoding="utf-8")
            body, response = call_model(prompt, provider, url, api_key_env, model, args.max_tokens, args.timeout_seconds, args.api_attempts)
            response_diag = response_diagnostics(response["payload"])
            body_for_log = compact_api_request_meta(
                body,
                prompt,
                provider,
                url,
                api_key_env,
                stage="single_shot_or_stage2",
                prompt_path=str(attempt_prompt_path),
                repair_attempt=attempt,
                timeout_seconds=args.timeout_seconds,
                api_attempts=args.api_attempts,
            )
            write_json(attempt_dir / "api_request_meta.json", body_for_log)
            write_json(attempt_dir / "api_request_body_redacted.json", redacted_api_request_body(body))
            write_json(attempt_dir / "api_response_payload.json", response["payload"])
            write_json(attempt_dir / "api_response_meta.json", response["meta"])
            raw = response["payload"]["choices"][0]["message"]["content"]
            (attempt_dir / "raw_response.txt").write_text(raw, encoding="utf-8")
            strict_existing = row.get("strict_edit_existing_files")
            allowed_existing_paths = set(strict_existing) if isinstance(strict_existing, list) else None
            patch, diag, edit_payload = extract_candidate(
                raw,
                task_dir,
                edit_format,
                args.whole_file_max_files,
                args.search_replace_max_edits,
                args.file_op_max_files,
                args.state_contract,
                args.patch_transport,
                allowed_existing_paths,
            )
            write_json(attempt_dir / "extractor_diagnostics.json", diag)
            if edit_payload is not None:
                write_json(attempt_dir / "candidate_edit.json", edit_payload)

            validation = None
            local_check = None
            if patch is not None:
                attempt_patch_path = attempt_dir / "candidate.patch"
                attempt_patch_path.write_text(patch, encoding="utf-8", newline="\n")
                validation = validate_patch(patch)
                write_json(attempt_dir / "candidate_patch_validator_diagnostics.json", validation)
                if validation["ok"]:
                    local_check = local_patch_apply_check(
                        run_dir,
                        row,
                        response_diag.get("finish_reason"),
                        patch_path_override=attempt_patch_path,
                        check_subdir=f"attempt_{attempt}",
                    )
                    write_json(attempt_dir / "local_patch_apply_check.json", local_check)

            state_score = score_state_governance(
                edit_payload,
                args.state_contract,
                validation["files"] if validation else [],
                raw,
                patch or "",
                transport_valid=bool(patch is not None and validation and validation.get("ok")),
                patch_applies=bool(local_check and local_check.get("patch_apply_check_ok")),
            )
            write_json(attempt_dir / "answer_state_diagnostics.json", state_score)

            failure = compact_failure_for_repair(response_diag, diag, validation, local_check)
            should_repair = False
            if patch is None:
                should_repair = True
            elif validation and not validation["ok"]:
                should_repair = True
            elif local_check and local_check.get("patch_apply_check_ok") is False:
                should_repair = True
            elif response_diag.get("finish_reason") == "length":
                should_repair = True

            if should_repair and attempt < args.repair_attempts:
                repair_events.append({"attempt": attempt, "failure": failure, "timestamp_utc": utc_now()})
                prompt = render_repair_prompt(base_prompt, edit_format, failure, args.state_contract, args.patch_transport)
                continue

            if response_diag.get("finish_reason") == "length" and args.state_contract == "answer_state":
                state_score = fail_closed_for_finish_reason_length(state_score)

            raw_path.write_text(raw, encoding="utf-8")
            write_json(row_dir / "api_request_meta.json", body_for_log)
            write_json(row_dir / "api_request_body_redacted.json", redacted_api_request_body(body))
            write_json(row_dir / "api_response_payload.json", response["payload"])
            write_json(row_dir / "api_response_meta.json", response["meta"])
            write_json(row_dir / "extractor_diagnostics.json", diag)
            write_json(row_dir / "repair_events.json", repair_events)
            if edit_payload is not None:
                write_json(edit_json_path, edit_payload)
            write_json(row_dir / "answer_state_diagnostics.json", state_score)

            if patch is None:
                failure_step = (
                    normalize_answer_state_failure_step(response_diag.get("finish_reason"), diag.get("failure_reason"), "patch_diff_missing")
                    if args.state_contract == "answer_state"
                    else "patch_extract_failed"
                )
                return {
                    **row,
                    **response_diag,
                    **answer_state_transport_stats_from_diag(diag, args.patch_transport),
                    "edit_format": edit_format,
                    "generation_ok": True,
                    "extract_ok": False,
                    "repair_count": attempt,
                    "created_files": [],
                    "deleted_files": [],
                    "modified_files": [],
                    **state_score,
                    "final_failure_category": failure_step if args.state_contract == "answer_state" else diag.get("failure_reason"),
                    "failure_step": failure_step,
                    "failure_reason": diag["failure_reason"],
                    "timestamp_utc": utc_now(),
                }

            if response_diag.get("finish_reason") == "length" and args.state_contract == "answer_state":
                stats = file_change_stats_from_diag(diag)
                return {
                    **row,
                    **response_diag,
                    **stats,
                    **answer_state_transport_stats_from_diag(diag, args.patch_transport),
                    "edit_format": edit_format,
                    "generation_ok": True,
                    "extract_ok": False,
                    "repair_count": attempt,
                    "created_files": stats.get("created_files", []),
                    "deleted_files": stats.get("deleted_files", []),
                    "modified_files": stats.get("modified_files", []),
                    "candidate_validate_ok": False,
                    **state_score,
                    "failure_step": "finish_reason_length",
                    "failure_reason": "finish_reason_length",
                    "final_failure_category": "finish_reason_length",
                    "timestamp_utc": utc_now(),
                }

            patch_path.write_text(patch, encoding="utf-8", newline="\n")
            validation = validation or validate_patch(patch)
            write_json(row_dir / "candidate_patch_validator_diagnostics.json", validation)
            if local_check:
                write_json(row_dir / "local_patch_apply_check.json", local_check)
            stats = file_change_stats_from_diag(diag)
            failure_step = None
            failure_reason = None
            final_failure_category = None
            if not validation["ok"]:
                failure_step = "patch_file_scope_invalid" if args.state_contract == "answer_state" else "candidate_patch_validation_failed"
                failure_reason = json.dumps(validation["bad_files"], ensure_ascii=False)
                final_failure_category = failure_step
            elif local_check and local_check.get("patch_apply_check_ok") is False:
                failure_step = "patch_apply_failed" if args.state_contract == "answer_state" else "patch_apply_check_failed"
                failure_reason = local_check.get("patch_failure_category")
                final_failure_category = failure_step if args.state_contract == "answer_state" else local_check.get("patch_failure_category")
            elif response_diag.get("finish_reason") == "length":
                failure_step = "finish_reason_length" if args.state_contract == "answer_state" else failure_step
                final_failure_category = "finish_reason_length" if args.state_contract == "answer_state" else "likely_output_truncated"
            result = {
                **row,
                **response_diag,
                **(local_check or {}),
                **stats,
                **answer_state_transport_stats_from_diag(diag, args.patch_transport),
                "edit_format": edit_format,
                "generation_ok": True,
                "extract_ok": True,
                "repair_count": attempt,
                "candidate_validate_ok": validation["ok"],
                "candidate_files": validation["files"],
                "candidate_patch_sha256": sha256_text(patch),
                **state_score,
                "timestamp_utc": utc_now(),
                "failure_step": failure_step,
                "failure_reason": failure_reason,
                "final_failure_category": final_failure_category,
            }
            return result
        raise RuntimeError("unreachable repair loop")
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, APINoResponseTimeout):
            for target_dir in [locals().get("attempt_dir"), row_dir]:
                if target_dir is not None:
                    write_json(target_dir / "api_request_meta.json", exc.meta)
                    write_json(target_dir / "api_request_body_redacted.json", redacted_api_request_body(exc.body))
                    write_json(target_dir / "api_error.json", {"timestamp_utc": utc_now(), "error_type": type(exc).__name__, "error": str(exc)})
        write_json(row_dir / "api_error.json", {"timestamp_utc": utc_now(), "error_type": type(exc).__name__, "error": str(exc)})
        write_json(row_dir / "repair_events.json", repair_events)
        failure_step = "api_no_response_timeout" if isinstance(exc, APINoResponseTimeout) else ("generation_failed" if args.state_contract == "answer_state" else "api_failed")
        return {
            **row,
            "edit_format": edit_format,
            "patch_transport": args.patch_transport,
            "generation_ok": False,
            "extract_ok": False,
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
            "transport_failure": isinstance(exc, APINoResponseTimeout),
            "model_quality_scored": False if isinstance(exc, APINoResponseTimeout) else None,
            "repair_count": len(repair_events),
            "timestamp_utc": utc_now(),
            "failure_step": failure_step,
            "failure_reason": str(exc),
            "final_failure_category": failure_step,
        }


def build_plan(
    run_dir: Path,
    task_ids: list[str],
    methods: list[str],
    budget: int,
    max_context_chars: int,
    edit_format: str,
    whole_file_max_files: int,
    search_replace_max_edits: int,
    file_op_max_files: int,
    context_mode: str,
    state_contract: str,
    patch_transport: str,
) -> list[dict[str, Any]]:
    prompts = run_dir / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    idx = 0
    for task_id in task_ids:
        task_dir = TASKS_ROOT / task_id
        for method in methods:
            idx += 1
            format_suffix = "" if edit_format == "unified_diff" else f"__fmt{edit_format}"
            run_id = f"roadmapbench_deepseek_5task_6method__{task_id}__{method}__b{budget}{format_suffix}__run0"
            prompt, meta = render_prompt(
                task_dir,
                method,
                budget,
                max_context_chars,
                edit_format,
                whole_file_max_files,
                search_replace_max_edits,
                file_op_max_files,
                context_mode,
                state_contract,
                patch_transport,
            )
            prompt_path = prompts / f"{run_id}.txt"
            prompt_path.write_text(prompt, encoding="utf-8")
            rows.append(
                {
                    "row_index": idx,
                    "run_id": run_id,
                    "task_id": task_id,
                    "method": method,
                    "budget": budget,
                    "edit_format": edit_format,
                    "patch_transport": patch_transport,
                    "model": DEFAULT_MODEL,
                    "prompt_path": str(prompt_path),
                    **meta,
                }
            )
    write_json(
        run_dir / "RUN_PLAN.json",
        {
            "created_utc": utc_now(),
            "rows": rows,
            "methods": methods,
            "tasks": task_ids,
            "budget": budget,
            "edit_format": edit_format,
            "whole_file_max_files": whole_file_max_files,
            "search_replace_max_edits": search_replace_max_edits,
            "file_op_max_files": file_op_max_files,
            "context_mode": context_mode,
            "state_contract": state_contract,
            "patch_transport": patch_transport,
        },
    )
    (run_dir / "RUN_PLAN.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    return rows


def row_dir_for(run_dir: Path, row: dict[str, Any]) -> Path:
    return run_dir / "rows" / f"{row['row_index']:03d}_{row['run_id']}"


def enrich_row_from_artifacts(run_dir: Path, row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    row_dir = row_dir_for(run_dir, row)
    payload_path = row_dir / "api_response_payload.json"
    if payload_path.exists() and not enriched.get("finish_reason"):
        try:
            enriched.update({k: v for k, v in response_diagnostics(read_json(payload_path)).items() if v is not None})
        except Exception:
            pass
    eval_dir_value = enriched.get("eval_output_dir")
    eval_dir = Path(eval_dir_value) if eval_dir_value else run_dir / "eval" / row["run_id"]
    if "patch_apply_check_ok" not in enriched:
        apply_check_exit = eval_dir / "apply_check.exit"
        if apply_check_exit.exists():
            enriched["patch_apply_check_ok"] = apply_check_exit.read_text(encoding="utf-8", errors="replace").strip() == "0"
    if not enriched.get("patch_failure_category"):
        stderr_path = eval_dir / "apply_check.stderr"
        if stderr_path.exists():
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
            patch_path = row_dir / "candidate.patch"
            patch_text = patch_path.read_text(encoding="utf-8", errors="replace") if patch_path.exists() else ""
            enriched["patch_failure_category"] = None if enriched.get("patch_apply_check_ok") else classify_patch_failure(enriched.get("finish_reason"), stderr, patch_text)
    if "edit_format" not in enriched:
        enriched["edit_format"] = "unified_diff"
    if "answer_success" not in enriched and "test_passed" in enriched:
        enriched = add_answer_state_outcomes(enriched)
    elif enriched.get("state_contract") == "answer_state" and "reliable_composite_success" not in enriched and "test_passed" in enriched:
        enriched = add_answer_state_outcomes(enriched)
    return enriched


def write_summary(run_dir: Path) -> None:
    result_path = run_dir / "RESULTS.jsonl"
    rows = [json.loads(line) for line in result_path.read_text(encoding="utf-8").splitlines() if line.strip()] if result_path.exists() else []
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest[row["run_id"]] = row
    vals = [enrich_row_from_artifacts(run_dir, row) for row in latest.values()]
    by_method: dict[str, dict[str, Any]] = {}
    by_task: dict[str, dict[str, Any]] = {}
    for key, field in [(by_method, "method"), (by_task, "task_id")]:
        for value in sorted({row[field] for row in vals}):
            items = [row for row in vals if row[field] == value]
            key[value] = {
                "rows": len(items),
                "generation_ok": sum(1 for row in items if row.get("generation_ok")),
                "extract_ok": sum(1 for row in items if row.get("extract_ok")),
                "patch_apply_check_ok": sum(1 for row in items if row.get("patch_apply_check_ok")),
                "patch_apply_check_failed": sum(1 for row in items if row.get("patch_apply_check_ok") is False),
                "candidate_applies": sum(1 for row in items if row.get("candidate_patch_applies")),
                "test_passed": sum(1 for row in items if row.get("test_passed")),
                "answer_success": sum(1 for row in items if row.get("answer_success") or row.get("test_passed")),
                "state_json_valid": sum(1 for row in items if row.get("state_json_valid") or row.get("state_parse_success")),
                "edit_json_valid": sum(1 for row in items if row.get("edit_json_valid")),
                "deterministic_edit_apply_success": sum(1 for row in items if row.get("deterministic_edit_apply_success")),
                "deterministic_patch_generated": sum(1 for row in items if row.get("deterministic_patch_generated")),
                "state_contract_valid": sum(1 for row in items if row.get("state_contract_valid")),
                "action_governance_success": sum(1 for row in items if row.get("action_governance_success") or row.get("state_governance_success")),
                "state_governance_success": sum(1 for row in items if row.get("action_governance_success") or row.get("state_governance_success")),
                "reliable_composite_success": sum(1 for row in items if row.get("reliable_composite_success")),
                "avg_reward": round(sum((row.get("reward") or 0.0) for row in items) / len(items), 4) if items else 0.0,
            }
    answer_success_count = sum(1 for row in vals if row.get("answer_success") or row.get("test_passed"))
    state_json_valid_count = sum(1 for row in vals if row.get("state_json_valid") or row.get("state_parse_success"))
    edit_json_valid_count = sum(1 for row in vals if row.get("edit_json_valid"))
    deterministic_edit_apply_success_count = sum(1 for row in vals if row.get("deterministic_edit_apply_success"))
    deterministic_patch_generated_count = sum(1 for row in vals if row.get("deterministic_patch_generated"))
    state_contract_valid_count = sum(1 for row in vals if row.get("state_contract_valid"))
    action_success_count = sum(1 for row in vals if row.get("action_governance_success") or row.get("state_governance_success"))
    state_success_count = action_success_count
    reliable_count = sum(1 for row in vals if row.get("reliable_composite_success"))
    answer_only_count = sum(
        1
        for row in vals
        if (row.get("answer_success") or row.get("test_passed")) and not (row.get("action_governance_success") or row.get("state_governance_success"))
    )
    governance_only_count = sum(
        1
        for row in vals
        if (row.get("action_governance_success") or row.get("state_governance_success")) and not (row.get("answer_success") or row.get("test_passed"))
    )
    neither_count = sum(
        1
        for row in vals
        if not (row.get("answer_success") or row.get("test_passed")) and not (row.get("action_governance_success") or row.get("state_governance_success"))
    )
    state_failure_counter: Counter[str] = Counter()
    for row in vals:
        for reason in row.get("state_failure_reasons") or []:
            state_failure_counter[str(reason)] += 1
    summary = {
        "updated_utc": utc_now(),
        "result_rows": len(vals),
        "generation_ok": sum(1 for row in vals if row.get("generation_ok")),
        "extract_ok": sum(1 for row in vals if row.get("extract_ok")),
        "docker_scored": sum(1 for row in vals if row.get("docker_scored")),
        "patch_apply_check_ok": sum(1 for row in vals if row.get("patch_apply_check_ok")),
        "patch_apply_check_failed": sum(1 for row in vals if row.get("patch_apply_check_ok") is False),
        "candidate_applies": sum(1 for row in vals if row.get("candidate_patch_applies")),
        "test_passed": sum(1 for row in vals if row.get("test_passed")),
        "answer_success": answer_success_count,
        "state_json_valid": state_json_valid_count,
        "edit_json_valid": edit_json_valid_count,
        "deterministic_edit_apply_success": deterministic_edit_apply_success_count,
        "deterministic_patch_generated": deterministic_patch_generated_count,
        "state_contract_valid": state_contract_valid_count,
        "action_governance_success": action_success_count,
        "state_governance_success": state_success_count,
        "reliable_composite_success": reliable_count,
        "answer_only": answer_only_count,
        "governance_only": governance_only_count,
        "neither_answer_nor_governance": neither_count,
        "finish_reasons": dict(Counter(str(row.get("finish_reason")) for row in vals if row.get("finish_reason"))),
        "length_finished": sum(1 for row in vals if row.get("finish_reason") == "length"),
        "apply_check_failure_categories": dict(Counter(str(row.get("patch_failure_category")) for row in vals if row.get("patch_failure_category"))),
        "final_failure_categories": dict(Counter(str(row.get("final_failure_category")) for row in vals if row.get("final_failure_category"))),
        "non_apply_failure_categories": dict(
            Counter(str(row.get("patch_failure_category")) for row in vals if row.get("candidate_patch_applies") is False and row.get("patch_failure_category"))
        ),
        "edit_formats": dict(Counter(str(row.get("edit_format")) for row in vals if row.get("edit_format"))),
        "patch_transports": dict(Counter(str(row.get("patch_transport")) for row in vals if row.get("patch_transport"))),
        "context_modes": dict(Counter(str(row.get("context_mode")) for row in vals if row.get("context_mode"))),
        "state_contracts": dict(Counter(str(row.get("state_contract")) for row in vals if row.get("state_contract"))),
        "state_failure_reasons": dict(state_failure_counter),
        "repair_counts": dict(Counter(str(row.get("repair_count", 0)) for row in vals)),
        "created_file_rows": sum(1 for row in vals if row.get("created_files")),
        "deleted_file_rows": sum(1 for row in vals if row.get("deleted_files")),
        "failure_steps": dict(Counter(str(row.get("failure_step")) for row in vals if row.get("failure_step"))),
        "by_method": by_method,
        "by_task": by_task,
    }
    write_json(run_dir / "SUMMARY.json", summary)
    lines = [
        "# RoadmapBench DeepSeek 5-task 6-prompt-variant Summary",
        "",
        f"Updated: {summary['updated_utc']}",
        "",
        f"- Rows: {summary['result_rows']}",
        f"- Generation ok: {summary['generation_ok']}",
        f"- Extract ok: {summary['extract_ok']}",
        f"- Docker scored: {summary['docker_scored']}",
        f"- Patch apply-check ok: {summary['patch_apply_check_ok']}",
        f"- Patch apply-check failed: {summary['patch_apply_check_failed']}",
        f"- Candidate applies: {summary['candidate_applies']}",
        f"- Test passed: {summary['test_passed']}",
        f"- Answer success: {summary['answer_success']}",
        f"- State JSON valid: {summary['state_json_valid']}",
        f"- Edit JSON valid: {summary['edit_json_valid']}",
        f"- Deterministic edit apply success: {summary['deterministic_edit_apply_success']}",
        f"- Deterministic patch generated: {summary['deterministic_patch_generated']}",
        f"- RoadmapBench state_contract_valid: {summary['state_contract_valid']}",
        f"- RoadmapBench action_governance_success: {summary['action_governance_success']}",
        f"- Legacy state_governance_success compat field: {summary['state_governance_success']}",
        f"- Reliable composite success: {summary['reliable_composite_success']}",
        f"- Answer only: {summary['answer_only']}",
        f"- Governance only: {summary['governance_only']}",
        f"- Neither answer nor governance: {summary['neither_answer_nor_governance']}",
        f"- Finish reason length: {summary['length_finished']}",
        f"- Edit formats: {summary['edit_formats']}",
        f"- Patch transports: {summary['patch_transports']}",
        f"- Context modes: {summary['context_modes']}",
        f"- State contracts: {summary['state_contracts']}",
        f"- State failure reasons: {summary['state_failure_reasons']}",
        f"- Repair counts: {summary['repair_counts']}",
        f"- Rows creating files: {summary['created_file_rows']}",
        f"- Rows deleting files: {summary['deleted_file_rows']}",
        f"- Apply-check failure categories: {summary['apply_check_failure_categories']}",
        f"- Final failure categories: {summary['final_failure_categories']}",
        f"- Non-applying patch categories: {summary['non_apply_failure_categories']}",
        "",
        "## By Prompt Variant",
        "",
        "| Prompt variant | Rows | Apply-check ok | Applies | Answer | State JSON | Edit JSON | State contract | Action gov | Reliable | Avg reward |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method, item in by_method.items():
        method_items = [row for row in vals if row["method"] == method]
        patch_ok = sum(1 for row in method_items if row.get("patch_apply_check_ok"))
        lines.append(
            f"| `{method}` | {item['rows']} | {patch_ok} | {item['candidate_applies']} | {item['answer_success']} | "
            f"{item['state_json_valid']} | {item['edit_json_valid']} | {item['state_contract_valid']} | {item['action_governance_success']} | {item['reliable_composite_success']} | {item['avg_reward']} |"
        )
    lines.extend(["", "## By Task", "", "| Task | Rows | Apply-check ok | Applies | Answer | State JSON | Edit JSON | State contract | Action gov | Reliable | Avg reward |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for task, item in by_task.items():
        lines.append(
            f"| `{task}` | {item['rows']} | {item['patch_apply_check_ok']} | {item['candidate_applies']} | {item['answer_success']} | "
            f"{item['state_json_valid']} | {item['edit_json_valid']} | {item['state_contract_valid']} | {item['action_governance_success']} | {item['reliable_composite_success']} | {item['avg_reward']} |"
        )
    (run_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", default=f"roadmapbench_deepseek_5task_6method_b600_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    parser.add_argument("--tasks", nargs="*", default=DEFAULT_TASKS)
    parser.add_argument("--methods", nargs="*", default=METHODS)
    parser.add_argument("--budget", type=int, default=600)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--provider", choices=["auto", "deepseek", "openrouter", "dashscope"], default="auto")
    parser.add_argument("--edit-format", choices=["unified_diff", "whole_file_json", "search_replace_json", "file_ops_json"], default="unified_diff")
    parser.add_argument("--context-mode", choices=["full", "targeted"], default="full")
    parser.add_argument("--state-contract", choices=["none", "answer_state"], default="none")
    parser.add_argument("--patch-transport", choices=["unified_diff", "edit_json"], default="unified_diff")
    parser.add_argument("--whole-file-max-files", type=int, default=3)
    parser.add_argument("--search-replace-max-edits", type=int, default=6)
    parser.add_argument("--file-op-max-files", type=int, default=8)
    parser.add_argument("--repair-attempts", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-context-chars", type=int, default=140000)
    parser.add_argument("--timeout-seconds", type=float, default=300)
    parser.add_argument("--api-attempts", type=int, default=3)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--force-score", action="store_true")
    parser.add_argument("--retry-api-failed-only", action="store_true")
    parser.add_argument("--skip-docker-on-invalid-patch", action="store_true")
    args = parser.parse_args()

    unknown_methods = sorted(set(args.methods) - set(METHODS))
    if unknown_methods:
        raise SystemExit(f"unknown methods: {unknown_methods}; valid methods: {METHODS}")
    if args.repair_attempts < 0:
        raise SystemExit("--repair-attempts must be >= 0")
    load_env_file(args.env_file)
    provider_info = resolve_provider(args.provider, args.model)
    provider, url, api_key_env, resolved_model = provider_info
    run_dir = RUNS_ROOT / args.run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    ensure_tmp_tasks(args.tasks)
    plan_path = run_dir / "RUN_PLAN.json"
    if plan_path.exists():
        rows = read_json(plan_path)["rows"]
    else:
        rows = build_plan(
            run_dir,
            args.tasks,
            args.methods,
            args.budget,
            args.max_context_chars,
            args.edit_format,
            args.whole_file_max_files,
            args.search_replace_max_edits,
            args.file_op_max_files,
            args.context_mode,
            args.state_contract,
            args.patch_transport,
        )
    run_config = {
        "created_utc": utc_now(),
        "run_name": args.run_name,
        "argv": sys.argv,
        "tasks": args.tasks,
        "tasks_root": str(TASKS_ROOT),
        "tmp_task_root": str(TMP_TASK_ROOT),
        "methods": args.methods,
        "planned_rows": len(rows),
        "budget": args.budget,
        "jobs": args.jobs,
        "provider": provider,
        "api_key_env": api_key_env,
        "model": resolved_model,
        "route_resolution": route_resolution_metadata(provider, url, api_key_env, resolved_model),
        "edit_format": args.edit_format,
        "patch_transport": args.patch_transport,
        "context_mode": args.context_mode,
        "state_contract": args.state_contract,
        "whole_file_max_files": args.whole_file_max_files,
        "search_replace_max_edits": args.search_replace_max_edits,
        "file_op_max_files": args.file_op_max_files,
        "repair_attempts": args.repair_attempts,
        "max_tokens": args.max_tokens,
        "max_context_chars": args.max_context_chars,
        "timeout_seconds": args.timeout_seconds,
        "api_attempts": args.api_attempts,
        "api_request_surface": api_request_surface_for_config(provider, resolved_model, args.max_tokens),
        "skip_docker_on_invalid_patch": args.skip_docker_on_invalid_patch,
        "env_key_present": bool(os.getenv(api_key_env)),
        "env_file_used": bool(args.env_file),
        "env_file_path_redacted": bool(args.env_file),
    }
    write_json(run_dir / "RUN_CONFIG.json", run_config)
    write_json(run_dir / "ROUTE_RESOLUTION.json", run_config["route_resolution"])
    append_jsonl(run_dir / "RUN_INVOCATIONS.jsonl", run_config)
    result_path = run_dir / "RESULTS.jsonl"
    latest_before_generation = {}
    if result_path.exists():
        for line in result_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                latest_before_generation[row["run_id"]] = row
    generation_rows = rows
    if args.retry_api_failed_only:
        generation_rows = [
            row
            for row in rows
            if latest_before_generation.get(row["run_id"], {}).get("failure_step") == "api_failed"
        ]
        print(json.dumps({"stage": "retry_filter", "rows": len(generation_rows)}, ensure_ascii=False), flush=True)
    if not args.score_only:
        if not os.getenv(api_key_env):
            raise SystemExit(f"{api_key_env} is not set; pass --env-file or export it before running")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
            futures = [executor.submit(generate_one, run_dir, row, args, provider_info) for row in generation_rows]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                append_jsonl(result_path, result)
                print(
                    json.dumps(
                        {
                            "stage": "generated",
                            "run_id": result["run_id"],
                            "ok": result.get("candidate_validate_ok"),
                            "finish_reason": result.get("finish_reason"),
                            "failure": result.get("failure_step"),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    if not args.generate_only:
        latest = {}
        if result_path.exists():
            for line in result_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    latest[row["run_id"]] = row
        for row in rows:
            gen = latest.get(row["run_id"])
            if not gen or not gen.get("candidate_validate_ok"):
                continue
            if gen.get("docker_scored") and not args.force_score:
                continue
            eval_result = evaluate_patch(run_dir, row, gen, args.skip_docker_on_invalid_patch)
            merged = {**gen, **eval_result, "timestamp_utc": utc_now()}
            append_jsonl(result_path, merged)
            print(
                json.dumps(
                    {
                        "stage": "scored",
                        "run_id": row["run_id"],
                        "reward": eval_result.get("reward"),
                        "passed": eval_result.get("test_passed"),
                        "applies": eval_result.get("candidate_patch_applies"),
                        "patch_check": eval_result.get("patch_apply_check_ok"),
                        "patch_category": eval_result.get("patch_failure_category"),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    write_summary(run_dir)
    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
