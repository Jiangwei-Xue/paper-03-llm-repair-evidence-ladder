# Model and Data Provenance

## Benchmark and task pools

The experiments use RoadmapBench version-upgrade tasks. The package distributes
derived task identifiers, admission records, run metadata, and image identities;
it does not redistribute third-party repository snapshots, protected verifier
material, or Docker layers.

The first pool contains 30 admission-filtered tasks. It was frozen before the
claim-bearing main-matrix calls. The second pool contains 30 additional tasks
constructed from a seed-first priority list after excluding the first pool.
Infrastructure failures and replacements are recorded in
`protocols/extension_pool/`. The pools are controlled evaluation surfaces, not
random-sample estimates of all repository-level repair tasks.

## Hosted model strata

| Public stratum | Provider route | Recorded model id | Rows | Role |
| --- | --- | --- | ---: | --- |
| DeepSeek clean, Flash | DeepSeek direct API | `deepseek-v4-flash` | 480 | primary |
| DeepSeek clean, Pro | DeepSeek direct API | `deepseek-v4-pro` | 480 | primary |
| DeepSeek extension, Flash | DeepSeek direct API | `deepseek-v4-flash` | 480 | independent pool replication |
| DeepSeek extension, Pro | DeepSeek direct API | `deepseek-v4-pro` | 480 | independent pool replication |
| GLM boundary | Alibaba Bailian DashScope-compatible hosted API | `glm-5.2` | 480 | supplementary cross-model boundary |

These are provider-visible identities, not checkpoint hashes. Hosted services may
change routing or serving implementations while retaining a public model id.
Accordingly, the historical model outputs are replay evidence; a future API call
is a new execution, not a bitwise regeneration claim.

## Common recorded controls

- V3 and V4 arms;
- `loop_only` prompt condition;
- eight repeats per task-arm-model cell;
- `answer_state` contract;
- strict `edit_json` transport;
- `max_tokens=32768` and `stage1_max_tokens=8192`;
- zero fuzzy matching and fail-closed edit application;
- Docker/verifier evaluation after a valid deterministic edit; and
- UTC timestamps, prompt hashes, row hashes, and replay links.

Historical fields are reported exactly as retained in each `RUN_CONFIG.json`.
Missing fields are not reconstructed from later defaults. The clean-pool profile
is recorded as `large_upgrade_v1_mko_contract_fix`; the extension profile is
recorded as `frozen`. They are separate strata rather than interchangeable pools.

## Randomness, retries, and service defaults

The eight repetitions are repeated hosted-model opportunities, not eight random
task samples. No task-selection seed is claimed for the first pool. The extension
pool's seed and full reserve order are public in `protocols/extension_pool/`.
Provider parameters absent from a historical request record are treated as
provider defaults and are not silently assigned a value in this release.
