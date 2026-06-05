# Gemma 4

Gemma 4 model profiles for Ollama under the shared `odytrice/gemma4` model name.
Tags encode target GPU and parameter count as `<gpu>-<size>`.

## Tags

| Tag | GPU | Quantization | `num_ctx` |
|---|---|---|---|
| `odytrice/gemma4:4090-12b` | RTX 4090 (24 GB Ada) | Q8_0 (~12 GB) | 262144 |
| `odytrice/gemma4:5090-12b` | RTX 5090 (32 GB Blackwell) | BF16 (~24 GB) | 262144 |
| `odytrice/gemma4:4090-26b` | RTX 4090 (24 GB Ada) | Q4_K_M (~17 GB) | 131072 |
| `odytrice/gemma4:5090-26b` | RTX 5090 (32 GB Blackwell) | Q4_K_M (~17 GB) | 262144 |
| `odytrice/gemma4:5090-31b` | RTX 5090 (32 GB Blackwell) | Q4_K_M (~19 GB) | 153600 |

## Upstream

| Size | Upstream | Architecture | Modalities | Native context |
|---|---|---|---|---|
| 12B | `google/gemma-4-12B` / `google/gemma-4-12B-it` | Dense unified | Text + Image + Audio | 256K |
| 26B | `google/gemma-4-26B-A4B-it` | MoE A4B | Text + Image | 256K |
| 31B | `google/gemma-4-31B-it` | Dense | Text + Image | 256K |

## Environment

For the 26B and 31B Q4 profiles, set KV cache quantization before running Ollama:

```
set OLLAMA_KV_CACHE_TYPE=q4_0
set OLLAMA_FLASH_ATTENTION=1

export OLLAMA_KV_CACHE_TYPE=q4_0
export OLLAMA_FLASH_ATTENTION=1
```

For 12B profiles, flash attention is still recommended:

```
set OLLAMA_FLASH_ATTENTION=1

export OLLAMA_FLASH_ATTENTION=1
```

## Sampling

Gemma 4 defaults from Ollama:

```
temperature   1.0
top_p         0.95
top_k         64
```

Set sampling via `/set parameter` inside `ollama run` or pass it as request
options from your client. Sampling is not baked into these Modelfiles.

## Notes

The 26B 5090 profile uses the known-good Ollama Q4_K_M artifact with a tuned
262144 OpenCode context and q4_0 KV cache. The 31B profile uses 153600 context
to fit the dense model on a 32 GB 5090 while staying inside the native 256K
window. The direct HF NVFP4/GGUF imports for the larger models have had loader
compatibility issues on the remote Ollama 0.23.x server.
