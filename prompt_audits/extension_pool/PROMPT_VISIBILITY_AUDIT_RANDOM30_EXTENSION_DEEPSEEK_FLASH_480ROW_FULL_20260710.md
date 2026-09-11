# RoadmapBench Full-Transcript Prompt Visibility Audit

Run dir: `runs/roadmapbench_random30_extension_deepseek_flash_30task_v3_v4_8rep_20260710`

## Scope

This audit scans initial prompts and any saved repair/feedback attempt prompts. It is designed for staged or bounded-repair runs where later turns can introduce new leakage risk.

Boundary-only mentions such as `solution/changes.patch`, `tests/`, and `task.toml` are allowed when used as prohibitions. The audit flags forbidden file headers, forbidden diff paths, possible solution patch payloads, and verifier/test feedback payloads in repair-turn failure summaries.

## Counts

- prompt_files_scanned: 1484
- stage1_plan_prompts_scanned: 480
- initial_prompts_scanned: 480
- attempt_prompts_scanned: 524
- missing_attempt_prompt_artifacts: 0
- failure_count: 0
- feedback_leak_audit_failures: 0

## Finding Categories

- none

## V4 Gate Use

For staged-agent V4, this audit should be a hard gate over the full transcript, not only the first prompt. A V4 run should require `failure_count=0`, `feedback_leak_audit_failures=0`, and no missing attempt prompt artifacts.
