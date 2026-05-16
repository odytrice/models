# Qwen 3.6 35B-A3B - RTX 5090 (32 GB VRAM)

> Qwen 3.6 35B-A3B (MoE, 35B total / 3B active, 256 experts), vision + thinking + native tool calling, 190K context (262K native), NVFP4-ready on Blackwell.

Local profile for the RTX 5090 (32 GB Blackwell). Currently Q4_K_M GGUF
via Ollama. Target: NVFP4 once Ollama supports it natively -
`unsloth/Qwen3.6-35B-A3B-NVFP4` and `RedHatAI/Qwen3.6-35B-A3B-NVFP4`
already exist upstream for Blackwell hardware.

## Summary

| Field | Value |
|---|---|
| Upstream | `Qwen/Qwen3.6-35B-A3B` |
| NVFP4 source | `unsloth/Qwen3.6-35B-A3B-NVFP4`, `RedHatAI/Qwen3.6-35B-A3B-NVFP4` |
| Family | Qwen 3.6 (Alibaba) |
| Architecture | Mixture-of-Experts (A3B) |
| Total / Active params | 35B / 3B (256 experts, 8 routed + 1 shared) |
| Layers | 40 (hybrid: Gated DeltaNet + Gated Attention + MoE) |
| Modalities | Text + Image + Video (vision) |
| Languages | 100+ |
| Tool calling | Native (`qwen3_coder` parser) |
| Thinking mode | Default on; preserves thinking traces across turns |
| Native context | 262,144 (extensible to 1,010,000 via YaRN) |
| License | Apache 2.0 |
| Local quantization | Q4_K_M today (~23 GB), NVFP4 future |
| KV cache | q8_0 |
| Local `num_ctx` | **190000** |

## Why 190000 here

Mirrors the xeon-ai gateway config. With ~23 GB Q4 weights and 32 GB VRAM,
q8_0 KV cache for 190K context is feasible - though it is the tightest
fit in this folder. Below the model's 262K native window. Verify with
`ollama ps`; if any CPU% shows, drop `num_ctx` (e.g. 131072 or 153600)
or switch KV cache to `q4_0`.

## Architecture note (the key correction)

Qwen 3.6 35B is **MoE, not dense**. The `A3B` suffix in the upstream name
(`Qwen3.6-35B-A3B`) means 3B activated parameters per token out of 35B total.
Per the Qwen team's HF card: 256 experts (8 routed + 1 shared), 40 layers
with a hybrid Gated DeltaNet + Gated Attention + MoE layout. This makes it
considerably faster per token than the dense 31B-class models in the
sibling cards.

## Sampling

Per the Qwen team's published guidance:

```
# Thinking mode - general tasks (default)
temperature        1.0
top_p              0.95
top_k              20
min_p              0.0
presence_penalty   1.5

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

Recommended output length: 32,768 tokens default; 81,920 for hard math/code.
To preserve thinking across turns: `chat_template_kwargs={"preserve_thinking": True}`.

## Build & run

```bash
ollama create odytrice/qwen3.6-35b:5090 -f Modelfile.qwen3.6-35b
ollama run    odytrice/qwen3.6-35b:5090
ollama push   odytrice/qwen3.6-35b:5090
```

## Strengths

- MoE with only 3B active params - dramatically faster than dense 32B-class
- Full 190K context - matches gateway expectations, below 262K native
- Strong agentic coding (SWE-bench Verified 73.4, SWE-bench Pro 49.5,
  Terminal-Bench 2.0 51.5)
- Native vision (text + image + video input)
- `preserve_thinking` for agent scenarios - retains reasoning across turns
- 100+ languages
- Apache 2.0 licensed

## Caveats

- Tightest fit in the 5090 folder - verify `ollama ps` before long runs
- If you need maximum vision throughput on the same card, the A4B Gemma
  4 26B has even fewer active params

## See also

- Qwen 3.6 27B card (same folder) - dense sibling, lower total params
- 32 GB tier guide at the repo root
- Hugging Face: https://huggingface.co/Qwen/Qwen3.6-35B-A3B
- Hugging Face NVFP4: https://huggingface.co/unsloth/Qwen3.6-35B-A3B-NVFP4
- Hugging Face NVFP4 (Red Hat): https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-NVFP4
