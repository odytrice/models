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
| Native context | 256K |
| License | Gemma Terms of Use |

## Tags

| Tag | GPU | Quantization | KV cache | `num_ctx` |
|---|---|---|---|---|
| `odytrice/gemma4-26b:4090` | RTX 4090 (24 GB Ada) | Q4_K_M (~17 GB) | q4_0 | 131072 |
| `odytrice/gemma4-26b:5090` | RTX 5090 (32 GB Blackwell) | Ollama Q4_K_M (~17 GB) | q4_0 | 131072 |

### Why this context size

The 5090 profile uses the same known-good Ollama Q4_K_M artifact as the
4090 profile, with 131072 (128K) context and q4_0 KV cache. The direct HF
UD-Q6_K import currently fails to load on the remote Ollama 0.23.x server.

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

- 4090: 131072 at q4_0 KV cache fits on 24 GB; verify with `ollama ps`;
  no FP4 tensor-core acceleration on Ada
- 5090: Ollama Q4_K_M compatibility fallback with 131072 context; verify
  full GPU offload with `ollama ps`

## See also

- Hugging Face: https://huggingface.co/google/gemma-4-26B-A4B-it
- Hugging Face GGUF: https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF
- Hugging Face NVFP4: https://huggingface.co/nvidia/Gemma-4-26B-A4B-NVFP4
- 24 GB tier guide at the repo root
- 32 GB tier guide at the repo root
