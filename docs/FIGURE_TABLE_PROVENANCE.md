# Figure and Table Provenance

## Deterministic path

```text
paper/data/row_level_master_original.csv
  -> paper/data/row_level_claim_view.csv
  -> paper/scripts/build_derived.py
  -> paper/tables/*.tex and paper/numbers.tex
  -> paper/main.tex
  -> paper/paper.pdf
```

`python3 reproduce.py` validates the canonical inputs and generated manuscript
statistics. `paper/CLAIM_EVIDENCE_MAP.md` maps every principal numerical claim to
its input and generated output. `paper/DATA_DICTIONARY.md` defines the released
columns and denominators.

The current manuscript is table-led and does not rely on an untracked plotting
workflow. Any future visualization derived from the released CSV files should be
treated as a new presentation layer and should preserve the stratum, task, and
family denominators used here.
