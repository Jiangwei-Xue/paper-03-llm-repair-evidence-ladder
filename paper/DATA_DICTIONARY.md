# Manuscript Data Dictionary

## Row tables

### `row_level_master_original.csv`

Unmodified public canonical table from the verified evidence bundle. Its relevant source fields are:

| Canonical field | Use in manuscript |
|---|---|
| `pool` | instrumentation stratum |
| `model` | hosted route label |
| `task_id`, `task_family` | support units |
| `arm`, `repetition` | fixed-cell and opportunity structure |
| `action_governance_success` | raw action field |
| `deterministic_edit_apply_success` | deterministic application indicator |
| `patch_apply_check_ok` | retained patch-application check |
| `action_governance_harmonized` | published governed-action construct |
| `answer_success` | verifier-pass endpoint |
| `failure_step`, `failure_reason`, `final_failure_category` | mechanical execution diagnostics |
| `timestamp_utc` | canonical result-row timestamp |
| `row_id` | canonical row identity |

### `row_level_claim_view.csv`

Deterministic projection used by `scripts/build_derived.py`. It contains stable run/cell identifiers and the variables referenced in the manuscript. Binary claim fields use a positive-event rule: equality to numeric `1` maps to one; every other canonical value maps to zero for the planned-execution denominator. The canonical table remains available so missingness and historical field coverage can be inspected directly.

The validator recomputes:

`action_harmonized = action_raw AND deterministic_edit_apply_success AND patch_apply_check_ok`

and checks exact agreement with both the canonical harmonized field and the compact claim view.

## Other tables

The remaining CSV files are compact verified outputs for cell/task structure, opportunity analysis, endpoint controls, construct conflicts, task-family sensitivity, provider coverage, and chronology. Their roles are listed in `CLAIM_EVIDENCE_MAP.md`.
