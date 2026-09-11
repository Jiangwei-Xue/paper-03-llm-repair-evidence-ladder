# Source and Evidence Notes

This master was prepared from two verified public evidence archives:

- `arxiv_rewrite_evidence_bundle_20260902.zip`  
  SHA-256: `bc0e7daa7d08cbb62473070fa73891b9c1313d693c1f165140a9804c7060cea9`
- `arxiv_rewrite_evidence_addendum_20260902.zip`  
  SHA-256: `8731cd62231015ceb95130ec6ee82157a6aefa1f02ab27933af56956d5cb2c81`

No new model request, repository execution, Docker run, verifier call, mutation run, or controller experiment was used in preparing the manuscript.

## Claim-bearing data in this package

- `data/row_level_master_original.csv` is an unmodified copy of the public canonical 2,400-row table.
- `data/row_level_claim_view.csv` is a deterministic projection generated from the canonical table. It keeps the identifiers and variables used by the manuscript.
- The build validator recomputes governed action as the conjunction of the raw action flag, deterministic edit application, and patch-application check, then verifies agreement with the published harmonized field.
- Provider coverage, endpoint controls, opportunity tables, task support, and chronology windows are compact copies or deterministic derivatives of the verified releases.

## Public/private boundary

The manuscript package contains no protected prompt text, raw provider response text, candidate patch content, hidden verifier material, credentials, or private transport payloads. Coverage tables and integrity identifiers describe the retained evidence without disclosing protected content.

## Chronology boundary

Retained local records and provider-linked artifacts document development chronology. They do not establish a public release date before the eventual archive deposit. The current manuscript points readers to the public reproduction repository at <https://github.com/Jiangwei-Xue/paper-03-llm-repair-evidence-ladder>. The separate DOI <https://doi.org/10.5281/zenodo.22668842> identifies the manuscript, not the reproduction package.
