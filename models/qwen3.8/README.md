# Qwen 3.8

Qwen 3.8 model profiles for Ollama under the shared `odytrice/qwen3.8` model
name. Tags encode target GPU and parameter count as `<gpu>-<size>`.

Successor to the [Qwen 3.6](../qwen3.6/README.md) 27B profiles.

## Tags

| Tag | GPU | Quantization | `num_ctx` |
|---|---|---|---|
| `odytrice/qwen3.8:4090-27b` | RTX 4090 (24 GB Ada) | Ollama Q4_K_M (~18 GB) | 131072 |
| `odytrice/qwen3.8:5090-27b` | RTX 5090 (32 GB Blackwell) | Ollama Q4_K_M (~18 GB) | 262144 |

Only 27B is published. Upstream Qwen 3.8 has no MoE sibling to the Qwen 3.6
35B-A3B, so there is no `5090-35b` equivalent.

Both GPUs use the same Q4_K_M source. The `q8_0` source is 30 GB and the `bf16`
source is 56 GB, neither of which leaves usable KV cache headroom on 32 GB, so
there is no higher-precision 5090 profile the way `gemma4:5090-12b` has one.

## Upstream

| Size | Upstream | Architecture | Modalities | Native context |
|---|---|---|---|---|
| 27B | `Qwen/Qwen3.8-27B` | Dense hybrid attention, 64 layers — `16 x (3 x (Gated DeltaNet -> FFN) -> 1 x (Gated Attention -> FFN))` | Text + Image + Video | 262144 (extensible to 1M via YaRN) |

Apache 2.0. Only 16 of the 64 layers use full Gated Attention; the other 48 are
Gated DeltaNet layers with a constant-size recurrent state. KV cache therefore
grows with context on roughly a quarter of the layers, which is why the 27B fits
the full 262144 context on a 5090 despite being 1 GB heavier than Qwen 3.6 27B.

## Environment

Always set these before running Ollama:

```
set OLLAMA_KV_CACHE_TYPE=q8_0
set OLLAMA_FLASH_ATTENTION=1

export OLLAMA_KV_CACHE_TYPE=q8_0
export OLLAMA_FLASH_ATTENTION=1
```

## Context Size

The 4090 profile uses 131072 context tokens, matching the Qwen 3.6 27B 4090
profile. This is deliberately conservative: the weights are ~18 GB against
24 GB of VRAM, but the hybrid attention layout makes the KV cache far cheaper
per token than a full-attention 27B. If `ollama ps` shows 100% GPU with room to
spare, 163840 or 196608 is likely reachable — raise it and re-check rather than
assuming. If it shows any CPU offload, drop to 98304.

The 5090 profile uses the full 262144 native context. Going beyond that requires
YaRN RoPE scaling, which these profiles do not configure.

## Sampling

Per the Qwen team's published guidance for Qwen3.8-27B:

```
# Thinking mode (default)
temperature        1.0
top_p              0.95
top_k              20
min_p              0.0
presence_penalty   0.0
repetition_penalty 1.0

# Instruct (non-thinking) mode
temperature        0.7
top_p              0.80
top_k              20
min_p              0.0
presence_penalty   1.5
repetition_penalty 1.0
```

Note the presence penalty differs from Qwen 3.6, where thinking mode used 1.5.
Qwen 3.8 thinking mode uses 0.0.

Thinking is enabled by default and emits `<think>...</think>` before the answer.
To disable it, pass `enable_thinking=False` via `chat_template_kwargs`.

## Notes

The profiles build on the default `qwen3.8:27b` Ollama tag rather than a direct
Hugging Face GGUF import, following the same compatibility precedent as the
Qwen 3.6 profiles.

`ollama show --parameters` on the built tags reports `draft_num_predict 4`, so
the default `qwen3.8:27b` source already carries draft/speculative decoding
config. Upstream also publishes a separate `qwen3.8:27b-mtp-q4_K_M` tag at the
same 18 GB, but what it changes relative to the default is not established here
— do not assume it is the only route to the MTP draft head.
