# Prompt Visibility Audits

This directory contains retained executed audit reports for all five public run
strata: two DeepSeek routes on the first 30-task pool, two DeepSeek routes on the
extension pool, and one GLM-5.2 hosted boundary stratum.

The audits inspect model-visible prompts, including staged and repair-attempt
transcripts where present. They check that gold patches, solution diffs,
protected tests, hidden verifier material, expected fixes, and scorer-only
content do not enter the prompt surface.

The executable auditor is
`experiment_code/scripts/roadmapbench_prompt_visibility_audit.py`. Historical
reports are evidence from retained run artifacts; auditing new transcripts
creates a new result.
