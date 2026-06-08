# Qwen 3.6

Qwen 3.6 model profiles for Ollama under the shared `odytrice/qwen3.6` model
name. Tags encode target GPU and parameter count as `<gpu>-<size>`.

## Tags

| Tag | GPU | Quantization | `num_ctx` |
|---|---|---|---|
| `odytrice/qwen3.6:4090-27b` | RTX 4090 (24 GB Ada) | Ollama Q4_K_M (~17 GB) | 131072 |
| `odytrice/qwen3.6:5090-27b` | RTX 5090 (32 GB Blackwell) | Ollama Q4_K_M (~17 GB) | 262144 |
| `odytrice/qwen3.6:5090-35b` | RTX 5090 (32 GB Blackwell) | Ollama Q4_K_M (~23 GB) | 262144 |

The 35B-A3B MoE profile does not leave usable KV cache headroom on a 24 GB
4090 at practical context lengths, so only a 5090 profile is provided for 35B.

## Upstream

| Size | Upstream | Architecture | Modalities | Native context |
|---|---|---|---|---|
| 27B | `Qwen/Qwen3.6-27B` | Dense | Text + Image + Video | 262144 |
| 35B | `Qwen/Qwen3.6-35B-A3B` | MoE A3B, 35B total / 3B active | Text + Image + Video | 262144 |

## Environment

Always set these before running Ollama:

```
set OLLAMA_KV_CACHE_TYPE=q8_0
set OLLAMA_FLASH_ATTENTION=1

export OLLAMA_KV_CACHE_TYPE=q8_0
export OLLAMA_FLASH_ATTENTION=1
```

## Context Size

The 27B 4090 profile uses 131072 context tokens to preserve KV cache headroom on
24 GB VRAM. The 5090 profiles use the full 262144 native context. If `ollama ps`
shows CPU offload on the 35B profile, drop to 131072 or 98304.

## Sampling

Per the Qwen team's published guidance:

```
# Thinking mode - general tasks (default)
temperature        1.0
top_p              0.95
top_k              20
min_p              0.0
presence_penalty   1.5
repetition_penalty 1.0

# Thinking mode - precise coding (e.g. WebDev)
temperature        0.6
top_p              0.95
top_k              20
presence_penalty   0.0

# Instruct (non-thinking) mode
temperature        0.7
top_p              0.80
top_k              20
presence_penalty   1.5
```

To disable thinking, pass `enable_thinking=False` via `chat_template_kwargs`.
For agent scenarios on 35B-A3B, preserve thinking across turns with
`chat_template_kwargs={"preserve_thinking": True}`.

## Notes

The profiles use known-good Ollama Q4_K_M sources as compatibility fallbacks.
Direct HF NVFP4/GGUF imports have produced malformed template or projector
artifacts on Ollama 0.23.x.
