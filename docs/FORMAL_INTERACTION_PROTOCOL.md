# Formal Model Interaction Protocol

## Visible input

Each request is assembled from the roadmap instruction, repository file tree,
bounded visible source context, one fixed prompt-condition description, and the
output contract. Gold patches, solution diffs, protected tests, hidden verifier
content, expected fixes, and scorer-only material are not model-visible. The
released full-transcript audits are in `prompt_audits/`.

## Final answer-state surface

The model must emit exactly two tagged JSON blocks and no surrounding prose:

```text
<STATE_JSON>
{"OUT":["..."],"ALW":["relative/source/path"],"NO":[],"B":[],"G":"...","CK":["..."]}
</STATE_JSON>
<EDIT_JSON>
{"ops":[{"op":"replace","path":"relative/source/file","old":"exact old text","new":"replacement"}]}
</EDIT_JSON>
```

`OUT` or `CK` must be non-empty. `ALW` must cover every touched source path.
State fields may describe only model-visible source facts and action boundaries.
They may not contain edit operations or protected evaluation information.

## Strict edit semantics

Supported claim-bearing operations are `create`, `replace`, and `delete`.
`replace.old` must be non-empty, differ from `new`, and match exactly once in the
current sequential working copy. `create` requires a non-existing source-like
path and complete non-empty content. `delete` requires an existing allowed source
file. Any failed operation invalidates the entire row before Docker verification.

## Single-shot V3

V3 requests state and edits in one call. No edit repair attempt is used in the
frozen claim-bearing surface.

## Staged V4

Stage 1 returns exactly:

```json
{
  "existing_files": ["relative/existing/source"],
  "planned_new_files": ["relative/new/source"],
  "edit_targets": [{"path": "relative/source", "op": "replace", "reason": "..."}]
}
```

Stage 2 receives the validated plan and may edit only those targets. Creates must
refer to `planned_new_files`; replacements and deletions must refer to
`existing_files`. At most one bounded edit repair attempt may follow machine-
generated failure feedback. The feedback policy is checked as part of the full-
transcript prompt audit.

## Outcome functions

- `state_contract_valid`: the tagged state is complete, parseable, source-bearing,
  and internally consistent.
- `action_governance_success`: a valid state accompanies a non-empty, allowed,
  deterministically applicable action.
- `answer_success`: the frozen local verifier passes.
- `reliable_composite_success`: action governance and answer success occur on the
  same row.

RoadmapBench action governance is an external-layer analogue of usable governed
action state. It is not the same scorer or construct as PCG state governance.
