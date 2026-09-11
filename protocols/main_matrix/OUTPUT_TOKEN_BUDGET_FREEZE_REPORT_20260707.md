# Output Token Budget Freeze Report 20260707

## Status

This report freezes the claim-bearing RoadmapBench/SWE-EVO-style output token budget before the next main-matrix API execution.

No model API calls were made while creating this report.

## Frozen Values

| Variable | Frozen value | Scope |
| --- | ---: | --- |
| `max_tokens` / `max_completion_tokens` budget | 32768 | All claim-bearing model generations unless a provider adapter requires a renamed equivalent parameter. |
| `stage1_max_tokens` | 8192 | Staged V4 stage-1 planning only. |

These values replace the previous pre-main-matrix values:

| Variable | Previous value | New frozen value |
| --- | ---: | ---: |
| `max_tokens` | 16384 | 32768 |
| `stage1_max_tokens` | 4096 | 8192 |

Historical runs that used `16384/4096` remain historical evidence and must not be rewritten. Future claim-bearing runs under the frozen main matrix must use `32768/8192`.

## Rationale

The purpose of this freeze is not to maximize any one model's capability. The purpose is to remove a hidden output-budget confound before comparing transport, action-governance observability, and answer success across models.

The selected `32768` output budget is a conservative cross-model compatibility value:

- It matches Qwen-Long's documented maximum output length of 32,768 tokens.
- It matches the documented default `max_tokens` budget for Kimi K2.6 and Kimi K2.7 Code.
- It is below the documented output ceilings of DeepSeek V4, GPT-5.x, and current Claude Opus/Sonnet models.
- It is large enough to reduce avoidable `finish_reason=length` failures in long-code repair while remaining a common budget rather than a model-specific advantage.

The selected `8192` stage-1 budget is for staged V4 planning only. Earlier staged runs showed that stage-1 planning can be a bottleneck on larger upgrade tasks. Doubling the planning budget keeps the staged protocol bounded while reducing artificial plan truncation before stage-2 edit generation.

## Compatibility Evidence Snapshot

This is a source-derived compatibility snapshot as of 2026-07-07. Provider limits can change; claim-bearing runs must record actual request metadata and response metadata.

| Family | Relevant current models | Documented context/output evidence | Relationship to `32768` |
| --- | --- | --- | --- |
| DeepSeek API | `deepseek-v4-flash`, `deepseek-v4-pro` | DeepSeek documents 1M context and 384K max output for V4 Flash/Pro. | 32768 is well below provider ceiling. |
| OpenAI API | `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini` | OpenAI documents 128K max output for these models; 1M context for GPT-5.5/5.4 and 400K for GPT-5.4-mini. | 32768 is below provider ceiling. |
| Claude API | `claude-opus-4-8`, `claude-sonnet-5`, `claude-sonnet-4.6` | Anthropic documents 1M context and 128K max output for current Opus/Sonnet models; batch API can raise output further for some models. | 32768 is below synchronous provider ceiling. |
| Qwen API | `qwen-long-latest`, `qwen3.7-max`, `qwen3.6-flash` | Qwen-Long documents 10M context and 32,768 maximum output. Qwen3.7/Qwen3.6 pricing/docs expose up to 1M input/request tiers, while per-model output caps are provider-page-specific. | 32768 matches the smallest clearly documented Qwen long-context output cap. |
| Kimi API | `kimi-k2.6`, `kimi-k2.7-code` | Kimi documents 256K context and a 32K default `max_tokens` budget for K2.6/K2.7 Code; thinking models recommend sufficiently large budgets to avoid truncation. | 32768 matches documented default. |
| Open-weight Qwen | `Qwen3-Coder-Next`, `Qwen3-Coder-480B-A35B-Instruct`, `Qwen3.6-35B-A3B` | Qwen model cards document 256K-class contexts for current coder/3.6 models; coder examples/recommendations use 65,536 in some settings. | 32768 is compatible and conservative. |
| Open-weight Kimi | `Kimi-K2.6`, `Kimi-K2.7-Code` | Kimi model cards document 256K context. Kimi API docs use 32K default output for these families. | 32768 matches documented practical default. |
| Open-weight GLM/MiniMax candidates | GLM 4.6/4.7/5.x, MiniMax M2.5-class | Public model cards commonly document 200K+ context. Exact output caps depend on serving stack. | 32768 is a portable serving-level cap for admission probes. |

## Source References

The freeze uses official or first-party sources where available. Third-party routing/catalog pages were checked during exploration but are not used as claim-bearing evidence for this freeze.

| Source id | Provider / family | URL | Evidence used |
| --- | --- | --- | --- |
| S1 | DeepSeek API | `https://api-docs.deepseek.com/quick_start/pricing` | Model Details table for `deepseek-v4-flash` and `deepseek-v4-pro`: context length 1M and max output 384K. |
| S2 | OpenAI API | `https://developers.openai.com/api/docs/models` | Models page entries for GPT-5.5, GPT-5.4, and GPT-5.4 mini: max output 128K; context 1M for GPT-5.5/GPT-5.4 and 400K for GPT-5.4 mini. |
| S3 | Anthropic Claude context windows | `https://docs.anthropic.com/en/docs/build-with-claude/context-windows` | Claude Opus 4.8, Opus 4.7, Opus 4.6, Sonnet 5, and Sonnet 4.6 have 1M-token context windows on Claude API; output counts toward context. |
| S4 | Anthropic Claude extended thinking | `https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking` | Claude Opus 4.8, Opus 4.7, Sonnet 5, Opus 4.6, and Sonnet 4.6 support up to 128K output tokens; Claude Haiku 4.5 supports up to 64K. |
| S5 | Anthropic Opus 4.8 release docs | `https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-8` | Claude Opus 4.8 supports 1M context and 128K max output tokens. |
| S6 | Alibaba Cloud Qwen-Long | `https://www.alibabacloud.com/help/en/model-studio/long-context-qwen-long` | Qwen-Long total context length 10M; API output maximum 32,768 tokens. |
| S7 | Alibaba Cloud Qwen OpenAI-compatible API | `https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions` | `max_completion_tokens` controls full output including chain-of-thought; default and maximum values correspond to the model's maximum output length; supported by Qwen, Kimi, DeepSeek, GLM, and MiniMax families on Model Studio where applicable. |
| S8 | Alibaba Cloud Qwen pricing/model tiers | `https://www.alibabacloud.com/help/en/model-studio/model-pricing` | Qwen3.7 Max and Qwen Flash pricing/model tables expose up to 1M input-token/request tiers; used for context-budget awareness, not for a per-model output cap claim. |
| S9 | Kimi K2.7 Code quickstart | `https://platform.kimi.ai/docs/guide/kimi-k2-7-code-quickstart` | `max_tokens` is optional and defaults to 32K / 32768 for Kimi K2.7 Code. |
| S10 | Kimi K2.6 quickstart | `https://platform.kimi.ai/docs/guide/kimi-k2-6-quickstart` | `max_tokens` is optional and defaults to 32K / 32768 for Kimi K2.6. |
| S11 | Kimi FAQ | `https://platform.kimi.ai/docs/guide/faq` | Kimi output length is bounded by model context minus prompt tokens for K2.6/K2.5/K2 preview families; used as context-window boundary evidence. |
| S12 | Kimi thinking model guide | `https://platform.kimi.ai/docs/guide/use-kimi-k2-thinking-model` | Kimi recommends `max_tokens >= 16000` for thinking models to return reasoning and content without truncation. |
| S13 | DeepSeek V4 model card | `https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro` | Open-weight DeepSeek V4 Pro/Flash model card documents 1M context and open-weight availability. |
| S14 | Qwen3-Coder-Next model card | `https://huggingface.co/Qwen/Qwen3-Coder-Next` | Open-weight Qwen3-Coder-Next documents 262,144 native context and uses `max_tokens=65536` in an example. |
| S15 | Qwen3-Coder-480B-A35B-Instruct model card | `https://huggingface.co/Qwen/Qwen3-Coder-480B-A35B-Instruct` | Model card recommends an output length of 65,536 tokens for most queries. |
| S16 | Qwen3.6-35B-A3B model card | `https://huggingface.co/Qwen/Qwen3.6-35B-A3B` | Open-weight Qwen3.6 model card documents 262,144 native context. |
| S17 | Kimi K2.7 Code model card | `https://huggingface.co/moonshotai/Kimi-K2.7-Code` | Open-weight Kimi K2.7 Code model card documents 256K context. |
| S18 | Kimi K2.6 model card | `https://huggingface.co/moonshotai/Kimi-K2.6` | Open-weight Kimi K2.6 model card documents 256K context. |
| S19 | GLM-4.5 / GLM-4.6 repository | `https://github.com/zai-org/GLM-4.5` | GLM 4.6/4.7 notes document a 200K-token context window for later GLM-4.x open-weight models. |

## Source Interpretation

The smallest clearly documented practical output number among the reviewed first-party sources is `32768`:

- Qwen-Long: maximum output length is 32,768.
- Kimi K2.6/K2.7 Code: default `max_tokens` is 32K / 32768.

Therefore `32768` is a defensible cross-model freeze point. It does not claim every candidate model has the same official maximum. It fixes a common experimental budget below the larger provider ceilings and at the smallest clearly documented long-code output budget among likely follow-up models.

## Protocol Changes Made

Updated future-facing protocol files:

```text
Artifact_Chain/FROZEN_MAIN_MATRIX_PROTOCOL_20260707.md
Artifact_Chain/FROZEN_3REPO_E5_PILOT_PROTOCOL_20260707.md
Artifact_Chain/FROZEN_1REPO_OPEN_CHINESE_MODEL_ADMISSION_PROTOCOL_20260707.md
roadmap_swe_evo_probe/scripts/roadmapbench_tier1_matched_v3_v4_runner.py
```

The runner defaults now match the frozen values to avoid accidental fallback to the old budget when CLI flags are omitted.

## Validation

Local checks:

```text
py_compile runner: PASS
py_compile prompt visibility audit: PASS
py_compile E5/VCR tool: PASS
answer_state_contract_tests: PASS
```

New dry-run evidence was generated with no API calls:

| Run | Planned rows | `max_tokens` | `stage1_max_tokens` |
| --- | ---: | ---: | ---: |
| `roadmapbench_mainmatrix_deepseek_pro_30task_clean_v3_v4_1rep_token32768_8192_20260707_dryrun` | 60 | 32768 | 8192 |
| `roadmapbench_mainmatrix_deepseek_flash_30task_clean_v3_v4_1rep_token32768_8192_20260707_dryrun` | 60 | 32768 | 8192 |

Prompt visibility dry-run audits:

| Audit | Prompt files scanned | failure_count | feedback_leak_audit_failures | missing_attempt_prompt_artifacts |
| --- | ---: | ---: | ---: | --- |
| `outputs/PROMPT_VISIBILITY_AUDIT_MAINMATRIX_DEEPSEEK_PRO_30TASK_TOKEN32768_8192_DRYRUN_20260707.json` | 90 | 0 | 0 | `[]` |
| `outputs/PROMPT_VISIBILITY_AUDIT_MAINMATRIX_DEEPSEEK_FLASH_30TASK_TOKEN32768_8192_DRYRUN_20260707.json` | 90 | 0 | 0 | `[]` |

E5/VCR preflight package:

```text
Artifact_Chain/E5_VCR_MAINMATRIX_30TASK_TOKEN32768_8192_PREFLIGHT_20260707_*
```

E5/VCR summary:

| Metric | Value |
| --- | ---: |
| `run_count` | 2 |
| `row_ledger_count` | 120 |
| `replay_record_count` | 120 |
| `rows_with_prompt_hash` | 120 |
| `rows_with_row_ledger_hash` | 120 |
| `rows_with_request_response_hashes` | 0 |
| `rows_with_result_row_hash` | 0 |

The zero request/response/result counts are expected because this is a dry-run preflight, not a model execution.

## Inclusion Boundary

This token-budget freeze is a controlled-variable update before claim-bearing execution. It does not change:

- task pool;
- task hashes;
- provider route;
- DeepSeek model ids;
- V3/V4 arm definitions;
- prompt variant;
- `answer_state` contract;
- strict `edit_json` / `file_ops_json` transport;
- deterministic edit semantics;
- failure taxonomy;
- prompt visibility gate;
- metric definitions.

If a future provider cannot accept the exact `max_tokens` parameter name, its adapter must map this value to the provider-equivalent field, such as `max_completion_tokens`, and record that mapping in the provider addendum before any claim-bearing API call.

## Decision

GO for future dry-run and claim-bearing execution under the frozen output budget:

```text
max_tokens = 32768
stage1_max_tokens = 8192
```

HOLD for Kimi/Qwen/open-model claim-bearing execution until exact provider adapters, model ids, and parameter mappings are frozen separately.
