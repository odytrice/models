# Qwen 3.6 27B

> Qwen 3.6 27B dense, multimodal (text + image + video), thinking + native tool calling, 262K native context.

Model card for `odytrice/qwen3.6-27b:5090`. The dense 27B profile does not
leave usable KV cache headroom on a 24 GB 4090 at any practical context
length, so only a 5090 profile is provided.

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
| `odytrice/qwen3.6-27b:5090` | RTX 5090 (32 GB Blackwell) | Ollama Q4_K_M (~17 GB) | q4_0 | 190000 |

### Why this context size

190000 matches the tuned OpenCode 5090 profile while using the known-good
Ollama Q4_K_M artifact. It stays below the model's 262K native window - no
YaRN scaling required. The direct HF NVFP4-GGUF import currently produces
a malformed template artifact on the remote Ollama 0.23.x server.

## Environment

Always set these before running this dense profile:

```
set OLLAMA_KV_CACHE_TYPE=q4_0    # Windows
set OLLAMA_FLASH_ATTENTION=1

export OLLAMA_KV_CACHE_TYPE=q4_0   # Linux/macOS
export OLLAMA_FLASH_ATTENTION=1
```

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

## Strengths

- Strong reasoning + coding balance in the dense 27B band
- Native vision: text + image + video input
- Native tool calling (`qwen3_coder` parser)
- Thinking / non-thinking mode toggle
- 262K native context (gated only by VRAM here)
- 100+ languages
- Apache 2.0 licensed

## Caveats

- Ollama Q4_K_M compatibility fallback; the direct HF NVFP4-GGUF import
  currently produces a malformed template artifact on the remote Ollama
  0.23.x server

## See also

- Qwen 3.6 35B A3B MoE card - A3B MoE sibling (35B total / 3B active)
- Hugging Face: https://huggingface.co/Qwen/Qwen3.6-27B
- Hugging Face GGUF: https://huggingface.co/unsloth/Qwen3.6-27B-GGUF
- Hugging Face NVFP4-GGUF: https://huggingface.co/s-batman/Qwen3.6-27B-NVFP4-MTP-GGUF
- Hugging Face NVFP4: https://huggingface.co/unsloth/Qwen3.6-27B-NVFP4
- Hugging Face FP8: https://huggingface.co/Qwen/Qwen3.6-27B-FP8
- 32 GB tier guide at the repo root
