# Gemma 4 12B

> Gemma 4 12B instruction model with vision, audio, thinking, and native tool calling.

Shared model card for `odytrice/gemma4-12b:4090` and `odytrice/gemma4-12b:5090`.
Ollama's registry shares the description across tags of the same model name,
so both GPU profiles live under this one card.

## Upstream

| Field | Value |
|---|---|
| Upstream | `gemma4:12b-it` |
| Family | Gemma 4 (Google) |
| Parameters | 11.9B |
| Modalities | Text + Image + Audio |
| Tool calling | Native |
| Native context | 256K |
| License | Apache 2.0 |

## Tags

| Tag | GPU | Quantization | `num_ctx` |
|---|---|---|---|
| `odytrice/gemma4-12b:4090` | RTX 4090 (24 GB Ada) | Q8_0 (~12 GB) | 262144 |
| `odytrice/gemma4-12b:5090` | RTX 5090 (32 GB Blackwell) | BF16 | 262144 |

## Environment

Always set these before running Ollama:

```
set OLLAMA_FLASH_ATTENTION=1

export OLLAMA_FLASH_ATTENTION=1
```

## Sampling

Gemma 4 defaults from Ollama:

```
temperature   1.0
top_p         0.95
top_k         64
```

Set via `/set parameter` inside `ollama run` or pass as request options
from your client (OpenCode, Aider, etc.). Not baked into the Modelfiles.
