# Gemma 4 31B

> Gemma 4 31B dense, vision + native tool calling.

Model card for `odytrice/gemma4-31b:5090`. The dense 31B profile does not
leave usable KV cache headroom on a 24 GB 4090, so only a 5090 profile is
provided.

## Upstream

| Field | Value |
|---|---|
| Upstream | `google/gemma-4-31B-it` |
| NVFP4 source | `nvidia/Gemma-4-31B-IT-NVFP4` |
| Family | Gemma 4 (Google) |
| Architecture | Dense |
| Params | ~31B (33B on HF card) |
| Modalities | Text + Image (vision) |
| Languages | 140+ |
| Tool calling | Native (structured JSON) |
| Native context | 256K |
| License | Gemma Terms of Use |

## Tags

| Tag | GPU | Quantization | KV cache | `num_ctx` |
|---|---|---|---|---|
| `odytrice/gemma4-31b:5090` | RTX 5090 (32 GB Blackwell) | Ollama Q4_K_M (~19 GB) | q4_0 | 153600 |

### Why this context size

153600 mirrors the earlier 5090 gateway profile while using the known-good
Ollama Q4_K_M artifact. It remains within the model's native 256K window -
no YaRN scaling needed. The direct HF NVFP4-GGUF import currently fails to
load on the remote Ollama 0.23.x server.

If `ollama ps` shows CPU% on the 4090 tag: drop `num_ctx` to 32K or switch
KV cache to `q4_0`.

## Environment

Always set these before running this dense profile:

```
set OLLAMA_KV_CACHE_TYPE=q4_0    # Windows
set OLLAMA_FLASH_ATTENTION=1

export OLLAMA_KV_CACHE_TYPE=q4_0   # Linux/macOS
export OLLAMA_FLASH_ATTENTION=1
```

## Sampling

```
temperature   1.0
top_p         0.95
top_k         64
```

Set via `/set parameter` or pass from your client.

## Strengths

- Best reasoning in the Gemma 4 family (MMLU Pro, AIME, Codeforces leader)
- Native vision + native tool calling
- 140+ languages
- Gemma Terms permit commercial use

## Caveats

- Dense ~31B is slower per token than the A4B MoE 26B variant
- Ollama Q4_K_M compatibility fallback; the direct HF NVFP4-GGUF import
  currently fails to load on the remote Ollama 0.23.x server

## See also

- Gemma 4 26B A4B MoE card - faster A4B MoE sibling
- Hugging Face: https://huggingface.co/google/gemma-4-31B-it
- Hugging Face GGUF: https://huggingface.co/unsloth/gemma-4-31B-it-GGUF
- Hugging Face NVFP4-GGUF: https://huggingface.co/LibertAIDAI/Gemma-4-31B-IT-NVFP4-GGUF
- Hugging Face NVFP4: https://huggingface.co/nvidia/Gemma-4-31B-IT-NVFP4
- 32 GB tier guide at the repo root
