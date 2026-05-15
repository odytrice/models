# Gemma 4 26B - RTX 5090 (32 GB VRAM)

Local profile for the RTX 5090 (32 GB Blackwell). Currently Q4_K_M GGUF
via Ollama. Target: NVFP4 once Ollama supports it natively (Blackwell
tensor cores accelerate FP4; will pivot the `FROM` source when available).

> Note: `gemma4:26b` is not on the public Ollama library today (the live
> page covers `gemma3` up to 27B). This card describes the local tag you
> have pulled and extrapolates from the Gemma 3 family page.

## Summary

| Field | Value |
|---|---|
| Family | Gemma 4 (Google) |
| Architecture | Mixture-of-Experts (MoE) |
| Total / Active params | 25.2B / 3.8B |
| Modalities | Text + Image (vision) |
| Languages | 140+ |
| Tool calling | Native (structured JSON) |
| Native context | 256K |
| License | Gemma Terms of Use |
| Local quantization | Q4_K_M (~17 GB) |
| Future target | NVFP4 (Blackwell-accelerated) |
| KV cache | q8_0 |
| Local `num_ctx` | **153600** |

## Why 153600 here

This matches the gateway (`xeon-ai`) config exactly so the local Ollama
tag mirrors the limits the rest of your stack is expecting. The 5090's
32 GB is enough to hold ~17 GB of weights plus the q8_0 KV cache for
150K-class context with headroom for compute buffers.

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
- Same MoE speed advantage (~3.8B active params)
- Headroom for FP4 acceleration once Ollama exposes it on Blackwell

## See also

- `../RTX-4090/gemma4-26b.md` - 24 GB profile (64K ctx)
- `../../32GB-GPU.md` - generic 32 GB tier guidance
- Ollama Gemma 3 upstream: https://ollama.com/library/gemma3
