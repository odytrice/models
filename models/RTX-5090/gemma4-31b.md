# Gemma 4 31B - RTX 5090 (32 GB VRAM)

> Gemma 4 31B dense, vision + native tool calling, 153K context, NVFP4-ready on Blackwell.

Local profile for the RTX 5090 (32 GB Blackwell). Currently Q4_K_M GGUF
via Ollama. Target: NVFP4 once Ollama supports it natively - the
quantized checkpoint already exists upstream as `nvidia/Gemma-4-31B-IT-NVFP4`.

## Summary

| Field | Value |
|---|---|
| Upstream | `google/gemma-4-31B-it` |
| NVFP4 source | `nvidia/Gemma-4-31B-IT-NVFP4` |
| Family | Gemma 4 (Google) |
| Architecture | Dense |
| Params | ~31B (33B on HF card) |
| Modalities | Text + Image (vision) |
| Languages | 140+ |
| Tool calling | Native |
| Native context | 128K |
| License | Gemma Terms of Use |
| Local quantization | Q4_K_M today (~19 GB), NVFP4 future |
| KV cache | q8_0 |
| Local `num_ctx` | **153600** |

## Why 153600 here

Mirrors the xeon-ai gateway config. On a 32 GB 5090, ~19 GB of Q4 weights
plus q8_0 KV cache for ~150K context fits with overhead. Note this
exceeds the model's nominal 128K - YaRN-style RoPE extension applies
beyond that.

## Sampling

```
temperature   1.0
top_p         0.95
top_k         64
```

## Build & run

```bash
ollama create odytrice/gemma4-31b:5090 -f Modelfile.gemma4-31b
ollama run    odytrice/gemma4-31b:5090
ollama push   odytrice/gemma4-31b:5090
```

## Strengths

- Best reasoning in the Gemma 4 family (MMLU Pro, AIME, Codeforces leader)
- Native vision + tool calling
- 153K context with room to spare on Blackwell
- Gemma Terms - commercial use permitted
- NVFP4 path already exists upstream (NVIDIA-published)

## Trade-offs

- Dense ~31B - slower per token than the A4B MoE 26B
- If maximum throughput is the priority, use `gemma4-26b:5090` instead

## See also

- Gemma 4 26B A4B MoE card (same folder) - faster sibling, same context
- 24 GB profile for the same model (RTX 4090 folder) - 64K ctx
- 32 GB tier guide at the repo root
- Hugging Face: https://huggingface.co/google/gemma-4-31B-it
- Hugging Face NVFP4: https://huggingface.co/nvidia/Gemma-4-31B-IT-NVFP4
