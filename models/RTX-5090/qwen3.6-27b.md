# Qwen 3.6 27B - RTX 5090 (32 GB VRAM)

> Qwen 3.6 27B dense, multimodal (text + image + video), thinking + native tool calling, 190K context (262K native), NVFP4-ready on Blackwell.

Local profile for the RTX 5090 (32 GB Blackwell). Currently Q4_K_M GGUF
via Ollama. Target: NVFP4 once Ollama supports it natively -
`unsloth/Qwen3.6-27B-NVFP4` and `Qwen/Qwen3.6-27B-FP8` already exist
upstream for Blackwell hardware.

## Summary

| Field | Value |
|---|---|
| Upstream | `Qwen/Qwen3.6-27B` |
| NVFP4 source | `unsloth/Qwen3.6-27B-NVFP4` |
| Family | Qwen 3.6 (Alibaba) |
| Architecture | Dense |
| Params | ~27-28B |
| Modalities | Text + Image + Video (vision) |
| Languages | 100+ |
| Tool calling | Native (`qwen3_coder` parser) |
| Thinking mode | Default on; togglable via `enable_thinking` |
| Native context | 262,144 (extensible to 1,010,000 via YaRN) |
| License | Apache 2.0 |
| Local quantization | Q4_K_M today (~17 GB), NVFP4 future |
| KV cache | q8_0 |
| Local `num_ctx` | **190000** |

## Why 190000 here

Mirrors the xeon-ai gateway config exactly. With ~17 GB Q4 weights and
32 GB VRAM, q8_0 KV cache for 190K context fits with reasonable headroom
on the 5090. Below the model's 262K native window - no YaRN scaling needed.

## Sampling

Per the Qwen team's published guidance:

```
# Thinking mode - general tasks (default)
temperature        1.0
top_p              0.95
top_k              20
min_p              0.0
presence_penalty   1.5

# Thinking mode - precise coding
temperature        0.6
top_p              0.95
top_k              20
presence_penalty   0.0

# Instruct (non-thinking) mode
temperature        0.7
top_p              0.80
top_k              20
presence_penalty   1.5
```

To disable thinking: `chat_template_kwargs={"enable_thinking": False}`.

## Build & run

```bash
ollama create odytrice/qwen3.6-27b:5090 -f Modelfile.qwen3.6-27b
ollama run    odytrice/qwen3.6-27b:5090
ollama push   odytrice/qwen3.6-27b:5090
```

## Strengths

- Full 190K context - matches gateway expectations, well below 262K native
- Native vision (text + image + video input)
- Strong tool calling (OpenCode / Aider / Cline via `qwen3_coder`)
- Thinking mode for heavier reasoning workloads
- 100+ languages
- Apache 2.0 licensed

## See also

- Qwen 3.6 35B A3B MoE card (same folder) - MoE sibling on the same card
- 24 GB profile for the same model (RTX 4090 folder) - 64K ctx
- 32 GB tier guide at the repo root
- Hugging Face: https://huggingface.co/Qwen/Qwen3.6-27B
- Hugging Face NVFP4: https://huggingface.co/unsloth/Qwen3.6-27B-NVFP4
