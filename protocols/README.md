# Frozen Protocol Evidence

- `main_matrix/` records the 30-task DeepSeek matrix freeze, variable surface,
  and token-budget decision.
- `extension_pool/` records the full seed-first priority order, infrastructure-
  constrained admission, exclusions, gold/oracle sanity, and final pool freeze.
- `model_boundary/` describes the GLM-5.2 hosted supplementary protocol in a
  public, machine-independent form.

These records establish what was fixed before execution. The per-stratum
`RUN_CONFIG.json` and `RUN_PLAN.json` files remain authoritative for actual
retained request settings and planned rows.
