# Ollama Logprob Investigation

Investigation into whether the Ollama API returns per-token logprobs for cloud vs local models, conducted 2026-03-23.

---

## Background

The Kenichi distillation project plans to add logprob-based distillation (KL-divergence loss) on top of existing SFT data. This requires per-token probability distributions from teacher models. The `Training/events.md` notes that Ollama supports `logprobs: true` and `top_logprobs: 15`, but this had not been tested against cloud models.

## Test Setup

A test script (`pipeline/scripts/test_logprobs.py`) was created to invoke models with logprobs enabled across all three Ollama API endpoints:

1. **`/api/chat`** -- native Ollama chat endpoint
2. **`/api/generate`** -- native Ollama generate endpoint
3. **`/v1/chat/completions`** -- OpenAI-compatible endpoint

Prompt used: `"What is 2 + 2? Answer in one word."` with `logprobs: true` and `top_logprobs: 5`.

---

## Test 1: Cloud Model (`glm-5:cloud`)

### `/api/chat`

```json
{
  "model": "glm-5:cloud",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is 2 + 2? Answer in one word."}
  ],
  "stream": false,
  "logprobs": true,
  "top_logprobs": 5,
  "options": {"temperature": 0.7, "top_p": 0.95, "num_predict": 512}
}
```

**Response:** Model returned correct answer ("Four") with thinking trace. **No `logprobs` key in response.**

### `/api/generate`

Same parameters adapted for the generate endpoint. **No `logprobs` key in response.**

### `/v1/chat/completions` (OpenAI-compatible)

```json
{
  "model": "glm-5:cloud",
  "messages": [...],
  "temperature": 0.7,
  "top_p": 0.95,
  "max_tokens": 512,
  "logprobs": true,
  "top_logprobs": 5
}
```

**Response:** OpenAI-format response with `choices[0]`, but **no `logprobs` field in the choice object**. The `logprobs` parameter was silently ignored.

### Cloud Model Notes

- First attempt had `logprobs` inside `options` -- also did not work.
- Moving `logprobs`/`top_logprobs` to top-level payload made no difference.
- The Ollama API documentation (GitHub `ollama/ollama/blob/main/docs/api.md`) does **not** list `logprobs` as a parameter for either `/api/generate` or `/api/chat`.
- The cloud relay at `ollama.com:443` either strips or does not forward the logprobs request.

---

## Test 2: Local Model (`gpt-oss:20b`)

### `/api/chat`

Same payload structure, model changed to `gpt-oss:20b`.

**Result: Logprobs returned successfully.** Top-level `logprobs` array with per-token data:

```json
{
  "model": "gpt-oss:20b",
  "message": {
    "role": "assistant",
    "content": "Four.",
    "thinking": "The user is asking \"What is 2 + 2?\" ..."
  },
  "done": true,
  "logprobs": [
    {
      "token": "<|channel|>",
      "logprob": -2.12e-08,
      "bytes": [60, 124, 99, 104, 97, 110, 110, 101, 108, 124, 62],
      "top_logprobs": [
        {"token": "<|channel|>", "logprob": -2.12e-08, "bytes": [...]},
        {"token": "<|message|>", "logprob": -17.93, "bytes": [...]},
        {"token": "<|constrain|>", "logprob": -19.18, "bytes": [...]}
      ]
    }
  ]
}
```

### `/api/generate`

**Result: Logprobs returned successfully.** Same per-token structure.

### `/v1/chat/completions` (OpenAI-compatible)

**Result: Logprobs returned successfully** in the standard OpenAI format:

```json
{
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "..."},
      "logprobs": {
        "content": [
          {
            "token": "<|channel|>",
            "logprob": -3.82e-09,
            "bytes": [...],
            "top_logprobs": [...]
          }
        ]
      },
      "finish_reason": "stop"
    }
  ]
}
```

---

## Summary

| Model | Type | `/api/chat` | `/api/generate` | `/v1/chat/completions` |
|---|---|---|---|---|
| `glm-5:cloud` | Cloud (remote) | No logprobs | No logprobs | No logprobs |
| `gpt-oss:20b` | Local | **Logprobs returned** | **Logprobs returned** | **Logprobs returned** |

### Per-Token Logprob Structure

Each token entry contains:

| Field | Type | Description |
|---|---|---|
| `token` | string | The token text |
| `logprob` | float | Log probability of the selected token |
| `bytes` | int[] | UTF-8 byte representation |
| `top_logprobs` | array | Top-N alternative tokens with their logprobs |

---

## Conclusion

**Ollama supports logprobs for locally-served models but not for cloud (`:cloud`) models.** The cloud relay at `ollama.com:443` either does not request logprobs from the upstream provider or strips them from the response.

### Implications for Logprob Distillation

To collect logprob data from cloud-scale teacher models, options include:

1. **Use provider APIs directly** -- Zhipu (GLM), MiniMax, and Moonshot (Kimi) may expose logprobs through their native API endpoints.
2. **Run teacher models locally** -- requires significant GPU resources (likely multi-GPU or cloud instances) for models at the scale of GLM-5 / Kimi K2.5 / MiniMax M2.7.
3. **Use locally-runnable models as teachers** -- e.g., `gpt-oss:20b` or similar models that fit on consumer GPUs and return logprobs via Ollama.
4. **Wait for Ollama cloud logprob support** -- this may be added in a future Ollama update.
