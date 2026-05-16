# Gemma 4 26B - RTX 4090 (24 GB VRAM)

> Gemma 4 26B-A4B (MoE, ~26B total / 4B active), vision + native tool calling, 64K context on Ada.

Local profile for the RTX 4090 (24 GB Ada Lovelace). Q4_K_M GGUF via Ollama.
NVFP4 not used: Ada Lovelace tensor cores do not support FP4 (Blackwell-only).
NVIDIA does publish `nvidia/Gemma-4-26B-A4B-NVFP4` for Blackwell hardware -
see the matching 5090 profile.

## Summary

| Field | Value |
|---|---|
| Upstream | `google/gemma-4-26B-A4B-it` |
| Family | Gemma 4 (Google) |
| Architecture | Mixture-of-Experts (A4B) |
| Total / Active params | ~26B / 4B |
| Modalities | Text + Image (vision) |
| Languages | 140+ |
| Tool calling | Native (structured JSON) |
| Native context | 128K (per Ollama tag) |
| License | Gemma Terms of Use |
| Local quantization | Q4_K_M (~17 GB on disk) |
| KV cache | q8_0 (`OLLAMA_KV_CACHE_TYPE=q8_0`) |
| Local `num_ctx` | **65536 (64K)** |

## Why 64K on a 4090

With ~17 GB of Q4 weights plus OS overhead, only ~6 GB remains for the
KV cache on a 24 GB card. At q8_0, 64K fits with headroom; 128K is borderline
and likely to spill to CPU. If `ollama ps` shows any CPU%, drop to 32K or
switch KV cache to `q4_0`.

## Sampling

Gemma 4 sampling differs from the Qwen-style 0.7/0.8/20 defaults used by
other models in this repo:

```
temperature   1.0
top_p         0.95
top_k         64
```

Set via `/set parameter` inside `ollama run` or pass as request options
from your client (OpenCode, Aider, etc.). Not baked into the Modelfile.

## Build & run

```bash
ollama create odytrice/gemma4-26b:4090 -f Modelfile.gemma4-26b
ollama run    odytrice/gemma4-26b:4090
ollama push   odytrice/gemma4-26b:4090
```

Verify 100% GPU offload:

```bash
ollama ps
```

## Strengths

- MoE with only ~4B active params -> ~150 tok/s class on Ada
- Native vision input (Image-Text-to-Text)
- Native structured-JSON tool calling
- 140+ language coverage
- Apache-style Gemma terms - commercial use permitted

## Caveats on RTX 4090

- KV cache budget is tight - keep `num_ctx` at 64K, don't push higher
  without verifying `ollama ps`
- No FP4 tensor-core acceleration on Ada; the 5090 (which can use NVFP4)
  will be meaningfully faster on the same weights

## See also

- 32 GB profile for the same model (RTX 5090 folder)
- 24 GB tier guide at the repo root
- Hugging Face: https://huggingface.co/google/gemma-4-26B-A4B-it
