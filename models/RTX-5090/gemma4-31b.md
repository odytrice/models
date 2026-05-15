# Gemma 4 31B - RTX 5090 (32 GB VRAM)

Local profile for the RTX 5090 (32 GB Blackwell). Currently Q4_K_M GGUF
via Ollama. Target: NVFP4 once Ollama supports it natively.

> Note: `gemma4:31b` is not on the public Ollama library today (the live
> page covers `gemma3` up to 27B). This card describes the local tag and
> extrapolates from the Gemma 3 family page and the project's
> `32GB-GPU.md` notes.

## Summary

| Field | Value |
|---|---|
| Family | Gemma 4 (Google) |
| Architecture | Dense |
| Params | 30.7B |
| Modalities | Text + Image (vision) |
| Languages | 140+ |
| Tool calling | Native |
| Native context | 256K |
| License | Gemma Terms of Use |
| Local quantization | Q4_K_M (~19 GB) |
| Future target | NVFP4 |
| KV cache | q8_0 |
| Local `num_ctx` | **153600** |

## Why 153600 here

Mirrors the gateway (`xeon-ai`) config. On a 32 GB 5090, ~19 GB of weights
plus q8_0 KV cache for ~150K context fits comfortably with overhead.

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

- Best reasoning in the Gemma 4 family (MMLU Pro / AIME / Codeforces lead)
- Native vision + tool calling
- 153K context with room to spare on Blackwell
- Apache 2.0-style license - commercial-friendly

## Trade-offs

- Dense 30.7B - slower per token than the MoE 26B
- If you need maximum throughput, use `gemma4-26b:5090` instead

## See also

- `gemma4-26b.md` - MoE sibling (faster, same context)
- `../RTX-4090/gemma4-31b.md` - 24 GB profile (64K ctx)
- `../../32GB-GPU.md`
- Ollama Gemma 3 upstream: https://ollama.com/library/gemma3
