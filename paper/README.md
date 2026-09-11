# Claim-Indexed Repair Measurement Paper: LaTeX Master

This package is a full, editable manuscript master for:

> **What Does a Repair Statistic Measure? A Claim-Indexed Audit of Repository-Level LLM Repair**

It contains no newly generated model, Docker, verifier, mutation, or controller observations. All numerical claims are deterministic transformations of the public canonical row table and compact claim view in `data/`.

## Build

Requirements: Python 3 with pandas, TeX Live with `latexmk`, and BibTeX.

```bash
make all
```

The build performs two steps:

1. validates the claim-bearing data and regenerates `numbers.tex` plus all tables;
2. compiles `paper.pdf`.

## Manuscript metadata

The current authors, affiliations, and corresponding-author details are supplied
in `metadata.tex`. The public reproduction repository is
<https://github.com/Jiangwei-Xue/paper-03-llm-repair-evidence-ladder>. The
manuscript DOI is <https://doi.org/10.5281/zenodo.22668842>; it is not the
reproduction package identifier. The body is organized under `sections/`;
in-manuscript appendices are under `appendix/`. No figure files or figure
environments are used.

The authors retain copyright in the manuscript and license it under CC BY 4.0,
consistently with the Zenodo manuscript record. See `LICENSE.md` in this
directory and `../LICENSE.md` for the package-wide layered license map.

## Data choices

`row_level_master_original.csv` preserves the public canonical fields. `row_level_claim_view.csv` is a deterministic projection containing the identifiers and variables used by the manuscript. The cross-stratum empirical variables are harmonized governed action and verifier pass. Earlier event fields remain in the canonical table where available, but their historical coverage is incomplete. The primary repeated-opportunity result uses the exact subset-averaged finite-population calculation over each cell's eight retained outcomes. Ordered-prefix values remain a sensitivity analysis.

## Reproduction files

- `CLAIM_EVIDENCE_MAP.md`: maps headline claims to data and scope.
- `scripts/build_derived.py`: regenerates all numerical content.
