# Experiment Harness and Live Runner Inventory

## Included implementation

| File | Role in the experiment |
|---|---|
| `experiment_code/scripts/roadmapbench_deepseek_6method_runner.py` | Live API runner, prompt construction, provider routing, state/edit parsing, deterministic edit application, artifact persistence, and Docker scoring |
| `experiment_code/scripts/roadmapbench_tier1_matched_v3_v4_runner.py` | Matched V3/V4 arm scheduler and staged execution wrapper |
| `experiment_code/scripts/roadmapbench_prompt_visibility_audit.py` | Prompt and repair-feedback visibility audit |
| `experiment_code/tests/test_answer_state_contract.py` | Strict answer-state and edit-operation contract tests |
| `experiment_code/render_rerun_command.py` | No-execution renderer for a prospective command from a retained run config |
| `experiment_code/verify_snapshot.py` | Offline syntax and contract-test verifier |

The run plans and configurations under
`evidence/02_CLAIM_BEARING_RUN_LEDGERS/` identify the task, arm, model/provider,
token, concurrency, retry, and execution settings retained for each historical
stratum. `docker/RUNTIME_CONTRACT.json` records the deterministic edit and verifier
execution surface. Together these artifacts explain how a row moved from prompt
construction to state/edit extraction, strict application, Docker entry, and
recorded outcome.

## What can be run from this package

`python3 experiment_code/verify_snapshot.py` compiles the included implementation
and runs the contract tests without network or API access. `python3 replay_all.py`
replays the released evidence and analysis. These are complete offline checks.

Fresh live execution additionally requires benchmark task repositories, support
files, protected verifier material, Docker image layers, and user-supplied provider
credentials. Those dependencies are identified but not redistributed. A new live
execution is a new evidence stratum and must not overwrite the historical rows.
`experiment_code/render_rerun_command.py` exposes retained settings without
making a provider or Docker call.

## Provenance boundary

The included code is the retained implementation snapshot available when this
package was prepared. It is suitable for protocol inspection and future rerun
construction. It is not asserted to be a byte-identical source-tree snapshot for
every historical provider request; row semantics are additionally fixed by the
bundled run plans, run configurations, artifacts, and E5/VCR records.
