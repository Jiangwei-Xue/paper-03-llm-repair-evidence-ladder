# GLM-5.2 Hosted Boundary Protocol

GLM-5.2 was used as a supplementary cross-model boundary stratum through an
Alibaba Bailian DashScope-compatible hosted API in the `cn-beijing` service
region. This was not a self-hosted checkpoint execution and is not pooled with
the two DeepSeek task-pool strata.

The frozen experiment used the first 30-task pool, V3/V4 arms, `loop_only`, eight
repeats, `answer_state`, strict `edit_json`, `max_tokens=32768`,
`stage1_max_tokens=8192`, and the same Docker/verifier outcome surface. The
retained `RUN_CONFIG.json` additionally records four workers, five API attempts,
a 600-second timeout, and a 320,000-character context limit.

Provider-visible model identity and request metadata support API-level audit, not
bitwise checkpoint reproduction. A self-hosted reproduction would require a
public checkpoint revision, tokenizer and chat-template hashes, serving-engine
version, numerical precision or quantization, accelerator/runtime information,
and equivalent generation parameters. None of those unobserved hosted-service
details is inferred here.
