# Muse

Muse Glimmer profile for Ollama, published as `odytrice/muse`.

The card name is shortened to `muse`; the upstream model is Meta's Muse
Glimmer 30B.

This card does not use the `<gpu>-<size>` tag scheme the other cards use. A
per-GPU split would be meaningless here — context is capped by the source GGUF
rather than by VRAM, so a 24 GB and a 32 GB card get the identical profile.

Meta's Apache 2.0 agentic model — distilled from Muse Spark and built for
local tool use, multi-step reasoning, and failure recovery rather than for
general chat.

## Tags

| Tag | Quantization | `num_ctx` |
|---|---|---|
| `odytrice/muse:30b` | Ollama 4-bit (~18 GB) | 131072 |
| `odytrice/muse:latest` | Ollama 4-bit (~18 GB) | 131072 |

Both tags are the same build from `30b/Modelfile`; `latest` is the convenience
alias so `ollama run odytrice/muse` works.

Ollama publishes only `30b` (~18 GB) and `30b-mlx` (~21 GB, Apple silicon);
there is no `q8_0` or `bf16` tag to build a higher-precision variant from the
way `gemma4:5090-12b` has one.

## Upstream

| Size | Upstream | Architecture | Modalities | Native context |
|---|---|---|---|---|
| 30B | `meta-models/Muse-Glimmer-30B` | Dense causal transformer, 52 layers, hidden 6656, GQA 32 query / 2 KV heads, head dim 128 | Text + Image in, text out (~1.8B ViT-G/14 encoder) | 131072 (documented up to 262144) |

~29.6B parameters, Apache 2.0.

## Environment

Always set these before running Ollama:

```
set OLLAMA_KV_CACHE_TYPE=q8_0
set OLLAMA_FLASH_ATTENTION=1

export OLLAMA_KV_CACHE_TYPE=q8_0
export OLLAMA_FLASH_ATTENTION=1
```

## Context Size

The 32:2 GQA ratio makes the KV cache unusually cheap: 2 KV heads x 128 head dim
x 2 (K and V) x 52 layers is ~26 KB per token at `q8_0` cache, so 131072 tokens
costs roughly 3.5 GB and 262144 costs roughly 7 GB. Against ~18 GB of weights
that leaves the 4090 comfortable at full native context — unlike the 27B dense
profiles, this model is not context-constrained on 24 GB.

131072 is a hard ceiling rather than a tuning choice. The packaged GGUF reports
`muse-glimmer.context_length: 131072`, and Ollama silently clamps any larger
`num_ctx` to it — a profile built with 262144 still loaded at 131072 under
`ollama ps`. Meta documents the architecture as supporting up to 262144, but
that requires RoPE scaling this GGUF does not carry (`rope.freq_base` 500000).

This is why there is one profile instead of a per-GPU pair: the extra VRAM on a
32 GB card buys nothing here. The genuine upgrade for a larger card would be a
higher-precision build — Unsloth's `UD-Q6_K_XL` at 20-22 GB — which Ollama's
library does not publish; see Notes.

Verified on a 5090: 16 GB resident, `100% GPU`, no CPU offload at 131072.
If `ollama ps` does show CPU offload, drop to 98304.

## Sampling

Meta's published defaults:

```
temperature 1.0
top_p       0.95
top_k       64
```

Note `top_k 64` — higher than the `top_k 20` used by the Qwen 3.6 / 3.8
profiles. Carrying a Qwen client config across will be wrong.

The model exposes adjustable reasoning effort (`low`, `medium`, `high`,
`xhigh`) to trade compute against answer depth. These profiles do not pin a
level; set it per request.

## Notes

The profiles build on the default `muse-glimmer:30b` Ollama tag rather than a
direct Hugging Face GGUF import, following the same compatibility precedent as
the Qwen 3.6 / 3.8 profiles.

Unsloth publishes a `UD-Q6_K_XL` build at 20-22 GB that would fit a 5090 with
room for KV cache and would be a genuine quality upgrade over 4-bit. It is a
direct HF GGUF import, which this repo has avoided after malformed template and
projector artifacts on earlier Ollama releases — worth testing, but not what
these profiles ship.
