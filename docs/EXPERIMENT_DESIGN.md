# Experiment Design

## Research objective

The study asks what common repository-level repair statistics actually measure.
It separates structured instruction compliance, deterministic edit delivery,
governed action, verifier engagement, partial progress, and verifier pass rather
than compressing all of them into one success label.

The central measurement boundary is:

```text
instruction compliance
!= deterministic edit application
!= governed source action
!= verifier entry
!= partial reward
!= verifier pass
!= absolute semantic correctness
```

## Evidence ladder

| Layer | Observable event | Supported interpretation | Unsupported interpretation |
| --- | --- | --- | --- |
| S | state contract valid | structured state satisfies its schema | the repair is executable or correct |
| E | deterministic edit apply | exact edit operations produce a source change | the change solves the issue |
| A | action governance success | a permitted, non-empty, executable source action exists | the verifier will pass |
| D | Docker verifier entered | the candidate reached the execution environment | tests improved |
| R | partial reward | the frozen verifier observed partial progress | complete repair |
| P | verifier pass | the frozen local operational criterion passed | complete developer-intent equivalence |

The public canonical table focuses on harmonized action and verifier-pass
variables that can be reconstructed consistently across historical protocols.

## Design strata

### DeepSeek clean pool

- 30 admission-filtered RoadmapBench tasks.
- DeepSeek V4 Flash and DeepSeek V4 Pro routes.
- `single_shot_v3` and `staged_v4` protocol arms.
- `loop_only` prompt variant.
- Eight retained opportunities per task, model route, and arm.
- 960 claim-bearing rows.

### DeepSeek extension pool

- 30 additional seed-first, infrastructure-admitted RoadmapBench tasks.
- The same two DeepSeek routes, arms, prompt variant, and repetition depth.
- 960 claim-bearing rows.

### GLM supplementary stratum

- The original 30-task clean pool.
- GLM-5.2 through an Alibaba Bailian hosted API route.
- The same V3/V4 arms, prompt variant, and repetition depth.
- 480 claim-bearing rows.
- An external model-family boundary check, not a pooled leaderboard comparison.

## Fixed protocol controls

- answer-state contract;
- deterministic `edit_json` transport;
- no fuzzy or approximate matching;
- no silent operation skipping;
- no empty anchors;
- no implicit whole-file rewrite;
- fail-closed sequential operation application;
- no Docker verification after deterministic edit failure;
- full-transcript prompt-visibility auditing;
- explicit failure states for length truncation and missing artifacts;
- UTC timestamps;
- row-level E5 hashes and VCR replay links; and
- Docker/OCI identity recorded separately from mutable tags.

## Unit of analysis

Execution rows are repeated observations nested in tasks and task families. They
are useful for describing the repair pipeline, but they are not independent
repository samples. The analysis therefore reports row-level prevalence together
with fixed-cell `metric@k`, task-macro quantities, family-clustered uncertainty,
support concentration, and leave-one-family-out sensitivity.

## Human involvement

No human annotator or language-model judge assigned a claim-bearing row outcome.
The public labels are deterministic functions of saved parser states, edit
application records, container/verifier events, and frozen outcome rules. Human
activity was limited to pre-freeze engineering, protocol development, and
artifact auditing. Verifier pass remains an operational criterion, not a claim
of absolute semantic truth.

## Development and claim boundary

Pilot rows, harness repairs, Qwen contract diagnostics, model bridge checks, and
controller-study development runs are excluded from the 2,400-row estimator.
They may explain protocol history but do not enter Paper A's quantitative claims.
