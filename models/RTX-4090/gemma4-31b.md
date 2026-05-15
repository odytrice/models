# Gemma 4 31B - RTX 4090 (24 GB VRAM)

Local profile for the RTX 4090 (24 GB Ada Lovelace). Q4_K_M GGUF via Ollama.
NVFP4 not used - Ada Lovelace tensor cores do not support FP4 (Blackwell-only).

> Note: `gemma4:31b` is not currently published on the public Ollama library
> (the live page covers `gemma3` up to 27B). This card describes the local
> tag you have pulled. Upstream details below extrapolate from the Gemma 3
> family and the project's existing `32GB-GPU.md` notes.

## Summary

| Field | Value |
|---|---|
| Family | Gemma 4 (Google) |
| Architecture | Dense |
| Params | 30.7B |
| Modalities | Text + Image (vision) |
| Languages | 140+ |
| Tool calling | Native (structured JSON) |
| Native context | 256K |
| License | Gemma Terms of Use |
| Local quantization | Q4_K_M (~19 GB on disk) |
| KV cache | q8_0 |
| Local `num_ctx` | **65536 (64K)** |

## Why 64K on a 4090 (and not larger)

Dense 31B at Q4_K_M is roughly 19 GB. Subtract OS overhead and you have
~4 GB left for KV cache on a 24 GB 4090. q8_0 at 64K is the realistic
ceiling here; anything above will overflow into system RAM and tank
throughput. This model is genuinely happier on the 5090 - see
`../RTX-5090/gemma4-31b.md`.

If `ollama ps` shows any CPU%:

1. Drop `num_ctx` to 32K
2. Or switch the KV cache to `q4_0`

## Sampling

```
temperature   1.0
top_p         0.95
top_k         64
```

Set via `/set parameter` in an `ollama run` session or pass as request
options from your client.

## Build & run

```bash
ollama create odytrice/gemma4-31b:4090 -f Modelfile.gemma4-31b
ollama run    odytrice/gemma4-31b:4090
ollama push   odytrice/gemma4-31b:4090
```

## Strengths (vs 26B MoE)

- Best reasoning in the Gemma 4 family
- Top MMLU Pro, AIME, Codeforces numbers for a single-GPU model
- Same vision + tool calling as the 26B

## Trade-offs on RTX 4090

- Dense 30.7B is slower per token than the MoE 26B
- KV cache budget is severely limited - 64K is the practical max
- If you need >64K context on 24 GB, prefer Gemma 4 26B (MoE)

## See also

- `gemma4-26b.md` - faster MoE variant on the same card
- `../RTX-5090/gemma4-31b.md` - 32 GB profile (much more KV headroom)
- `../../24GB-GPU.md`
- Ollama Gemma 3 upstream: https://ollama.com/library/gemma3
