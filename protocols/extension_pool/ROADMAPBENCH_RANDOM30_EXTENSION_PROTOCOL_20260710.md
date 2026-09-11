# RoadmapBench Random-30 Extension Protocol 20260710

Created UTC: 2026-07-10T00:00:00Z

## Purpose

This protocol defines a second 30-task RoadmapBench extension pool. It is written before any extension-pool pull or admission step. No model/API execution is allowed until the final extension pool is frozen.

The extension is framed as:

`seed-first RoadmapBench extension under infrastructure-constrained admission`

This protocol does not change the existing DeepSeek Main Matrix V2 or the existing 30-task clean pool.

## Candidate Universe

- Universe source:
  `roadmap_swe_evo_probe/data/roadmapbench_min/.cache/huggingface/trees/59184e779909300a5a0150b06b945d39da81a099.json`
- Universe interpretation:
  all task ids ending in `-roadmap` present in the RoadmapBench tree manifest
- Expected full universe count:
  `115`
- Exclusion source:
  `protocols/main_matrix/VARIABLE_FREEZE_SPEC_MAIN_MATRIX_V2_20260707.yaml`
- Excluded task count:
  `30`
- Expected remaining sampling universe:
  `85`

## Sampling Rule

- RNG implementation:
  `python3 random.Random(seed)`
- Seeded input order:
  remaining task ids sorted lexicographically before shuffle
- Output:
  full seeded priority list, not only the first 30
- Initial target:
  first 30 tasks in the seeded list
- Reserve queue:
  all later tasks in the same seeded list

## Replacement Rule

If a task fails pre-model infrastructure admission, it is excluded and replaced only by the next task in the seeded reserve queue.

Allowed exclusion reasons:

- pull failure after retry budget
- missing support files
- digest mismatch
- file-integrity failure
- Docker image unavailability
- gold/oracle sanity failure
- verifier non-viability

Disallowed exclusion reasons:

- model output quality
- semantic difficulty
- reward
- answer success

No manual reranking or hand-picked backfill is allowed.

## Source Policy

Source order is fixed:

1. `official direct no-proxy probe`
2. `docker.1ms.run`
3. `dockerproxy.net`

Rules:

- Docker daemon network pull is disabled for claim-bearing retrieval.
- Use direct registry client retrieval plus local `docker load`.
- Record which source actually supplied each image.
- Record manifest digest and local image identity when available.
- After a task image is retrieved, `environment/repo/` may be materialized from the digest-locked task image working directory first; non-repo support files remain governed by the RoadmapBench tree manifest and are copied or downloaded separately.
- Full manifest integrity still decides admission; image-based repo extraction is a transport reduction, not a relaxed integrity rule.
- Retry budget:
  official direct full blob pull `1` attempt after successful no-proxy manifest probe
  mirror full pull `3` attempts per source
- A task is replaceable only after all allowed sources fail or a pre-model admission gate fails.

## Admission Rule

For each seeded task:

1. Retrieve the Docker image through the source policy.
2. Materialize the task files into a new additive root:
   `roadmap_swe_evo_probe/data/roadmapbench_random30_extension_seeded_20260710`
3. Run pre-model admission checks:
   file integrity, support-file completeness, Docker presence, official solution-script sanity, verifier viability
4. If the task passes:
   admit it
5. If the task fails:
   record the exact reason and evidence path/hash, then move to the next seeded reserve task

Stop when `30` tasks are admitted.

## Freeze Boundary

Before any claim-bearing model run, the extension must produce:

- final task list
- candidate-order artifact hash
- exclusion-ledger hash
- Docker-provenance hash
- file-integrity hash
- gold-sanity hash
- dry-run prompt-visibility gate
- preflight E5/VCR row ledger and replay index

Only after these exist may a future model-side extension run begin.

## Non-Claim Boundary

This phase is infrastructure and provenance work only.

- no model/API execution
- no official RoadmapBench leaderboard claim
- no official SWE-bench claim
- no claim that the extension is a perfect benchmark-wide random sample

The strongest valid claim is narrower:

> The extension preserves seed-locked task order, infrastructure-only replacement, row-level provenance, and a pre-model freeze boundary.
