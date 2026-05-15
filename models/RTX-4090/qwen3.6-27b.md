# Qwen 3.6 27B - RTX 4090 (24 GB VRAM)

Local profile for the RTX 4090 (24 GB Ada Lovelace). Q4_K_M GGUF via Ollama.
NVFP4 not used - Ada Lovelace tensor cores do not support FP4 (Blackwell-only).

> Note: `qwen3.6:27b` is not on the public Ollama library today (the live
> page lists `qwen3` 0.6B/1.7B/4B/8B/14B/30B/32B/235B). This card describes
> the local tag you have pulled. Upstream details below extrapolate from
> the Qwen 3 family page.

## Summary

| Field | Value |
|---|---|
| Family | Qwen 3.6 (Alibaba, Qwen series) |
| Architecture | Dense (assumed - Qwen 3 27B is dense in the family scheme) |
| Params | ~27B |
| Modalities | Text |
| Languages | 100+ |
| Tool calling | Native |
| Thinking mode | Yes (toggleable, like Qwen 3) |
| Native context | 256K class (190K used here per gateway config) |
| License | Apache 2.0 (Qwen 3 family default) |
| Local quantization | Q4_K_M (~17 GB on disk) |
| KV cache | q8_0 |
| Local `num_ctx` | **65536 (64K)** |

## Why 64K on a 4090

The original gateway config calls for 190K context, but on a 24 GB 4090
that would require ~30 GB of KV cache at q8_0 alone - completely impossible.
64K is the realistic ceiling with the 17 GB Q4 weights footprint.

The 5090 profile keeps the 190K target - see `../RTX-5090/qwen3.6-27b.md`.

## Sampling

Qwen 3 family recommended defaults (apply to thinking-mode-off):

```
temperature       0.7
top_p             0.8
top_k             20
repeat_penalty    1.05
```

For thinking mode, follow the upstream Qwen guidance (typically
`temperature 0.6`, `top_p 0.95`).

## Build & run

```bash
ollama create odytrice/qwen3.6-27b:4090 -f Modelfile.qwen3.6-27b
ollama run    odytrice/qwen3.6-27b:4090
ollama push   odytrice/qwen3.6-27b:4090
```

## Strengths

- Strong reasoning + coding balance in the 27B dense band
- Native tool calling (works cleanly with OpenCode / Aider / Cline)
- Thinking / non-thinking mode toggle
- Multilingual

## Caveats on RTX 4090

- Cannot reach the 190K context used by the upstream gateway - capped at 64K here
- If `ollama ps` shows any CPU%, lower to 32K or switch KV cache to `q4_0`

## See also

- `../RTX-5090/qwen3.6-27b.md` - 32 GB profile (190K context)
- `../../24GB-GPU.md`
- Ollama Qwen 3 upstream: https://ollama.com/library/qwen3
