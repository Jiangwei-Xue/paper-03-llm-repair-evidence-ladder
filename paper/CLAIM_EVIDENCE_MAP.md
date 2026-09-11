# Claim-Evidence Map

This file is an editorial map for the manuscript master. It is not part of the paper text.

| Claim | Source data | Manuscript location | Boundary |
|---|---|---|---|
| Three strata contain 2,400 rows and 300 eight-repetition cells | `row_level_master_original.csv`, `row_level_claim_view.csv`, `cell_manifest.csv` | Sec. 4.1, Table 2 | Historical frozen strata |
| The two DeepSeek pools share no exact task IDs; GLM reuses clean task IDs | `task_manifest.csv`, parent structure audit | Sec. 4.1 | No repository-ID claim |
| GLM raw action count 98 becomes 86 under the application invariant | `glm_12_contradictions.csv`, row table | Sec. 5.1, Table 4 | Exact legacy mechanism unresolved |
| No observed pass has harmonized action 0 | `action_pass_crosstab_by_stratum.csv` | Sec. 5.2, Table 5 | Pipeline-conformance observation |
| Conditional endpoint yield is 14/199 and 14/204 | row table, cross-tab | Sec. 5.2 | Descriptive within stratum |
| At k=8, action discovery is 40.83%, 46.67%, and 45.00%; pass discovery is 4.17%, 1.67%, and 0% | `repeated_opportunity_k1_k8.csv` | Sec. 5.3, Table 6 | Finite retained opportunities |
| DeepSeek pass support is 28 rows, 7 cells, 3 tasks, 2 families | row table, task manifest | Sec. 5.4, Table 7 | Audit inventory, not pooled capability rate |
| Controls: 6/6 gold pass, 6/6 no-op fail, 9/9 mutants rejected | `endpoint_control_runs.csv` | Sec. 5.5, Table 8 | Two tasks/two families |
| Provider-linked metadata covers 2,005 rows; prompt/result hashes cover 2,400 | `provider_metadata_coverage.csv` | Sec. 4.7, App. D | Hosted backend not bitwise reproducible |
| Early-July records document project chronology | corrected chronology addendum | Artifact Availability, App. D | No worldwide-first or retroactive publication-priority claim |
