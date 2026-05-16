# Qwen 3.6 27B

> Qwen 3.6 27B dense, multimodal (text + image + video), thinking + native tool calling, 262K native context.

Shared model card for `odytrice/qwen3.6-27b:4090` and `odytrice/qwen3.6-27b:5090`.
Ollama's registry shares the description across tags of the same model name,
so both GPU profiles live under this one card.

## Upstream

| Field | Value |
|---|---|
| Upstream | `Qwen/Qwen3.6-27B` |
| NVFP4 source | `unsloth/Qwen3.6-27B-NVFP4` |
| FP8 source | `Qwen/Qwen3.6-27B-FP8` |
| Family | Qwen 3.6 (Alibaba) |
| Architecture | Dense |
| Params | ~27-28B |
| Modalities | Text + Image + Video (vision) |
| Languages | 100+ |
| Tool calling | Native (`qwen3_coder` parser in vLLM/SGLang) |
| Thinking mode | Default on; togglable via `enable_thinking` |
| Native context | 262,144 (extensible to 1,010,000 via YaRN) |
| License | Apache 2.0 |

## Tags

| Tag | GPU | Quantization | KV cache | `num_ctx` |
|---|---|---|---|---|
| `odytrice/qwen3.6-27b:4090` | RTX 4090 (24 GB Ada) | Q4_K_M (~17 GB) | q8_0 | 65536 (64K) |
| `odytrice/qwen3.6-27b:5090` | RTX 5090 (32 GB Blackwell) | Q4_K_M (~17 GB), NVFP4 future | q8_0 | 190000 |

### Why these context sizes

- **4090 (64K):** The xeon-ai gateway config calls for 190K, but on 24 GB
  that would need ~30 GB of KV cache at q8_0 alone - infeasible. 64K is
  the realistic ceiling with ~17 GB Q4 weights.
- **5090 (190000):** Mirrors the xeon-ai gateway config exactly. 32 GB
  comfortably fits the weights plus q8_0 KV cache for 190K context. Below
  the model's 262K native window - no YaRN scaling required.

If `ollama ps` shows CPU% on the 4090 tag: drop to 32K or switch KV cache
to `q4_0`.

## Sampling

Per the Qwen team's published guidance:

```
# Thinking mode - general tasks (default)
temperature        1.0
top_p              0.95
top_k              20
min_p              0.0
presence_penalty   1.5
repetition_penalty 1.0

# Thinking mode - precise coding (e.g. WebDev)
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

To disable thinking: pass `enable_thinking=False` via
`chat_template_kwargs` (vLLM/SGLang).

## Build & run

```bash
# 4090 profile
ollama create odytrice/qwen3.6-27b:4090 -f RTX-4090/Modelfile.qwen3.6-27b
ollama run    odytrice/qwen3.6-27b:4090

# 5090 profile
ollama create odytrice/qwen3.6-27b:5090 -f RTX-5090/Modelfile.qwen3.6-27b
ollama run    odytrice/qwen3.6-27b:5090

ollama push   odytrice/qwen3.6-27b:4090
ollama push   odytrice/qwen3.6-27b:5090
```

Or use the deploy script:

```bash
./deploy.ps1 -Filter qwen3.6-27b
./deploy.sh  --filter qwen3.6-27b
```

## Strengths

- Strong reasoning + coding balance in the dense 27B band
- Native vision: text + image + video input
- Native tool calling (`qwen3_coder` parser)
- Thinking / non-thinking mode toggle
- 262K native context (gated only by VRAM here)
- 100+ languages
- Apache 2.0 licensed

## Caveats

- 4090 cannot reach the 190K gateway target - capped at 64K
- 5090 stays inside native 262K window; no quality degradation expected
- NVFP4 weights exist upstream but Ollama does not yet load them

## See also

- `qwen3.6-35b.md` - A3B MoE sibling (35B total / 3B active)
- Hugging Face: https://huggingface.co/Qwen/Qwen3.6-27B
- Hugging Face NVFP4: https://huggingface.co/unsloth/Qwen3.6-27B-NVFP4
- Hugging Face FP8: https://huggingface.co/Qwen/Qwen3.6-27B-FP8
- 24 GB tier guide at the repo root
- 32 GB tier guide at the repo root
