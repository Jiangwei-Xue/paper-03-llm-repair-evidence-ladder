# Current Manuscript and Evidence Alignment

The bundled manuscript is the current 22-page version and includes its LaTeX
sources, bibliography, compiled PDF, and approved public attribution for
Jiangwei X&#117;e, Zhida Qin, and Yuda Bi.

Its data- and artifact-availability statement points to:

> <https://github.com/Jiangwei-Xue/paper-03-llm-repair-evidence-ladder>

The manuscript DOI is <https://doi.org/10.5281/zenodo.22668842>. This DOI
identifies the manuscript rather than the reproduction package.

Preparing this local release does not itself upload or publish the package.

The paper's quantitative surface is fixed at 2,400 audited executions and 300
fixed task-arm cells across two DeepSeek task-pool strata and one separate GLM-5.2
supplementary stratum. `paper/SHA256SUMS.txt` binds the manuscript inputs;
`paper/scripts/build_derived.py --check-only` validates all released derived
outputs against the canonical rows.

The manuscript and package preserve the same interpretation boundary: intermediate
instruction compliance, applicable edits, governed actions, verifier entry, and
partial progress are not interchangeable with verifier-passing repair. The local
verifier is an operational criterion, not a claim of absolute semantic correctness.
