# Experiment Timeline

All dates below use UTC. This is a scientific chronology, not a development log.

| Date | Scientific event | Public evidence |
| --- | --- | --- |
| 2026-07-05 | Answer-state decomposition and strict edit transport were developed in pilots. | `docs/METHOD_VERSION_HISTORY.md` |
| 2026-07-07 | The 30-task main-matrix protocol, task pool, token budgets, two DeepSeek routes, V3/V4 arms, and eight repeats were frozen and executed. | `protocols/main_matrix/`; main-matrix run ledgers |
| 2026-07-08 to 2026-07-09 | GLM-5.2 was executed as a hosted cross-model boundary stratum under the matched V3/V4 measurement surface. | `protocols/model_boundary/`; GLM run ledger |
| 2026-07-09 to 2026-07-10 | A seed-first candidate order was subjected to infrastructure admission; exclusions and replacements followed the frozen reserve order. | `protocols/extension_pool/` |
| 2026-07-10 | The 30-task extension pool was frozen, audited for prompt visibility, and executed with the two DeepSeek routes. | extension run ledgers and `prompt_audits/extension_pool/` |
| 2026-08-29 | Historical rows were reconciled into three separate evidence strata and a 2,400-row canonical analysis surface. | `paper/data/row_level_master_original.csv`; E5/VCR ledgers |
| 2026-09-11 | The current manuscript, analysis, protocols, prompt audits, runner snapshot, Docker metadata, and offline replay interface were assembled as this release. | `CURRENT_MANUSCRIPT.md`; `RELEASE_AUDIT.md` |

The primary analysis does not pool development pilots, Qwen adaptation diagnostics,
model bridge checks, or controller-study episodes. New hosted-model calls would
form a new evidence stratum rather than extending these historical rows in place.
