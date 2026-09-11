# Frozen Main Matrix Protocol V2 20260707

## Status

This is the active frozen main-matrix protocol for the Paper 2 RoadmapBench/SWE-EVO-style evaluation-methodology study.

Freeze timestamp: 2026-07-07.

This protocol supersedes:

```text
Artifact_Chain/FROZEN_MAIN_MATRIX_PROTOCOL_20260707.md
```

Supersession reason: the earlier protocol used one repeat per task-arm-model cell. V2 freezes eight repeats per cell before claim-bearing execution. No claim-bearing API execution was performed under the superseded 120-row protocol.

No API execution is performed by this file. The dry-run, prompt visibility audit, E5/VCR preflight, and hash-manifest updates must exist before any claim-bearing API execution under this protocol.

## Purpose

The main matrix tests an evaluation-methodology claim, not a repair-method superiority claim.

The core question is:

> In real-code version-upgrade repair tasks, do strict transport, structured state, governed action surfaces, and end-to-end answer correctness remain empirically separable under a frozen, audit-locked protocol?

The matrix may support claims about:

- metric decomposition;
- prompt visibility hygiene;
- strict edit transport;
- governed action-surface observability;
- hard-task semantic repair limits;
- artifact-lineage discipline.

It must not be used to claim:

- official SWE-bench performance;
- PCG replication;
- PCG `state_governance_success`;
- general SWE capability;
- method superiority between V3 and V4;
- model superiority between DeepSeek Pro and DeepSeek Flash;
- hard-task repair success unless non-`tpl` reliable composite success appears under this exact frozen protocol.

## Frozen Matrix

The V2 main matrix is:

```text
30 tasks
x 2 arms: single_shot_v3, staged_v4
x 2 models: deepseek-v4-pro, deepseek-v4-flash
x 8 repeats per task-arm-model cell
= 960 planned rows
```

This is a DeepSeek-only main matrix. OpenRouter, Claude, GPT, Qwen, Kimi, GLM, and other models are not part of this frozen main matrix. Any later non-DeepSeek model probe must be defined in a separate addendum and must not be pooled silently into the V2 main matrix.

## Frozen Task Pool

Task root:

```text
roadmap_swe_evo_probe/data/roadmapbench_30_clean
```

Frozen tasks:

```text
dsl-2.1.0-roadmap
dsl-2.2.0-roadmap
dsl-2.3.0-roadmap
fal-1.3.0-roadmap
fal-2.0.0-roadmap
fal-4.1.0-roadmap
fbr-2.42.0-roadmap
fbr-2.43.0-roadmap
fbr-3.0.0-roadmap
fyn-2.1.0-roadmap
fyn-2.7.0-roadmap
glz-3.0.0-roadmap
glz-4.0.0-roadmap
ktx-0.10.0-roadmap
mko-3.0.0-roadmap
mko-4.0.0-roadmap
mko-4.1.0-roadmap
opt-2.0.0-roadmap
opt-3.0.0-roadmap
plr-1.0.0-roadmap
prm-5.0.0-roadmap
pyg-1.6.3-roadmap
rat-0.24.0-roadmap
spc-3.5.0-roadmap
tpl-3.0.0-roadmap
tpl-3.2.0-roadmap
tpl-3.3.0-roadmap
tpl-4.0.0-roadmap
tpl-5.0.0-roadmap
tpl-5.1.0-roadmap
```

The task pool spans 14 project families and multiple languages:

```text
Python: 8
C++: 8
Go: 6
Rust: 4
TypeScript: 4
```

Family counts:

```text
tpl=6, dsl=3, fal=3, fbr=3, mko=3, fyn=2, glz=2, opt=2,
ktx=1, plr=1, prm=1, pyg=1, rat=1, spc=1
```

No task may be added, removed, renamed, repaired, or replaced after the first API call under this protocol. If any task fails due to verifier, Docker, transport, or semantic repair behavior, the row remains in the main matrix and is classified by the frozen failure taxonomy.

Gold patches, `solution/changes.patch`, hidden/oracle tests, verifier-only material, scorer-only material, expected fixes, and post-hoc explanations must not enter prompts.

## Frozen Arms

### `single_shot_v3`

The V3 arm is a strict single-response answer-state repair contract:

- one model call per row;
- `answer_state` state contract;
- strict `edit_json` / `file_ops_json` transport;
- no repair attempt;
- deterministic edit application;
- Docker verifier only after strict deterministic edit application succeeds.

### `staged_v4`

The V4 arm is a staged answer-state repair contract:

- stage 1: file/target planning and governed state surface;
- stage 2: strict edit generation constrained by stage 1;
- at most one edit-repair attempt;
- `answer_state` state contract;
- strict `edit_json` / `file_ops_json` transport;
- deterministic edit application;
- Docker verifier only after strict deterministic edit application succeeds.

Frozen staged V4 profile:

```text
large_upgrade_v1_mko_contract_fix
```

The V4 label is a matched scaffold/protocol arm. It is not a mature autonomous agent method and must not be presented as method superiority.

## Frozen Prompt Variant

Only one prompt variant is included:

```text
loop_only
```

The earlier six labels remain historical prompt variants and are not part of this main matrix.

## Frozen Provider And Models

Provider:

```text
deepseek
```

Route:

```text
direct DeepSeek API
```

Forbidden route:

```text
OpenRouter
```

Models:

```text
deepseek-v4-pro
deepseek-v4-flash
```

Every row artifact must record provider metadata, resolved model id, and API key environment name. Rows using OpenRouter or any non-DeepSeek provider are out of protocol.

Reasoning/thinking mode:

```text
disabled for the claim-bearing main matrix unless the direct DeepSeek API records it as an unavoidable provider-side default.
```

API decoding parameters not sent by this protocol:

```text
top_p = not_sent_by_protocol / provider_default
top_k = not_sent_by_protocol / provider_default
repetition_penalty = not_sent_by_protocol / provider_default
frequency_penalty = not_sent_by_protocol / provider_default
presence_penalty = not_sent_by_protocol / provider_default
seed = not_sent_by_protocol / provider_default
stop = not_sent_by_protocol / provider_default
logit_bias = not_sent_by_protocol / provider_default
reasoning_effort = not_sent_by_protocol / thinking_disabled_controls_reasoning
```

These omissions are documented in:

```text
Artifact_Chain/DEEPSEEK_GLM_API_PARAMETER_SURFACE_ADDENDUM_20260708.md
```

They are not grounds for rerunning DeepSeek. Adding them after completion would define a new protocol rather than repair this one.

No web search, browser, external tools, or repository browsing tools are available to the model.

## Frozen Runner Parameters

Runner:

```text
roadmap_swe_evo_probe/scripts/roadmapbench_tier1_matched_v3_v4_runner.py
```

Frozen task-root environment variable:

```text
ROADMAPBENCH_TASKS_ROOT=roadmap_swe_evo_probe/data/roadmapbench_30_clean
```

Frozen execution parameters:

```text
--provider deepseek
--arms single_shot_v3 staged_v4
--methods loop_only
--reps 8
--budget 600
--jobs 4
--context-mode targeted
--max-context-chars 320000
--max-tokens 32768
--stage1-max-tokens 8192
--timeout-seconds 600
--api-attempts 5
--whole-file-max-files 3
--search-replace-max-edits 6
--file-op-max-files 8
--v3-repair-attempts 0
--v4-repair-attempts 1
--staged-v4-profile large_upgrade_v1_mko_contract_fix
--skip-docker-on-invalid-patch
--resume
```

The only permitted difference between the two core execution runs is:

```text
--model deepseek-v4-pro
--model deepseek-v4-flash
```

## Frozen Output Token Budget

The main matrix freezes:

```text
--max-tokens 32768
--stage1-max-tokens 8192
```

Rationale: `32768` is selected as a conservative common output budget for current and likely follow-up long-code models. Larger-output models may support higher ceilings, but the matrix fixes a common lower budget to avoid output-cap confounding. `stage1-max-tokens=8192` applies only to staged V4 planning and is frozen to reduce stage-1 length truncation on long-upgrade tasks while keeping planning bounded.

## Strict Edit Transport

Claim-bearing rows must use strict `edit_json` / `file_ops_json`.

Forbidden:

- fuzzy matching;
- approximate matching;
- silent skipped operations;
- empty `old` anchors;
- no-op edit success;
- whole-file rewrite unless separately enabled in a diagnostic-only mode;
- path auto-fix beyond exact leading `./` normalization;
- whitespace normalization for matching;
- indentation normalization;
- tabs/spaces conversion;
- line-ending conversion unless separately declared in a diagnostic-only mode.

If multiple operations target the same file, they are applied sequentially to the working copy and the operation order is recorded.

If any operation fails, the row fails closed before Docker verification.

If a later operation fails after earlier operations applied, the row is `edit_apply_failed` and must not enter Docker verification.

If `EDIT_JSON` produces no actual source change:

```text
deterministic_edit_apply_success = false
deterministic_patch_generated = false
action_governance_success = false
```

## Finish Reason Policy

If `finish_reason=length` at any model stage:

```text
failure_step = finish_reason_length
answer_success = false
action_governance_success = false
reliable_composite_success = false
```

Truncated output must not be counted as partial success.

For staged V4, a stage-1 length truncation fails the row before stage 2. A stage-2 length truncation fails the row before deterministic edit application unless the required block is complete and parseable; even then it cannot receive answer or action-governance success unless the strict edit surface applies and reaches the verifier.

## Prompt Visibility Gate

Prompt visibility must be audited over the full transcript after dry-run and after execution, including:

- initial prompts;
- stage-1 prompts;
- stage-2 prompts;
- repair prompts;
- any feedback prompts.

Gate:

```text
failure_count = 0
feedback_leak_audit_failures = 0
missing_attempt_prompt_artifacts = 0
```

If the full-transcript prompt audit fails, the affected run is not eligible for main-table claims.

## Metrics

Reports must keep these metrics separate:

| Metric | Meaning |
| --- | --- |
| `generation_success` / `generation_ok` | A model response was produced. |
| `state_contract_valid` | RoadmapBench answer-state JSON is valid. Diagnostic only. |
| `patch_extracted` / `extract_ok` | Strict edit JSON was extracted. |
| `patch_apply_success` / `candidate_applies` | Deterministic source edit applied successfully. |
| `docker_verifier_entered` / `docker_scored` | Docker verifier was reached. |
| `answer_success` / `test_passed` | Local RoadmapBench verifier passed. |
| `action_governance_success` | Valid state plus strict executable edit/action surface. Not PCG state governance. |
| `reliable_composite_success` | `answer_success AND action_governance_success`. |
| `finish_reason_length_count` | Count of length-truncated model outputs. |

Boundary language:

> RoadmapBench `action_governance_success` is an external-layer analogue of usable governed action state. It is not the same scorer or construct as PCG `state_governance_success`.

## Failure Taxonomy

Each row must receive one final failure category:

```text
generation_failed
finish_reason_length
state_contract_invalid
edit_json_invalid
edit_apply_failed
stage1_plan_failed
stage1_generation_failed
stage2_contract_failed
docker_not_entered
test_failed
test_passed
api_transport_failed
other_infra_failed
```

Task-level qualitative labels may be added after the fact, but they cannot change row-level metrics or inclusion:

```text
wrong_target_file
incomplete_api_migration
missing_new_file
wrong_interface_contract
compile_failure
test_assertion_failure
no_op_or_superficial_edit
length_truncation
other
```

## Pre-Execution Gates

Before executing either model run, these must pass:

```text
python3 -m py_compile roadmap_swe_evo_probe/scripts/roadmapbench_tier1_matched_v3_v4_runner.py
python3 -m py_compile roadmap_swe_evo_probe/scripts/roadmapbench_prompt_visibility_audit.py
python3 -m py_compile roadmap_swe_evo_probe/scripts/test_answer_state_contract.py
python3 roadmap_swe_evo_probe/scripts/test_answer_state_contract.py
```

The 30-task clean pool must remain intact:

```text
Artifact_Chain/ROADMAPBENCH_30_CLEAN_TASK_FILE_INTEGRITY_POST_GOLD_REPAIR_20260706.json
claim-bearing artifact ok: 30/30
repo hash failed count: 0/30
required files present: 30/30
```

Gold sanity must remain calibrated:

```text
roadmap_swe_evo_probe/runs/roadmapbench_solution_script_sanity_30task_clean_final2_calibrated_20260706/SUMMARY.json
all_rows_passed = true
all_rewards_stable_by_task = true
```

Dry-run plan must produce:

```text
planned_rows = 480 per model
planned_rows = 960 combined
result_rows = 0
API artifacts = 0 before execution
raw responses = 0 before execution
candidate patches = 0 before execution
prompt visibility failure_count = 0
feedback_leak_audit_failures = 0
missing_attempt_prompt_artifacts = 0
E5/VCR preflight row ledger rows = 960
E5/VCR preflight replay records = 960
```

## Dry-Run Commands

### DeepSeek Pro Dry-Run

```bash
ROADMAPBENCH_TASKS_ROOT=roadmap_swe_evo_probe/data/roadmapbench_30_clean \
python3 roadmap_swe_evo_probe/scripts/roadmapbench_tier1_matched_v3_v4_runner.py \
  --run-name roadmapbench_mainmatrix_v2_deepseek_pro_30task_v3_v4_8rep_960_20260707_dryrun \
  --provider deepseek \
  --model deepseek-v4-pro \
  --tasks dsl-2.1.0-roadmap dsl-2.2.0-roadmap dsl-2.3.0-roadmap fal-1.3.0-roadmap fal-2.0.0-roadmap fal-4.1.0-roadmap fbr-2.42.0-roadmap fbr-2.43.0-roadmap fbr-3.0.0-roadmap fyn-2.1.0-roadmap fyn-2.7.0-roadmap glz-3.0.0-roadmap glz-4.0.0-roadmap ktx-0.10.0-roadmap mko-3.0.0-roadmap mko-4.0.0-roadmap mko-4.1.0-roadmap opt-2.0.0-roadmap opt-3.0.0-roadmap plr-1.0.0-roadmap prm-5.0.0-roadmap pyg-1.6.3-roadmap rat-0.24.0-roadmap spc-3.5.0-roadmap tpl-3.0.0-roadmap tpl-3.2.0-roadmap tpl-3.3.0-roadmap tpl-4.0.0-roadmap tpl-5.0.0-roadmap tpl-5.1.0-roadmap \
  --arms single_shot_v3 staged_v4 \
  --methods loop_only \
  --reps 8 \
  --budget 600 \
  --jobs 4 \
  --context-mode targeted \
  --max-context-chars 320000 \
  --max-tokens 32768 \
  --stage1-max-tokens 8192 \
  --timeout-seconds 600 \
  --api-attempts 5 \
  --whole-file-max-files 3 \
  --search-replace-max-edits 6 \
  --file-op-max-files 8 \
  --v3-repair-attempts 0 \
  --v4-repair-attempts 1 \
  --staged-v4-profile large_upgrade_v1_mko_contract_fix \
  --skip-docker-on-invalid-patch \
  --resume \
  --dry-run
```

### DeepSeek Flash Dry-Run

Use the same command with:

```text
--run-name roadmapbench_mainmatrix_v2_deepseek_flash_30task_v3_v4_8rep_960_20260707_dryrun
--model deepseek-v4-flash
```

## Execution Commands

Execution uses the dry-run commands above with `--dry-run` removed.

Execution must not begin until:

- the V2 dry-run plans exist;
- prompt visibility audits pass;
- the V2 E5/VCR preflight package exists;
- `SHA256SUMS.txt`, `HASH_MANIFEST.jsonl`, and `RUN_LINEAGE.md` are updated;
- the user explicitly confirms API execution.

## Post-Execution Required Outputs

Each model run must produce:

```text
RUN_CONFIG.json
RUN_PLAN.json
RUN_PLAN.jsonl
RUN_INVOCATIONS.jsonl
RESULTS.jsonl
SUMMARY.json
SUMMARY.md
prompt files
stage1 prompts for staged_v4
raw responses
API request metadata
API response metadata
parsed state/edit artifacts
candidate patch artifacts
deterministic edit diagnostics
Docker verifier stdout/stderr
```

The combined report must include:

```text
PER_MODEL_SUMMARY.csv
PER_MODEL_ARM_SUMMARY.csv
PER_TASK_MODEL_ARM_SUMMARY.csv
TASK_MODEL_ARM_RUN_MATRIX.csv
FAILURE_TAXONOMY.csv
```

Every derived table must be reproducible from `RESULTS.jsonl`.

## Main-Table Gate

Write a main-table-ready decision only if:

```text
planned_rows = 960
result_rows = 960
provider = direct DeepSeek for all rows
OpenRouter rows = 0
prompt visibility full-transcript failure_count = 0
feedback_leak_audit_failures = 0
missing_attempt_prompt_artifacts = 0
all rows have raw response or explicit API failure artifact
all rows have final_failure_category
all run configs and run plans are hash-recorded
post-run E5/VCR row ledger rows = 960
post-run E5/VCR replay records = 960
```

If these conditions pass, the result may be used for evaluation-methodology claims even if hard-task `answer_success` remains zero.

If no non-`tpl` row reaches `reliable_composite_success`, the interpretation must be:

> The harness is transport/action-observability ready under this matrix, but hard-task semantic repair remains unsolved for these models and tasks.

This must not be called a system failure.

## No Post-Hoc Tuning Rule

After the first API call under this protocol:

- do not change task list;
- do not change arm definitions;
- do not change prompt template;
- do not change `staged_v4_profile`;
- do not change max files, max tokens, repair attempts, or context budget;
- do not change failure semantics;
- do not delete rows;
- do not exclude bad rows from the main table;
- do not repair task artifacts;
- do not replace Docker images;
- do not tune based on any task's observed model output.

Any later change must create a new protocol addendum before new API calls. Changed runs must be labeled as diagnostic or as a separately frozen matrix, not merged silently into this matrix.

## Interpretation Boundary

This protocol reduces post-hoc design risk. It does not prove the phenomenon could not be engineered artificially.

It provides a claim-bearing boundary:

- tasks are fixed before main execution;
- models are fixed before main execution;
- arms and metrics are fixed before main execution;
- prompts and strict edit semantics are fixed before main execution;
- provider/model routes are fixed before main execution;
- replication depth is fixed before main execution;
- all rows count;
- all failures remain visible;
- prompt visibility is audited;
- artifact lineage is hash-recorded.

If these conditions are followed, the resulting matrix is defensible as a frozen, audit-locked evaluation-methodology experiment rather than a post-hoc curated diagnostic.
