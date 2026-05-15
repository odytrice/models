# Qwen 3.6 27B - RTX 5090 (32 GB VRAM)

Local profile for the RTX 5090 (32 GB Blackwell). Currently Q4_K_M GGUF
via Ollama. Target: NVFP4 once Ollama supports it natively.

> Note: `qwen3.6:27b` is not on the public Ollama library today (the live
> page lists `qwen3` 0.6B through 235B). This card describes the local
> tag you have pulled.

## Summary

| Field | Value |
|---|---|
| Family | Qwen 3.6 (Alibaba) |
| Architecture | Dense |
| Params | ~27B |
| Modalities | Text |
| Languages | 100+ |
| Tool calling | Native |
| Thinking mode | Yes (toggleable) |
| Native context | 256K class |
| License | Apache 2.0 |
| Local quantization | Q4_K_M (~17 GB) |
| Future target | NVFP4 |
| KV cache | q8_0 |
| Local `num_ctx` | **190000** |

## Why 190000 here

Mirrors the gateway (`xeon-ai`) config exactly. With ~17 GB of Q4 weights
and 32 GB of VRAM, q8_0 KV cache for 190K context fits with reasonable
overhead headroom on the 5090.

## Sampling

Non-thinking mode (default for code agents):

```
temperature       0.7
top_p             0.8
top_k             20
repeat_penalty    1.05
```

Thinking mode (heavier reasoning):

```
temperature       0.6
top_p             0.95
```

## Build & run

```bash
ollama create odytrice/qwen3.6-27b:5090 -f Modelfile.qwen3.6-27b
ollama run    odytrice/qwen3.6-27b:5090
ollama push   odytrice/qwen3.6-27b:5090
```

## Strengths

- Full 190K context - matches gateway expectations
- Strong tool calling (OpenCode / Aider / Cline)
- Reasoning via thinking mode when needed
- Multilingual

## See also

- `qwen3.6-35b.md` - larger sibling on the same card
- `../RTX-4090/qwen3.6-27b.md` - 24 GB profile (64K ctx)
- `../../32GB-GPU.md`
- Ollama Qwen 3 upstream: https://ollama.com/library/qwen3
