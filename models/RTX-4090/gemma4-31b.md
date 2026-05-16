# Gemma 4 31B - RTX 4090 (24 GB VRAM)

> Gemma 4 31B dense, vision + native tool calling, 64K context (tight fit on 24 GB).

Local profile for the RTX 4090 (24 GB Ada Lovelace). Q4_K_M GGUF via Ollama.
NVFP4 not used: Ada Lovelace tensor cores do not support FP4 (Blackwell-only).
NVIDIA does publish `nvidia/Gemma-4-31B-IT-NVFP4` for Blackwell hardware -
see the matching 5090 profile.

## Summary

| Field | Value |
|---|---|
| Upstream | `google/gemma-4-31B-it` |
| Family | Gemma 4 (Google) |
| Architecture | Dense |
| Params | ~31B (33B on HF card) |
| Modalities | Text + Image (vision) |
| Languages | 140+ |
| Tool calling | Native (structured JSON) |
| Native context | 128K |
| License | Gemma Terms of Use |
| Local quantization | Q4_K_M (~19 GB on disk) |
| KV cache | q8_0 |
| Local `num_ctx` | **65536 (64K)** |

## Why 64K on a 4090 (and not larger)

Dense 31B at Q4_K_M is roughly 19 GB. Subtract OS overhead and you have
~4 GB left for KV cache on a 24 GB 4090. q8_0 at 64K is the realistic
ceiling here; anything above will overflow into system RAM. This model
is genuinely happier on the 5090 - see the RTX-5090 profile.

If `ollama ps` shows any CPU%:

1. Drop `num_ctx` to 32K
2. Or switch the KV cache to `q4_0`

## Sampling

```
temperature   1.0
top_p         0.95
top_k         64
```

Set via `/set parameter` or pass from your client.

## Build & run

```bash
ollama create odytrice/gemma4-31b:4090 -f Modelfile.gemma4-31b
ollama run    odytrice/gemma4-31b:4090
ollama push   odytrice/gemma4-31b:4090
```

## Strengths (vs the 26B MoE)

- Best reasoning in the Gemma 4 family
- Top MMLU Pro / AIME / Codeforces numbers for a single-GPU dense model
- Same vision + native tool calling as the 26B A4B

## Trade-offs on RTX 4090

- Dense ~31B is slower per token than the 4B-active MoE 26B
- KV cache budget is severely limited - 64K is the practical max
- If you need >64K context on 24 GB, prefer Gemma 4 26B (A4B MoE)

## See also

- Gemma 4 26B A4B MoE card (same folder) - faster sibling on the same card
- 32 GB profile for the same model (RTX 5090 folder) - much more KV headroom
- 24 GB tier guide at the repo root
- Hugging Face: https://huggingface.co/google/gemma-4-31B-it
