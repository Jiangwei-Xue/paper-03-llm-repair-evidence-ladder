# What Does a Repair Statistic Measure?

This is the GitHub-ready reproduction package for:

> **What Does a Repair Statistic Measure? A Claim-Indexed Audit of Repository-Level LLM Repair**

The package contains the current 22-page manuscript, its deterministic analysis
code, the canonical result surface, row-level E5/VCR integrity records,
historical run records, frozen protocols, full-transcript prompt audits, the live
experiment harness, and Docker identity/configuration metadata for the 60
RoadmapBench task images used by the two DeepSeek strata.

Repository: <https://github.com/Jiangwei-Xue/paper-03-llm-repair-evidence-ladder>

## Scientific scope

The released analysis treats the following as distinct observations:

1. structured state validity;
2. deterministic edit application;
3. governed source-code action;
4. Docker/verifier entry;
5. partial verifier progress; and
6. verifier-passing repair.

The evidence surface comprises:

| Stratum | Rows | Fixed cells | Role |
|---|---:|---:|---|
| DeepSeek clean task pool | 960 | 120 | primary evidence |
| DeepSeek extension task pool | 960 | 120 | independent task-pool replication |
| GLM-5.2 hosted arm | 480 | 60 | supplementary cross-model boundary |
| **Total** | **2,400** | **300** | audited executions, not independent tasks |

## Start here

1. `paper/paper.pdf` - compiled manuscript.
2. `docs/EXPERIMENT_DESIGN.md` - measurement model and study design.
3. `docs/PAPER_RESULTS_MAP.md` - claim-to-evidence map.
4. `docs/REPRODUCTION_PROTOCOL.md` - supported reproduction levels.
5. `paper/data/row_level_master_original.csv` - canonical execution table.
6. `paper/data/row_level_claim_view.csv` - deterministic claim projection.
7. `evidence/03_E5_VCR/` - row ledgers and replay indexes.
8. `protocols/` - matrix freezes, task-pool selection, admission, and model boundary.
9. `prompt_audits/` - first- and full-transcript visibility evidence.
10. `experiment_code/` - retained live runner, V3/V4 wrapper, audit, and tests.
11. `docker/IMAGE_ROSTER.jsonl` - identity records for 60 task images.
12. `docs/METHOD_VERSION_HISTORY.md` - V1 to V4 method and claim boundary.
13. `RELEASE_AUDIT.md` - public scientific reproducibility decision.
14. `LICENSE.md` - layered licensing rules.

## Verify the downloaded release

From the extracted archive root:

<!-- RELEASE_COMMAND:verify -->
```sh
python3 tools/VERIFY_ARCHIVE.py verify --archive <ARCHIVE_PATH> --public
```
<!-- END_RELEASE_COMMAND:verify -->

<!-- RELEASE_COMMAND:h5-e5-vcr-replay -->
```sh
python3 replay_all.py --archive <ARCHIVE_PATH>
```
<!-- END_RELEASE_COMMAND:h5-e5-vcr-replay -->

<!-- RELEASE_COMMAND:docker-metadata -->
```sh
python3 docker/verify_metadata.py --archive <ARCHIVE_PATH>
```
<!-- END_RELEASE_COMMAND:docker-metadata -->

<!-- RELEASE_COMMAND:experiment-code -->
```sh
python3 experiment_code/verify_snapshot.py --archive <ARCHIVE_PATH>
```
<!-- END_RELEASE_COMMAND:experiment-code -->

<!-- RELEASE_COMMAND:prompt-audit-reports -->
```sh
python3 prompt_audits/verify_reports.py --archive <ARCHIVE_PATH>
```
<!-- END_RELEASE_COMMAND:prompt-audit-reports -->

Expected markers include:

```text
OVERALL_RELEASE_STATUS=PASS
PUBLIC_SCIENTIFIC_EVIDENCE_INTEGRITY=PASS
E5_LEDGER_ROWS=2400
VCR_REPLAY_ROWS=2400
CANONICAL_ROWS=2400
FIXED_CELLS=300
CLAIM_METRICS_AND_CROSSTAB=PASS
H5_E5_VCR_REPLAY_STATUS=PASS
DOCKER_METADATA_STATUS=PASS
EXPERIMENT_CODE_STATUS=PASS
PROMPT_AUDIT_REPORTS_STATUS=PASS
```

## Recompute the manuscript analysis

The analysis uses Python plus the pinned dependency in `requirements.txt`:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 reproduce.py
```

The command compares regenerated outputs with the checked-in manuscript inputs
and ends with `REPRODUCTION_STATUS=PASS` when they agree.

For all network-free scientific checks in one command:

```sh
make all-offline
```

The Makefile also exposes `replay`, `analysis`, `harness`, `docker-metadata`, and
`prompt-audits` as separate stages so the one-command path is not a black box.

To compile the paper, follow `paper/README.md`. From the `paper/` directory run:

<!-- RELEASE_COMMAND:compile-current -->
```sh
sh COMPILE_SOURCE.sh <ARCHIVE_PATH>
```
<!-- END_RELEASE_COMMAND:compile-current -->

## Reproduction boundary

This package supports deterministic recomputation from saved evidence and offline
verification of row, replay, analysis, Docker-metadata, code-snapshot, prompt-
audit, and release integrity. It does not contain Docker image layers, protected
verifier material, third-party repository snapshots, hosted-model weights, or
credentials.

A fresh Docker rerun therefore requires the external benchmark assets identified
in `docker/`, subject to their original terms. A fresh hosted-model run is a new
evidence stratum because providers may update routing, weights, inference stacks,
or availability. Neither fresh external execution nor byte-identical model-output
regeneration is claimed by this archive. Complete per-attempt raw payloads require
a separate large-artifact deposit; their public availability is not claimed by
this source release. See `docs/LARGE_ARTIFACT_AVAILABILITY.md`.

## Licensing

Licensing is layered:

- project documentation and author-created derived result tables: CC BY 4.0;
- original analysis and verification code: MIT;
- manuscript: author copyright, publicly licensed under CC BY 4.0 consistently
  with its Zenodo record;
- third-party libraries, benchmark-derived records, public data, and model output:
  their original terms.

This is a mixed-license repository; no single license applies to every file.
See `LICENSE.md`, `LICENSES/`, `paper/LICENSE.md`, and
`THIRD_PARTY_NOTICES.md` for details.
