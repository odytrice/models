# Qwen 3.6 35B-A3B

> Qwen 3.6 35B-A3B (MoE, 35B total / 3B active, 256 experts), vision + thinking + native tool calling, 262K native context.

Model card for `odytrice/qwen3.6-35b:5090`. The 5090 is the only profile
in this set - the 35B MoE weights do not fit comfortably on a 24 GB 4090
with useful context.

## Upstream

| Field | Value |
|---|---|
| Upstream | `Qwen/Qwen3.6-35B-A3B` |
| NVFP4 sources | `unsloth/Qwen3.6-35B-A3B-NVFP4`, `RedHatAI/Qwen3.6-35B-A3B-NVFP4` |
| Family | Qwen 3.6 (Alibaba) |
| Architecture | Mixture-of-Experts (A3B) |
| Total / Active params | 35B / 3B |
| Experts | 256 (8 routed + 1 shared) |
| Layers | 40 (hybrid: Gated DeltaNet + Gated Attention + MoE) |
| Modalities | Text + Image + Video (vision) |
| Languages | 100+ |
| Tool calling | Native (`qwen3_coder` parser) |
| Thinking mode | Default on; preserves thinking traces across turns |
| Native context | 262,144 (extensible to 1,010,000 via YaRN) |
| License | Apache 2.0 |

## Tags

| Tag | GPU | Quantization | KV cache | `num_ctx` |
|---|---|---|---|---|
| `odytrice/qwen3.6-35b:5090` | RTX 5090 (32 GB Blackwell) | Ollama Q4_K_M (~23 GB) | q4_0 | 190000 |

### Why 190K (and why no 4090 tag)

- **5090 (190000):** uses the known-good Ollama Q4_K_M artifact instead
  of NVFP4 because only ~3B parameters are active per token. Below the
  262K native window and aligned with the tuned OpenCode 5090 profile.
  Verify with `ollama ps`; if CPU% appears, drop to 131072 or 98304.
- **No 4090 tag:** At ~25 GB the weights do not fit on a 24 GB card,
  leaving no headroom for KV cache. The dense Qwen 3.6 27B or Gemma 4
  26B-A4B are the practical 24 GB options.

## Environment

Always set these before running Ollama:

```
set OLLAMA_KV_CACHE_TYPE=q4_0    # Windows
set OLLAMA_FLASH_ATTENTION=1

export OLLAMA_KV_CACHE_TYPE=q4_0   # Linux/macOS
export OLLAMA_FLASH_ATTENTION=1
```

## Architecture note

The `A3B` suffix in `Qwen3.6-35B-A3B` means 3B activated parameters per
token out of 35B total. Per the Qwen team's HF card: 256 experts
(8 routed + 1 shared), 40 layers with a hybrid Gated DeltaNet + Gated
Attention + MoE layout. Considerably faster per token than the dense
31B-class models in this set.

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

Output length: 32,768 tokens default; 81,920 for hard math/code.
To preserve thinking across turns: `chat_template_kwargs={"preserve_thinking": True}`.

## Strengths

- MoE with only 3B active params - dramatically faster than dense 32B class
- Strong agentic coding (SWE-bench Verified 73.4, SWE-bench Pro 49.5,
  Terminal-Bench 2.0 51.5)
- Native vision: text + image + video input
- `preserve_thinking` for agent scenarios - retains reasoning across turns
- 100+ languages
- Apache 2.0 licensed
- Higher GGUF quant keeps MoE quality high without depending on NVFP4
  runtime support

## Caveats

- Tightest fit in the 5090 set - verify `ollama ps` before long runs
- Does not fit on a 24 GB 4090 with any usable context
- Uses the Ollama Q4_K_M source as a compatibility fallback. The direct
  HF GGUF UD-Q5_K_M import produced a malformed template/projector artifact
  on Ollama 0.23.x.
- Verify full GPU offload with `ollama ps`

## See also

- Qwen 3.6 27B card - dense sibling, lower total params, 5090 only
- Hugging Face: https://huggingface.co/Qwen/Qwen3.6-35B-A3B
- Hugging Face GGUF: https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF
- Hugging Face NVFP4 (unsloth): https://huggingface.co/unsloth/Qwen3.6-35B-A3B-NVFP4
- Hugging Face NVFP4 (Red Hat): https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-NVFP4
- 32 GB tier guide at the repo root
