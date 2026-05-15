# Qwen 3.6 35B - RTX 5090 (32 GB VRAM)

Local profile for the RTX 5090 (32 GB Blackwell). Currently Q4_K_M GGUF
via Ollama. Target: NVFP4 once Ollama supports it natively.

> Note: `qwen3.6:35b` is not on the public Ollama library today (the live
> page lists `qwen3` up to 32B / 235B MoE). This card describes the local
> tag you have pulled.

## Summary

| Field | Value |
|---|---|
| Family | Qwen 3.6 (Alibaba) |
| Architecture | Dense |
| Params | ~35B |
| Modalities | Text |
| Languages | 100+ |
| Tool calling | Native |
| Thinking mode | Yes (toggleable) |
| Native context | 256K class |
| License | Apache 2.0 |
| Local quantization | Q4_K_M (~23 GB) |
| Future target | NVFP4 |
| KV cache | q8_0 |
| Local `num_ctx` | **190000** |

## Why 190000 here

Mirrors the gateway (`xeon-ai`) config. With ~23 GB of Q4 weights and
32 GB of VRAM, q8_0 KV cache for 190K context is feasible - though it is
the tightest fit in this folder. Verify with `ollama ps`; if any CPU
percentage shows up, either drop `num_ctx` (e.g. 131072 or 153600) or
switch the KV cache to `q4_0`.

## Sampling

Non-thinking mode:

```
temperature       0.7
top_p             0.8
top_k             20
repeat_penalty    1.05
```

Thinking mode:

```
temperature       0.6
top_p             0.95
```

## Build & run

```bash
ollama create odytrice/qwen3.6-35b:5090 -f Modelfile.qwen3.6-35b
ollama run    odytrice/qwen3.6-35b:5090
ollama push   odytrice/qwen3.6-35b:5090
```

## Strengths

- Largest single-GPU Qwen 3.6 in this set
- Full 190K context - matches gateway expectations
- Strong reasoning (thinking mode) + tool calling
- Multilingual

## Caveats

- Tightest fit in the 5090 folder - verify `ollama ps` before long runs
- The 26B MoE Gemma is much faster if throughput is the priority

## See also

- `qwen3.6-27b.md` - smaller sibling, more comfortable headroom
- `../../32GB-GPU.md`
- Ollama Qwen 3 upstream: https://ollama.com/library/qwen3
