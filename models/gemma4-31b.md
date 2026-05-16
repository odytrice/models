# Gemma 4 31B

> Gemma 4 31B dense, vision + native tool calling.

Shared model card for `odytrice/gemma4-31b:4090` and `odytrice/gemma4-31b:5090`.
Ollama's registry shares the description across tags of the same model name,
so both GPU profiles live under this one card.

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
| Native context | 128K |
| License | Gemma Terms of Use |

## Tags

| Tag | GPU | Quantization | KV cache | `num_ctx` |
|---|---|---|---|---|
| `odytrice/gemma4-31b:4090` | RTX 4090 (24 GB Ada) | Q4_K_M (~19 GB) | q8_0 | 65536 (64K) |
| `odytrice/gemma4-31b:5090` | RTX 5090 (32 GB Blackwell) | Q4_K_M (~19 GB), NVFP4 future | q8_0 | 153600 |

### Why these context sizes

- **4090 (64K):** Dense 31B at Q4_K_M is ~19 GB. Subtract OS overhead and
  ~4 GB remains for KV cache on 24 GB. q8_0 at 64K is the realistic ceiling;
  anything higher overflows into system RAM. This model is genuinely happier
  on the 5090.
- **5090 (153600):** mirrors the gateway config. 32 GB holds the
  ~19 GB weights plus q8_0 KV cache for ~150K context with overhead. Note
  this exceeds the model's nominal 128K - YaRN-style RoPE extension applies.

If `ollama ps` shows CPU% on the 4090 tag: drop `num_ctx` to 32K or switch
KV cache to `q4_0`.

## Environment

Always set these before running Ollama:

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
- 4090: severely KV-budget-limited at Q4_K_M, 64K is the practical max
- 5090: 153K exceeds the nominal 128K window - YaRN extension applies
- NVFP4 weights exist upstream but Ollama does not yet load them

## See also

- Gemma 4 26B A4B MoE card - faster A4B MoE sibling
- Hugging Face: https://huggingface.co/google/gemma-4-31B-it
- Hugging Face NVFP4: https://huggingface.co/nvidia/Gemma-4-31B-IT-NVFP4
- 24 GB tier guide at the repo root
- 32 GB tier guide at the repo root
