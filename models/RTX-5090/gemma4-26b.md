# Gemma 4 26B - RTX 5090 (32 GB VRAM)

> Gemma 4 26B-A4B (MoE, ~26B total / 4B active), vision + native tool calling, 153K context, NVFP4-ready on Blackwell.

Local profile for the RTX 5090 (32 GB Blackwell). Currently Q4_K_M GGUF
via Ollama. Target: NVFP4 once Ollama supports it natively - the
quantized checkpoint already exists upstream as `nvidia/Gemma-4-26B-A4B-NVFP4`.

## Summary

| Field | Value |
|---|---|
| Upstream | `google/gemma-4-26B-A4B-it` |
| NVFP4 source | `nvidia/Gemma-4-26B-A4B-NVFP4` |
| Family | Gemma 4 (Google) |
| Architecture | Mixture-of-Experts (A4B) |
| Total / Active params | ~26B / 4B |
| Modalities | Text + Image (vision) |
| Languages | 140+ |
| Tool calling | Native |
| Native context | 128K |
| License | Gemma Terms of Use |
| Local quantization | Q4_K_M today (~17 GB), NVFP4 future |
| KV cache | q8_0 |
| Local `num_ctx` | **153600** |

## Why 153600 here

Matches the xeon-ai gateway config exactly so the local Ollama tag mirrors
the limits the rest of your stack expects. The 5090's 32 GB holds ~17 GB
of weights plus q8_0 KV cache for ~150K context with headroom for compute
buffers. Note this exceeds the model's nominal 128K - YaRN-style RoPE
extension applies; expect some quality degradation past 128K.

## Sampling

```
temperature   1.0
top_p         0.95
top_k         64
```

Set via `/set parameter` or pass from your client.

## Build & run

```bash
ollama create odytrice/gemma4-26b:5090 -f Modelfile.gemma4-26b
ollama run    odytrice/gemma4-26b:5090
ollama push   odytrice/gemma4-26b:5090
```

## Strengths (vs the 4090 profile)

- Full 153K context - matches gateway expectations
- Same MoE speed advantage (~4B active params)
- Headroom for FP4 tensor-core acceleration once Ollama exposes NVFP4
  on Blackwell

## See also

- 24 GB profile for the same model (RTX 4090 folder) - 64K ctx
- 32 GB tier guide at the repo root
- Hugging Face: https://huggingface.co/google/gemma-4-26B-A4B-it
- Hugging Face NVFP4: https://huggingface.co/nvidia/Gemma-4-26B-A4B-NVFP4
