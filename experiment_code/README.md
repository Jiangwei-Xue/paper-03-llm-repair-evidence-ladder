# Experiment Code Snapshot

This directory contains the retained Paper A experiment harness available at
public-package preparation time:

- `scripts/roadmapbench_deepseek_6method_runner.py`: the live RoadmapBench runner,
  provider adapters, answer-state parsing, strict `edit_json` application, repair
  attempts, artifact writing, and Docker verification path;
- `scripts/roadmapbench_tier1_matched_v3_v4_runner.py`: matched single-shot V3 and
  staged V4 orchestration;
- `scripts/roadmapbench_prompt_visibility_audit.py`: first-prompt and full-transcript
  visibility checks;
- `tests/test_answer_state_contract.py`: local state/edit contract tests; and
- `verify_snapshot.py`: no-API syntax and contract-test entry point.

The files are useful for inspecting the protocol and constructing future reruns.
They are not claimed to be byte-identical historical runner snapshots for every
July provider call. Historical run semantics are fixed by each bundled
`RUN_CONFIG.json`, `RUN_PLAN.json`, row artifact, and E5/VCR record. This explicit
boundary avoids overstating code provenance where an exact per-call source-tree
snapshot was not retained.

The full upstream SWE-EVO/SWE-bench codebase, benchmark repositories, image layers,
and protected verifier material remain external dependencies. Development-only
controller-study code is outside Paper A's estimator and is not included here.

Static validation:

```sh
python3 experiment_code/verify_snapshot.py
```

No API call is made by these checks.

## Inspect a historical rerun surface

This command renders a dry-run command from a retained configuration. It does not
contact a model provider or Docker:

```sh
python3 experiment_code/render_rerun_command.py \
  evidence/02_CLAIM_BEARING_RUN_LEDGERS/roadmapbench_glm52_bailian_30task_v3_v4_8rep_480_20260708/RUN_CONFIG.json \
  --tasks-root /path/to/roadmapbench/tasks
```

Passing `--execute` only changes the printed command; it still does not execute
it. A researcher must review that command, provide benchmark assets and the
provider credential named by the retained config, and then run it explicitly.

The DeepSeek historical configs do not retain every field later added to the
runner. The renderer omits unavailable fields instead of inventing values. The
historical saved outputs remain the primary replay surface; new calls are
prospective reruns.
