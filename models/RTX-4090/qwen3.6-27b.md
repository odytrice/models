# Qwen 3.6 27B - RTX 4090 (24 GB VRAM)

> Qwen 3.6 27B dense, multimodal (text + image + video), thinking + native tool calling, 64K context on Ada.

Local profile for the RTX 4090 (24 GB Ada Lovelace). Q4_K_M GGUF via Ollama.
NVFP4 not used: Ada Lovelace tensor cores do not support FP4 (Blackwell-only).
Official NVFP4 builds (`unsloth/Qwen3.6-27B-NVFP4`, `Qwen/Qwen3.6-27B-FP8`)
exist for Blackwell - see the matching 5090 profile.

## Summary

| Field | Value |
|---|---|
| Upstream | `Qwen/Qwen3.6-27B` |
| Family | Qwen 3.6 (Alibaba) |
| Architecture | Dense |
| Params | ~27-28B |
| Modalities | Text + Image + Video (vision) |
| Languages | 100+ |
| Tool calling | Native (`qwen3_coder` parser in vLLM/SGLang) |
| Thinking mode | Default on; togglable via `enable_thinking` |
| Native context | 262,144 (extensible to 1,010,000 via YaRN) |
| License | Apache 2.0 |
| Local quantization | Q4_K_M (~17 GB on disk) |
| KV cache | q8_0 |
| Local `num_ctx` | **65536 (64K)** |

## Why 64K on a 4090

The xeon-ai gateway config calls for 190K, but on a 24 GB 4090 that
would require ~30 GB of KV cache at q8_0 alone - infeasible.
64K is the realistic ceiling with ~17 GB Q4 weights. The 5090 profile
keeps the 190K target.

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
ollama create odytrice/qwen3.6-27b:4090 -f Modelfile.qwen3.6-27b
ollama run    odytrice/qwen3.6-27b:4090
ollama push   odytrice/qwen3.6-27b:4090
```

## Strengths

- Strong reasoning + coding balance in the dense 27B band
- Native vision (text + image + video input)
- Native tool calling (`qwen3_coder` parser)
- Thinking / non-thinking mode toggle
- 262K native context (gated only by VRAM here)
- Multilingual (100+ languages)

## Caveats on RTX 4090

- Cannot reach the 190K gateway target - capped at 64K here
- If `ollama ps` shows any CPU%, lower to 32K or switch KV cache to `q4_0`

## See also

- 32 GB profile for the same model (RTX 5090 folder) - 190K context
- 24 GB tier guide at the repo root
- Hugging Face: https://huggingface.co/Qwen/Qwen3.6-27B
