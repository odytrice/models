# Gemma 4 26B

> Gemma 4 26B-A4B (MoE, ~26B total / 4B active), vision + native tool calling.

Shared model card for `odytrice/gemma4-26b:4090` and `odytrice/gemma4-26b:5090`.
Ollama's registry shares the description across tags of the same model name,
so both GPU profiles live under this one card.

## Upstream

| Field | Value |
|---|---|
| Upstream | `google/gemma-4-26B-A4B-it` |
| NVFP4 source | `nvidia/Gemma-4-26B-A4B-NVFP4` |
| Family | Gemma 4 (Google) |
| Architecture | Mixture-of-Experts (A4B) |
| Total / Active params | ~26B / 4B |
| Modalities | Text + Image (vision) |
| Languages | 140+ |
| Tool calling | Native (structured JSON) |
| Native context | 128K |
| License | Gemma Terms of Use |

## Tags

| Tag | GPU | Quantization | KV cache | `num_ctx` |
|---|---|---|---|---|
| `odytrice/gemma4-26b:4090` | RTX 4090 (24 GB Ada) | Q4_K_M (~17 GB) | q8_0 | 65536 (64K) |
| `odytrice/gemma4-26b:5090` | RTX 5090 (32 GB Blackwell) | Q4_K_M (~17 GB), NVFP4 future | q8_0 | 153600 |

### Why these context sizes

- **4090 (64K):** With ~17 GB Q4 weights plus OS overhead, only ~6 GB remains
  for the KV cache on 24 GB. q8_0 at 64K fits with headroom; 128K is
  borderline and likely to spill to CPU.
- **5090 (153600):** Matches the xeon-ai gateway config exactly. 32 GB
  comfortably holds the weights plus q8_0 KV cache for ~150K context. Note
  this exceeds the model's nominal 128K - YaRN-style RoPE extension applies.

If `ollama ps` shows any CPU%, drop `num_ctx` or switch KV cache to `q4_0`.

## Sampling

Gemma 4 sampling differs from the Qwen-style defaults used elsewhere in
this repo:

```
temperature   1.0
top_p         0.95
top_k         64
```

Set via `/set parameter` inside `ollama run` or pass as request options
from your client (OpenCode, Aider, etc.). Not baked into the Modelfiles.

## Build & run

```bash
# 4090 profile
ollama create odytrice/gemma4-26b:4090 -f RTX-4090/Modelfile.gemma4-26b
ollama run    odytrice/gemma4-26b:4090

# 5090 profile
ollama create odytrice/gemma4-26b:5090 -f RTX-5090/Modelfile.gemma4-26b
ollama run    odytrice/gemma4-26b:5090

# Push to registry (both share the model page)
ollama push   odytrice/gemma4-26b:4090
ollama push   odytrice/gemma4-26b:5090
```

Or use the deploy script in this folder:

```bash
./deploy.ps1 -Filter gemma4-26b    # PowerShell
./deploy.sh  --filter gemma4-26b   # bash
```

Verify 100% GPU offload after loading:

```bash
ollama ps
```

## Strengths

- MoE with only ~4B active params -> fast inference (~150 tok/s class on Ada)
- Native vision input (Image-Text-to-Text)
- Native structured-JSON tool calling
- 140+ language coverage
- Gemma Terms permit commercial use

## Caveats

- 4090: KV cache budget is tight - keep `num_ctx` at 64K; no FP4 tensor-core
  acceleration on Ada
- 5090: 153K exceeds the model's nominal 128K - some quality degradation
  past 128K is expected via YaRN
- NVFP4 weights exist upstream but Ollama does not yet load them; the
  5090 tag will pivot when support lands

## See also

- Hugging Face: https://huggingface.co/google/gemma-4-26B-A4B-it
- Hugging Face NVFP4: https://huggingface.co/nvidia/Gemma-4-26B-A4B-NVFP4
- 24 GB tier guide at the repo root
- 32 GB tier guide at the repo root
