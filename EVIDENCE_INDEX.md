# Evidence Index

## Canonical analysis surface

| Evidence | Location | Scope |
|---|---|---|
| Canonical rows | `paper/data/row_level_master_original.csv` | 2,400 final rows |
| Claim view | `paper/data/row_level_claim_view.csv` | deterministic manuscript projection |
| Cell manifest | `paper/data/cell_manifest.csv` | 300 fixed cells |
| Task manifest | `paper/data/task_manifest.csv` | task and family support |
| Analysis code | `paper/scripts/build_derived.py` | validation and derived outputs |
| Claim map | `paper/CLAIM_EVIDENCE_MAP.md` | claims, inputs, outputs, and boundaries |

## Historical run records

`evidence/02_CLAIM_BEARING_RUN_LEDGERS/` contains five historical `RESULTS.jsonl`
files with 2,970 records, including retries and intermediate records. They are
provenance material and are not the manuscript denominator.

| Historical run | Recorded entries |
|---|---:|
| DeepSeek clean pool, Pro route | 605 |
| DeepSeek clean pool, Flash route | 568 |
| DeepSeek extension pool, Pro route | 592 |
| DeepSeek extension pool, Flash route | 597 |
| GLM-5.2 supplementary route | 608 |
| **Total** | **2,970** |

## Row and replay integrity

`evidence/03_E5_VCR/` contains three row ledgers and three replay indexes:

- DeepSeek clean pool: 960 rows;
- DeepSeek extension pool: 960 rows;
- GLM-5.2 supplementary stratum: 480 rows.

Each record carries a self-hash. Replay records link to the corresponding public
row-ledger hash. `replay_all.py` validates 2,400 row records, 2,400 replay records,
the canonical row table, the 300-cell manifest, and released claim counts.

## Corroborating evidence

`evidence/04_CORROBORATION/` preserves Docker retrieval and provenance records
used to identify the task-image surface. `evidence/05_VALIDATION/` records the
file-level E5/VCR validation summary and provider metadata census used by the
offline verifier.

## Docker and implementation surface

`docker/` contains the 60-image roster, full retained image-configuration ledger,
runtime contract, and an offline metadata verifier. `experiment_code/` contains
the retained runner snapshot and its own integrity verifier.

Image layers, protected verifier material, and third-party repository snapshots
are external dependencies. Their absence limits the package to saved-evidence
replay and metadata-level environment identification unless a reproducer obtains
the benchmark assets separately.

## Protocol and prompt evidence

`protocols/` preserves the claim-bearing matrix freeze, output-token decision,
extension candidate order and reserve logic, admission evidence, and model-
boundary protocol. `prompt_audits/` preserves executed visibility audits for the
two main-matrix routes, two extension routes, and GLM boundary stratum.

`docs/FORMAL_INTERACTION_PROTOCOL.md` provides a compact public specification of
the answer-state schema, strict edit semantics, staged plan, repair policy, and
outcome functions. `docs/METHOD_VERSION_HISTORY.md` separates the development
versions from the V3/V4 claim-bearing surface.
