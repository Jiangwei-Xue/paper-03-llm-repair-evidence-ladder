#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "roadmapbench_deepseek_6method_runner.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("roadmap_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_task_dir(text: str = "x = 1\nunchanged = True\n") -> Path:
    root = Path(tempfile.mkdtemp(prefix="answer_state_contract_"))
    repo = root / "task" / "environment" / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "main.py").write_text(text, encoding="utf-8")
    (repo / "tests" / "test_main.py").write_text("assert True\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return root / "task"


def clean_state(**overrides):
    state = {
        "OUT": ["src/main.py active source fact"],
        "ALW": ["src/main.py"],
        "NO": [],
        "B": [],
        "G": "update source value",
        "CK": ["src/main.py is the touched source file"],
    }
    state.update(overrides)
    return state


def edit_json(path: str = "src/main.py", old: str = "x = 1\n", new: str = "x = 2\n"):
    return {"ops": [{"op": "replace", "path": path, "old": old, "new": new}]}


def raw_edit_output(state: dict, edit: object | None) -> str:
    state_text = json.dumps(state, ensure_ascii=False, indent=2)
    if edit is None:
        return f"<STATE_JSON>\n{state_text}\n</STATE_JSON>\n"
    edit_text = edit if isinstance(edit, str) else json.dumps(edit, ensure_ascii=False, indent=2)
    return f"<STATE_JSON>\n{state_text}\n</STATE_JSON>\n\n<EDIT_JSON>\n{edit_text}\n</EDIT_JSON>\n"


def extract_and_score(runner, task_dir: Path, raw: str):
    patch, diag, payload = runner.extract_candidate(raw, task_dir, "file_ops_json", 3, 6, 8, "answer_state", "edit_json")
    candidate_files = runner.validate_patch(patch)["files"] if patch else []
    local_ok = False
    if patch:
        repo = task_dir / "environment" / "repo"
        patch_path = task_dir.parent / "candidate.patch"
        patch_path.write_text(patch, encoding="utf-8")
        local_ok = subprocess.run(["git", "-C", str(repo), "apply", "--check", str(patch_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).returncode == 0
    state = runner.score_state_governance(
        payload,
        "answer_state",
        candidate_files,
        raw,
        patch or "",
        transport_valid=bool(patch is not None),
        patch_applies=local_ok,
    )
    return patch, diag, payload, state, local_ok


def assert_true(condition: bool, message: object) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    runner = load_runner()

    # valid STATE_JSON + valid EDIT_JSON replace op
    task_dir = make_task_dir()
    try:
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit_json()))
        assert_true(patch is not None and diag["ok"], diag)
        assert_true(diag["edit_json_valid"] and diag["deterministic_edit_apply_success"] and diag["deterministic_patch_generated"], diag)
        statuses = diag["edit_validation"]["op_statuses"]
        assert_true(len(statuses) == 1 and statuses[0]["status"] == "applied", statuses)
        assert_true(not diag["edit_validation"]["line_ending_normalization"], diag)
        assert_true(local_ok, "deterministic patch should apply")
        assert_true(state["state_contract_valid"] and state["action_governance_success"], state)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # leading ./ is the only allowed path normalization
    task_dir = make_task_dir()
    try:
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit_json(path="./src/main.py")))
        statuses = diag["edit_validation"]["op_statuses"]
        assert_true(patch is not None and local_ok, diag)
        assert_true(statuses[0]["path"] == "src/main.py" and statuses[0]["path_normalized_leading_dot_slash"], statuses)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # valid state but missing EDIT_JSON
    task_dir = make_task_dir()
    try:
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), None))
        assert_true(patch is None and diag["failure_reason"] == "edit_json_missing", diag)
        assert_true(state["state_contract_valid"] and not state["action_governance_success"], state)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # invalid EDIT_JSON
    task_dir = make_task_dir()
    try:
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), '{"ops": [}'))
        assert_true(patch is None and diag["failure_reason"] == "edit_json_invalid", diag)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # empty old anchor is invalid
    task_dir = make_task_dir()
    try:
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit_json(old="")))
        assert_true(patch is None and diag["failure_reason"] == "edit_json_invalid", diag)
        assert_true(not diag["edit_json_valid"], diag)
        assert_true(diag["edit_validation"]["op_statuses"][0]["detail"] == "old_text_empty", diag)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # empty ops is not a valid edit contract
    task_dir = make_task_dir()
    try:
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), {"ops": []}))
        assert_true(patch is None and diag["failure_reason"] == "edit_ops_empty", diag)
        assert_true(not diag["edit_json_valid"], diag)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # no-op edit fails closed and is not counted as deterministic edit apply success
    task_dir = make_task_dir()
    try:
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit_json(new="x = 1\n")))
        assert_true(patch is None and diag["failure_reason"] == "deterministic_patch_generation_failed", diag)
        assert_true(not diag["deterministic_edit_apply_success"] and not diag["deterministic_patch_generated"], diag)
        assert_true(diag["edit_validation"]["op_statuses"][0]["detail"] == "op_no_actual_source_change", diag)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # whole-file rewrite is not allowed in V3 claim-bearing edit_json
    task_dir = make_task_dir("x = 1\n")
    try:
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit_json(old="x = 1\n", new="x = 2\n")))
        assert_true(patch is None and diag["failure_reason"] == "edit_json_invalid", diag)
        assert_true(diag["edit_validation"]["op_statuses"][0]["detail"] == "whole_file_rewrite_not_allowed", diag)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # replace op with old text not found
    task_dir = make_task_dir()
    try:
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit_json(old="missing\n")))
        assert_true(patch is None and diag["failure_reason"] == "edit_anchor_not_found", diag)
        assert_true(state["state_contract_valid"] and not state["action_governance_success"], state)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # replace op with old text found multiple times
    task_dir = make_task_dir("x = 1\nx = 1\n")
    try:
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit_json()))
        assert_true(patch is None and diag["failure_reason"] == "edit_anchor_ambiguous", diag)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # multiple ops targeting the same file apply sequentially and record order
    task_dir = make_task_dir("x = 1\ny = 1\n")
    try:
        edit = {"ops": [
            {"op": "replace", "path": "src/main.py", "old": "x = 1\n", "new": "x = 2\n"},
            {"op": "replace", "path": "src/main.py", "old": "y = 1\n", "new": "y = 2\n"},
        ]}
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit))
        statuses = diag["edit_validation"]["op_statuses"]
        assert_true(patch is not None and local_ok, diag)
        assert_true([s["status"] for s in statuses] == ["applied", "applied"], statuses)
        assert_true([s["working_copy_order"] for s in statuses] == [0, 1], statuses)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # if a later op fails after an earlier op applied, the row fails closed
    task_dir = make_task_dir("x = 1\ny = 1\n")
    try:
        edit = {"ops": [
            {"op": "replace", "path": "src/main.py", "old": "x = 1\n", "new": "x = 2\n"},
            {"op": "replace", "path": "src/main.py", "old": "missing\n", "new": "z = 3\n"},
        ]}
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit))
        statuses = diag["edit_validation"]["op_statuses"]
        assert_true(patch is None and diag["failure_reason"] == "edit_apply_failed", diag)
        assert_true(diag["edit_validation"]["underlying_failure_reason"] == "edit_anchor_not_found", diag)
        assert_true([s["status"] for s in statuses] == ["applied", "failed"], statuses)
        assert_true(state["state_contract_valid"] and not state["action_governance_success"], state)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # CRLF source must not be matched by an LF-normalized old anchor
    task_dir = make_task_dir("x = 1\r\ny = 1\r\n")
    try:
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit_json(old="x = 1\n")))
        assert_true(patch is None and diag["failure_reason"] == "edit_anchor_not_found", diag)
        patch, diag, payload, state, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit_json(old="x = 1\r\n", new="x = 2\r\n")))
        assert_true(patch is not None and local_ok, diag)
        assert_true(diag["edit_validation"]["original_line_endings"]["src/main.py"] == "CRLF", diag)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # edit path touches tests/
    task_dir = make_task_dir()
    try:
        state = clean_state(ALW=["tests/test_main.py"], CK=["tests/test_main.py touched"])
        edit = edit_json(path="tests/test_main.py", old="assert True\n", new="assert False\n")
        patch, diag, payload, scored, local_ok = extract_and_score(runner, task_dir, raw_edit_output(state, edit))
        assert_true(patch is None and diag["failure_reason"] == "edit_path_disallowed", diag)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # state ALW does not cover touched file
    task_dir = make_task_dir()
    try:
        state = clean_state(ALW=["src/other.py"], CK=["checked implementation"])
        patch, diag, payload, scored, local_ok = extract_and_score(runner, task_dir, raw_edit_output(state, edit_json()))
        assert_true(patch is not None and local_ok, diag)
        assert_true(scored["state_contract_valid"] and not scored["action_governance_success"], scored)
        assert_true("alw_or_ck_does_not_cover_patch_files" in scored["state_failure_reasons"], scored)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # state includes touched file only in NO/B
    task_dir = make_task_dir()
    try:
        state = clean_state(NO=["src/main.py"])
        patch, diag, payload, scored, local_ok = extract_and_score(runner, task_dir, raw_edit_output(state, edit_json()))
        assert_true(patch is not None and local_ok, diag)
        assert_true(scored["state_contract_valid"] and not scored["action_governance_success"], scored)
        assert_true("patched_file_listed_in_NO_or_B" in scored["state_failure_reasons"], scored)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # deterministic edit applies but tests fail: state_contract_valid=1, action_governance_success=1, answer_success=0
    task_dir = make_task_dir()
    try:
        patch, diag, payload, scored, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit_json()))
        outcome = runner.add_answer_state_outcomes({"test_passed": False}, scored)
        assert_true(scored["state_contract_valid"] and scored["action_governance_success"], scored)
        assert_true(not outcome["answer_success"] and not outcome["reliable_composite_success"], outcome)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # deterministic edit cannot apply: state_contract_valid may be 1, action_governance_success=0
    task_dir = make_task_dir()
    try:
        patch, diag, payload, scored, local_ok = extract_and_score(runner, task_dir, raw_edit_output(clean_state(), edit_json(old="missing\n")))
        assert_true(patch is None and diag["failure_reason"] == "edit_anchor_not_found", diag)
        assert_true(scored["state_contract_valid"] and not scored["action_governance_success"], scored)
    finally:
        shutil.rmtree(task_dir.parent, ignore_errors=True)

    # finish_reason=length fails closed for action/answer/reliable outcomes
    forced = runner.fail_closed_for_finish_reason_length(
        {
            "state_contract": "answer_state",
            "state_json_valid": True,
            "state_contract_valid": True,
            "action_governance_success": True,
            "state_governance_success": True,
            "state_failure_reasons": [],
        }
    )
    assert_true(forced["state_contract_valid"], forced)
    assert_true(not forced["action_governance_success"], forced)
    assert_true(not forced["state_governance_success"], forced)
    assert_true(not forced["answer_success"], forced)
    assert_true(not forced["reliable_composite_success"], forced)
    assert_true("finish_reason_length" in forced["state_failure_reasons"], forced)

    print("answer_state_contract_tests=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
