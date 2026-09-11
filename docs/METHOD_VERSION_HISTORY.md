# Method Version History

## Purpose

This document separates protocol development from the claim-bearing estimator.
Only the frozen V3/V4 surfaces described below enter the 2,400-row Paper A
analysis. Earlier pilots informed transport and contract design but are not pooled
with the reported rows.

## Version sequence

| Version | Main output surface | Scientific role | Claim-bearing here? |
| --- | --- | --- | --- |
| V1 | model-written unified diff | diagnosed source-grounding and diff-transport failure | no |
| V2 | tagged answer-state plus unified diff | made state/answer decomposition observable while retaining brittle diff transport | no |
| V3 | tagged `STATE_JSON` plus strict `EDIT_JSON` | single-shot comparator with deterministic edit application | yes |
| V4 | Stage 1 plan followed by Stage 2 strict edit | staged comparator for governed-action observability | yes |

## Frozen V3 surface

`single_shot_v3` receives the visible task instruction and bounded repository
context in one model call. It must return one valid `STATE_JSON` block followed by
one valid `EDIT_JSON` block. Exact create, replace, and delete operations are
applied sequentially. Any invalid or non-applicable operation fails the row closed.

## Frozen V4 surface

`staged_v4` first requests a compact plan that separates `existing_files`,
`planned_new_files`, and `edit_targets`. A second call receives the visible plan
and source context and must return the same strict answer-state/edit surface as V3.
At most one bounded edit-repair attempt is permitted. Stage 2 edits must remain
inside the Stage 1 target set.

## Fixed prompt condition

The claim-bearing matrices use only the `loop_only` prompt variant. The historical
six-label prompt exploration is development evidence and is not interpreted as a
comparison of six implemented multi-turn methods. Freezing one prompt condition
prevents prompt-label variation from being mixed with the V3/V4 contrast.

## Transport invariants

- no fuzzy or approximate matching;
- no empty `old` anchors;
- no silent operation skipping;
- no path repair beyond removing one leading `./`;
- no implicit whole-file rewrite;
- sequential operation application to the current working copy;
- no Docker entry after deterministic edit failure; and
- `finish_reason=length` is a failed row, not partial success.

The executable implementation is in `experiment_code/`. The exact retained
configuration for each historical stratum is in
`evidence/02_CLAIM_BEARING_RUN_LEDGERS/*/RUN_CONFIG.json` and `RUN_PLAN.json`.
