# Scientific Reproducibility Release Audit

## A. Scope

Release ID: `claim_indexed_repair_github_reproduction_20260911_v11`.
The release supports deterministic saved-evidence recomputation, scientific
integrity checks, protocol inspection, and inspection of the retained live
harness. It does not claim a fresh hosted-model or Docker execution.

## B. Experiment inventory

The release contains 2,400 canonical executions in three separate evidence
strata: 960 DeepSeek clean-pool rows, 960 DeepSeek extension-pool rows, and 480
GLM-5.2 supplementary rows. It also contains five historical run ledgers with
2,970 retained records, including retries and intermediate records.

## C. Experimental-design completeness

Research questions, evidence-ladder constructs, task pools, V3/V4 arms, repeated
opportunities, fixed prompt condition, token budgets, edit semantics, and claim
boundaries are documented in `docs/EXPERIMENT_DESIGN.md`,
`docs/FORMAL_INTERACTION_PROTOCOL.md`, and `protocols/`.

## D. Reproduction scaffolding

`experiment_code/` contains the live runner, matched V3/V4 orchestration,
full-transcript prompt-audit implementation, strict answer-state tests, and a
no-API verifier. `Makefile` exposes one-command and staged offline checks.

## E. Data and input provenance

Task-pool construction, extension sampling and exclusions, gold/oracle sanity,
provider-visible model identities, run parameters, and Docker identities are
recorded in `protocols/`, `docs/MODEL_AND_DATA_PROVENANCE.md`, and `docker/`.
Third-party task sources and image layers remain subject to their original terms.

## F. Result provenance

The public chain binds retained run records to 2,400 self-hashed E5 rows, 2,400
self-hashed replay-index rows, a canonical table, a deterministic claim view, 300
fixed cells, generated tables, and manuscript claims.

## G. Dependencies and environment requirements

Offline integrity checks require Python 3.10 or later and the standard library.
Derived analysis requires the pinned dependency in `requirements.txt`.
Manuscript compilation requirements are in `paper/README.md`. Scientific event
timestamps use UTC.

## H. Validation and tests

The release defines executable checks for E5/VCR replay, canonical row and claim
alignment, deterministic analysis, Docker metadata, experiment-code syntax and
contract tests, prompt-audit availability, manuscript compilation, and final
archive integrity.

## I. Full reproduction

Saved-evidence analysis is reproducible offline. The package does not include all
external task repositories, protected verifiers, image layers, hosted model
weights, or every large per-attempt payload. Fresh external execution and full
raw-attempt dereferencing are therefore not verified by this source package.

## J. Result equivalence

The frozen public checks require exactly 2,400 canonical rows, 300 fixed cells,
403 harmonized governed actions across the two DeepSeek strata, 86 in the GLM
stratum, and verifier-pass counts of 14, 14, and 0 by stratum. Recomputed tables
must agree exactly with checked-in manuscript inputs.

## K. Figure and table provenance

`paper/scripts/build_derived.py` maps canonical CSV inputs to `paper/tables/` and
`paper/numbers.tex`. The path is documented in
`docs/FIGURE_TABLE_PROVENANCE.md` and `paper/CLAIM_EVIDENCE_MAP.md`.

## L. Paper and result mapping

`CURRENT_MANUSCRIPT.md` identifies the released manuscript. Its title and authors
match `paper/metadata.tex` and the compiled `paper/paper.pdf`. Numerical claims
are indexed in `paper/CLAIM_EVIDENCE_MAP.md`.

## M. Archive and manifest integrity

The canonical release workflow built from an explicit allowlist, emitted a closed
member manifest, performed duplicate deterministic builds, extracted into a fresh
directory, and executed the documented commands against the candidate archive.
The final archive hash and member manifest are recorded under `RELEASE_METADATA/`.

## N. Scientific limitations and boundaries

Verifier pass is a frozen operational criterion, not absolute semantic truth.
The task pools are controlled, admission-filtered surfaces rather than unbiased
samples of all repository-repair tasks. Hosted-provider identities do not expose
checkpoint or serving-stack hashes. E5/VCR replay validates retained public
relationships but cannot substitute for omitted external assets or all large raw
attempt files.

## O. Release decision

`PACKAGE VALIDATION: PASS` for the scientific scope stated in this document. The
canonical build completed its deterministic-build, clean-extraction, documented-
command, manifest, archive-hygiene, and reproducibility gates. Fresh model and
Docker execution remain outside this decision.

| Scientific check | Status | Public evidence |
| --- | --- | --- |
| Design and method boundary | PASS | `docs/EXPERIMENT_DESIGN.md`; `docs/METHOD_VERSION_HISTORY.md` |
| Frozen protocol/configuration surface | PASS | `protocols/`; historical `RUN_CONFIG.json` and `RUN_PLAN.json` |
| Result provenance | PASS | `EVIDENCE_INDEX.md`; E5/VCR ledgers |
| Deterministic analysis | PASS | `reproduce.py`; `paper/scripts/build_derived.py` |
| Harness syntax and contract tests | PASS | `experiment_code/verify_snapshot.py` |
| Docker metadata closure | PASS | `docker/verify_metadata.py` |
| Full-transcript prompt-audit records | PASS | `prompt_audits/` |
| Fresh hosted-model regeneration | NOT_VERIFIED | external mutable service |
| Fresh Docker/verifier execution | NOT_VERIFIED | external task assets and image layers |
| Complete raw-attempt public deposit | NOT_VERIFIED | `docs/LARGE_ARTIFACT_AVAILABILITY.md` |
| Final archive integrity | PASS | `RELEASE_METADATA/RELEASE_MANIFEST.jsonl`; canonical verifier |
