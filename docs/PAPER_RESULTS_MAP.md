# Paper Results Map

## Canonical denominator

- 2,400 claim-bearing final rows.
- 300 fixed cells.
- Eight retained opportunities per cell.
- 1,920 DeepSeek rows across two separate 30-task pools.
- 480 GLM-5.2 supplementary rows on the original 30-task pool.

The five public historical ledgers contain 2,970 records because they preserve
intermediate calls and retries. They are provenance sources, not the analysis
denominator.

## Primary files

| Question | Canonical source |
| --- | --- |
| Row-level outcomes | `paper/data/row_level_claim_view.csv` |
| Original canonical rows | `paper/data/row_level_master_original.csv` |
| Fixed-cell membership | `paper/data/cell_manifest.csv` |
| Task and family identities | `paper/data/task_manifest.csv` |
| Protocol-stratified counts | `paper/data/protocol_stratified_summary.csv` |
| Repeated-opportunity results | `paper/data/repeated_opportunity_k1_k8.csv` |
| Action/pass cross-tabulation | `paper/data/action_pass_crosstab_by_stratum.csv` |
| Task support concentration | `paper/data/task_support_summary.csv` and `pass_concentration_by_task.csv` |
| Family-clustered uncertainty | `paper/data/family_cluster_bootstrap.csv` |
| Leave-one-family-out analysis | `paper/data/leave_one_family_out.csv` |
| Pool overlap | `paper/data/pool_overlap_audit.csv` |
| Endpoint controls | `paper/data/endpoint_control_runs.csv` |
| Claim-to-source prose map | `paper/CLAIM_EVIDENCE_MAP.md` |

## Released aggregate checks

The canonical view contains 489 harmonized governed-action rows and 28 verifier
passes across all three strata. These aggregate counts are descriptive only;
the paper separates strata and does not treat 2,400 repeated executions as
independent tasks.

The two DeepSeek pools each contribute 960 rows. The GLM-5.2 stratum contributes
480 rows and is reported separately as a supplementary model-family boundary.

## Interpretation limits

The release supports conclusions about measurement divergence and support
concentration within the two frozen RoadmapBench task pools. It does not estimate
a random-sample RoadmapBench-wide repair rate, rank the hosted models, establish
method superiority, or equate verifier pass with complete semantic correctness.

Docker identities cover the 60 distinct tasks in the two DeepSeek pools. The GLM
supplementary stratum reuses the first 30-task Docker pool and therefore does not
add another 30 image identities.
