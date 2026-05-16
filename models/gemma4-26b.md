# Gemma 4 26B

> Gemma 4 26B-A4B (MoE, ~26B total / 4B active), vision + native tool calling.

Shared model card for `odytrice/gemma4-26b:4090` and `odytrice/gemma4-26b:5090`.
Ollama's registry shares the description across tags of the same model name,
so both GPU profiles live under this one card.

## Upstream

| Field | Value |
|---|---|
| Upstream | `google/gemma-4-26B-A4B-it` |
| NVFP4 source | `nvidia/Gemma-4-26B-A4B-NVFP4` |
| Family | Gemma 4 (Google) |
| Architecture | Mixture-of-Experts (A4B) |
| Total / Active params | ~26B / 4B |
| Modalities | Text + Image (vision) |
| Languages | 140+ |
| Tool calling | Native (structured JSON) |
| Native context | 128K |
| License | Gemma Terms of Use |

## Tags

| Tag | GPU | Quantization | KV cache | `num_ctx` |
|---|---|---|---|---|
| `odytrice/gemma4-26b:4090` | RTX 4090 (24 GB Ada) | Q4_K_M (~17 GB) | q8_0 | 131072 |
| `odytrice/gemma4-26b:5090` | RTX 5090 (32 GB Blackwell) | Q4_K_M (~17 GB), NVFP4 future | q8_0 | 131072 |

### Why this context size

131072 (128K) is the model's nominal native context window. Both GPU tiers
target it: the 4090 at q4_0 KV cache and the 5090 at q8_0.

## Environment

Always set these before running Ollama:

```
set OLLAMA_KV_CACHE_TYPE=q4_0    # Windows
set OLLAMA_FLASH_ATTENTION=1

export OLLAMA_KV_CACHE_TYPE=q4_0   # Linux/macOS
export OLLAMA_FLASH_ATTENTION=1
```

## Sampling

Gemma 4 sampling differs from the Qwen-style defaults used elsewhere in
this repo:

```
temperature   1.0
top_p         0.95
top_k         64
```

Set via `/set parameter` inside `ollama run` or pass as request options
from your client (OpenCode, Aider, etc.). Not baked into the Modelfiles.

## Strengths

- MoE with only ~4B active params -> fast inference (~150 tok/s class on Ada)
- Native vision input (Image-Text-to-Text)
- Native structured-JSON tool calling
- 140+ language coverage
- Gemma Terms permit commercial use

## Caveats

- 4090: 131072 at q4_0 KV cache is tight - verify with `ollama ps`; no FP4
  tensor-core acceleration on Ada
- 5090: 131072 at q8_0 fits with headroom; NVFP4 will reduce weight footprint
  further when Ollama supports it
- NVFP4 weights exist upstream but Ollama does not yet load them; the
  5090 tag will pivot when support lands

## See also

- Hugging Face: https://huggingface.co/google/gemma-4-26B-A4B-it
- Hugging Face NVFP4: https://huggingface.co/nvidia/Gemma-4-26B-A4B-NVFP4
- 24 GB tier guide at the repo root
- 32 GB tier guide at the repo root
