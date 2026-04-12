# 24GB GPU — Local Coding Model Guide

Recommended models and configuration for GPUs with 24GB VRAM (RTX 4090, RTX 3090, RTX A5000, etc.).

> See [OLLAMA-GUIDE.md](OLLAMA-GUIDE.md) for universal setup instructions (environment variables, quantization, KV cache, context size reference).

## Target Hardware

- **VRAM:** 24GB
- **Quantization:** Q4_K_M (sweet spot), Q5_K_M (better quality if it fits)
- **KV Cache:** q8_0 (via `OLLAMA_KV_CACHE_TYPE`)
- **Inference:** Ollama

---

## Recommended Models

### Tier 1 — Best Choices

| Model | Type | Total / Active Params | Context | VRAM (Q4) | Best For |
|---|---|---|---|---|---|
| **Gemma 4 26B** | MoE | 25.2B / 3.8B | 256K | ~18 GB | Fast agentic coding, reasoning, vision, 256K context |
| **Devstral-Small-2 24B** | Dense | 24B / 24B | 256K | ~15 GB | Agentic coding, SWE-bench, repo navigation |
| **GPT-OSS 20B** | MoE | 21B / 3.6B | 128K | ~13 GB | Agentic workflows, tool use, large context headroom |
| **Qwen3-14B** | Dense | 14.8B / 14.8B | 128K | ~9 GB | Reasoning + coding with massive context headroom |

### Tier 2 — Worth Considering

| Model | Type | Total / Active Params | Context | VRAM (Q4) | Notes |
|---|---|---|---|---|---|
| Ministral 3 14B | Dense | 14B / 14B | 256K | ~9 GB | Native function calling, multimodal, small footprint |
| Llama 4 Scout 17B | MoE | 17B | 10M | ~10-12 GB | Huge context, not coding-specialized |

### Skip — 30B+ Dense Models on 24GB

**Gemma 4 31B** (30.7B dense, ~20 GB Q4 weights) fits in 24GB VRAM but leaves only ~3-4 GB for KV cache, limiting context to ~16-24K — below the 64K minimum for coding agents. It belongs on 32GB GPUs where it can use 64-96K context. See [32GB-GPU.md](32GB-GPU.md).

30B+ MoE models (Qwen3-Coder-30B-A3B, Qwen3-30B-A3B-Thinking) use ~18.6 GB for weights, leaving only ~4.4 GB for KV cache, limiting context to ~32-48K. Dense 32B models (Qwen2.5-Coder-32B, DeepSeek-R1-Distill-32B) are even worse at ~19-20 GB for weights. All belong on [32GB GPUs](32GB-GPU.md).

### Skip — Quantized 70B+ on 24GB

70B dense models at Q4 need ~35 GB. They require CPU offloading and drop to ~2-5 tok/s.

---

## Ollama Pull Commands

```bash
# Tier 1
ollama pull gemma4:26b
ollama pull devstral-small-2:24b
ollama pull gpt-oss:20b
ollama pull qwen3:14b

# Tier 2
ollama pull ministral-3:14b
```

---

## Recommended Context Size (num_ctx)

Ollama defaults to 4096 tokens. Always increase this after pulling a model.

| Model | Ollama Tag | num_ctx | Context |
|---|---|---|---|
| GPT-OSS 20B | `gpt-oss:20b` | 131072 | 128K |
| Gemma 4 26B | `gemma4:26b` | 131072 | 128K |
| Devstral-Small-2 24B | `devstral-small-2:24b` | 131072 | 128K |
| Qwen3-14B | `qwen3:14b` | 131072 | 128K |

Run the model, set the context, and save back to the same tag to update in place:

```
ollama run <model:tag>
/set parameter num_ctx <value>
/save <model:tag>
```

Verify with `ollama ps` — if you see any CPU percentage, reduce `num_ctx`.

**Note:** All Tier 1 models can reach 128K context on 24GB. Verify with `ollama ps` — if you see any CPU percentage, reduce `num_ctx`. On a [32GB GPU](32GB-GPU.md), these models can use their full native context.

---

## Benchmark Summary

| Model | LiveCodeBench v6 | MMLU Pro | Codeforces Elo | AIME 2026 | SWE-bench | ArenaHard |
|---|---|---|---|---|---|---|
| Gemma 4 26B | 77.1% | 82.6% | 1718 | 88.3% | — | — |
| Devstral-Small-2 24B | — | — | — | — | 65.8% | — |
| GPT-OSS 20B | — | — | — | Matches o3-mini | — | — |
| Qwen3-14B | — | — | — | — | — | 85.5 |

---

## VRAM Budget (24GB)

### With q8_0 KV Cache

| Component | VRAM |
|---|---|
| OS / display compositor | ~1 GB |
| Model weights (varies by model) | 9-18 GB |
| Available for KV cache + overhead | 8-14 GB |

### Max Context by Model (24GB, q8_0 KV cache)

| Model | VRAM for Weights | Remaining for KV | Approx Max Context |
|---|---|---|---|
| Qwen3-14B | ~9 GB | ~14 GB | ~128K (full) |
| GPT-OSS 20B | ~13 GB | ~10 GB | ~128K (full) |
| Devstral-Small-2 24B | ~15 GB | ~8 GB | ~128K (verified) |
| Gemma 4 26B (MoE) | ~18 GB | ~5 GB | ~128K (verified) |

All Tier 1 models reach 128K context on 24GB. Gemma 4 26B has the tightest KV budget — if `ollama ps` shows any CPU%, reduce `num_ctx` to 64K-96K or switch to `q4_0` KV cache.

### Verify with `ollama ps`

After loading a model, check VRAM usage and GPU offload:

```bash
ollama ps
```

Should show **100% GPU**. If you see any CPU percentage, reduce `num_ctx` or switch to `q4_0` KV cache. See [OLLAMA-GUIDE.md](OLLAMA-GUIDE.md#verifying-gpu-offload-and-vram-usage) for details.

---

## OpenCode Configuration

### Recommended model pairing

- **Primary:** `devstral-small-2:24b` — best SWE-bench in class (65.8%), purpose-built for agentic coding
- **Speed + reasoning:** `gemma4:26b` — fastest Tier 1 model (~150 tok/s), strongest benchmarks, with vision
- **Reasoning fallback:** `qwen3:14b` — complex problems requiring step-by-step thinking

### Known issues

- If tool calls generate JSON but never execute, increase `num_ctx` to 16K-32K+
- Q5_K_M quantization is the quality sweet spot if VRAM allows
- Gemma 4 sampling: use `temperature=1.0`, `top_p=0.95`, `top_k=64` (different from other models)
- Gemma 4 26B on 24GB at 128K is tight — if `ollama ps` shows any CPU%, reduce `num_ctx` to 64K-96K or switch to `q4_0` KV cache

### Inference settings

| Model | temperature | top_p | top_k | repetition_penalty |
|---|---|---|---|---|
| GPT-OSS / Devstral / Qwen | 0.7 | 0.8 | 20 | 1.05 |
| Gemma 4 | 1.0 | 0.95 | 64 | — |

---

## Model Selection Guide

| Task | Use This |
|---|---|
| Day-to-day coding with OpenCode/Aider | GPT-OSS 20B or Devstral-Small-2 24B |
| Hard algorithmic / debugging problems | Qwen3-14B |
| Need speed or large context headroom | GPT-OSS 20B or Qwen3-14B |
| Multi-file repo edits | Devstral-Small-2 24B |
| Fast agentic coding with vision | Gemma 4 26B |
| General coding + tool calling | Devstral-Small-2 24B |
| Small footprint utility tasks | Ministral 3 14B |

## Gemma 4 26B Notes

Gemma 4 is a significant upgrade over Gemma 3 — it adds **native function calling** (previously Gemma 3 was prompt-based only and excluded from this guide). Key details:

- **MoE architecture:** 25.2B total params, only 3.8B active per token → very fast inference (~150 tok/s on RTX 4090)
- **Vision support:** All Gemma 4 models accept image input natively (variable resolution with 70-1120 token budgets)
- **Thinking mode:** Configurable via `<|think|>` token in system prompt — outputs `<|channel>thought\n...<channel|>` reasoning blocks
- **Tool calling:** Native structured JSON function calling, compatible with OpenCode/Aider/Cline
- **Context budget on 24GB:** With ~18 GB Q4 weights, only ~5 GB remains for KV cache → **cap `num_ctx` at 32K-64K** and verify with `ollama ps`
- **Arena AI rank:** #6 among all open models (score 1441), outperforming models 20x its active parameter count
- **Apache 2.0 license:** Fully permissive for commercial use
