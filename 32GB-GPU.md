# 32GB GPU — Local Coding Model Guide

Recommended models and configuration for GPUs with 32GB VRAM (RTX 5090, etc.).

> See [OLLAMA-GUIDE.md](OLLAMA-GUIDE.md) for universal setup instructions (environment variables, quantization, KV cache, context size reference).

## Target Hardware

- **VRAM:** 32GB
- **Quantization:** Ollama Q4_K_M compatibility fallbacks for current 5090 profiles
- **KV Cache:** q8_0 via `OLLAMA_KV_CACHE_TYPE`
- **Inference:** Ollama

---

## Recommended Models

### Tier 1 — Best Choices

| Model | Type | Total / Active Params | Context | 5090 Profile | Best For |
|---|---|---|---|---|---|
| **Gemma 4 31B** | Dense | 30.7B / 30.7B | 256K | Ollama Q4_K_M fallback | Best reasoning in class, vision, native function calling |
| **Gemma 4 26B** | MoE | 25.2B / 3.8B | 256K | Ollama Q4_K_M fallback | Fast agentic coding, reasoning, vision, ~150 tok/s |
| **GLM-4.7-Flash** | MoE | 30B / 3B | 200K | ~18.3 GB | Best SWE-bench in class (59.2%), fast agentic coding |
| **Qwen3-Coder 30B-A3B** | MoE | 30B / 3.3B | 256K | ~18.6 GB | Agentic coding, tool calling (OpenCode, Aider, Cline) |
| **GLM-4-32B-0414** | Dense | 32B / 32B | 128K (YaRN) | ~20 GB | Best tool calling (BFCL 69.6), general coding |
| **Qwen3 32B** | Dense | 32B / 32B | 32K (128K w/ YaRN) | ~20 GB | General + reasoning + coding (thinking/non-thinking modes) |
| **Qwen 2.5 Coder 32B** | Dense | 32B / 32B | 128K | ~19 GB | Day-to-day coding, code completion, code repair |
| **DeepSeek R1 Distill 32B** | Dense | 32B / 32B | 128K | ~19 GB | Reasoning, complex debugging, algorithmic tasks |
| **Devstral-Small-2 24B** | Dense | 24B / 24B | 256K | ~15 GB | Multi-file agentic editing, repo navigation |
| **GPT-OSS 20B** | MoE | 21B / 3.6B | 128K | ~13 GB | Lightweight agentic workflows, tool use |

### Tier 2 — Worth Considering

| Model | Type | Total / Active Params | Context | VRAM (Q4) | Notes |
|---|---|---|---|---|---|
| IBM Granite 4.0 H-Small | Hybrid MoE | 32B / 9B | 128K | ~19.5 GB | Top BFCLv3 tool calling, Apache 2.0, ISO 42001 certified |
| Nemotron 3 Nano 30B-A3B | Hybrid MoE | 31.6B / 3.5B | 128K | ~18 GB | 68.3% LiveCodeBench v6, Mamba-2 hybrid |
| Qwen3-30B-A3B-Thinking-2507 | MoE | 30B / 3.3B | 262K | ~18.6 GB | Deep reasoning with massive context headroom |
| Mistral Small 3.2 24B | Dense | 24B / 24B | 128K | ~15 GB | General coding, native tool calling |
| Qwen3-14B | Dense | 14.8B / 14.8B | 128K | ~9 GB | Fast model with tons of context headroom |

### Models That Do NOT Fit (for reference)

| Model | Total Params | Active Params | Context Window | VRAM (Q4) |
|---|---|---|---|---|
| GLM-4.7 (Full) | 355B MoE | ~32B | 200K | ~130+ GB |
| Kimi K2 | 1T MoE | 32B | 128K-256K | ~245 GB |
| DeepSeek V3.2 | 685B MoE | ~37B | 128K | ~380+ GB |

### Skip — Quantized 70B+ on 32GB

70B dense models at Q4 need ~35 GB. Even on 32GB, they require CPU offloading and drop to ~2-5 tok/s. The dense 32B and MoE models above deliver better performance while fitting entirely in VRAM.

---

## Ollama Pull Commands

```bash
# Tier 1
ollama pull gemma4:31b
ollama pull gemma4:26b
ollama pull glm-4.7-flash
ollama pull qwen3-coder:30b
ollama pull sammcj/glm-4-32b-0414
ollama pull qwen3:32b
ollama pull qwen2.5-coder:32b
ollama pull deepseek-r1:32b
ollama pull devstral-small-2:24b
ollama pull gpt-oss:20b

# Tier 2
ollama pull granite4
ollama pull nemotron-3-nano:30b
ollama pull qwen3:30b-a3b-thinking-2507-q4_K_M
ollama pull mistral-small3.2:24b
ollama pull qwen3:14b
```

---

## Benchmark Summary

| Model | SWE-Bench Verified | HumanEval | Aider Polyglot | BFCL v3 | CodeForces Elo | LiveCodeBench v6 | MMLU Pro |
|---|---|---|---|---|---|---|---|
| GLM-4.7-Flash | 59.2% | — | — | — | — | — | — |
| Qwen3-Coder-30B-A3B | 69.6% | — | 61.8% | — | — | — | — |
| Gemma 4 31B | — | — | — | — | 2150 | 80.0% | 85.2% |
| GLM-4-32B-0414 | 33.8% (Moatless) | — | — | 69.6 | — | — | — |
| Qwen3 32B | — | — | — | — | — | — | — |
| Qwen2.5-Coder-32B | — | 91.0% | 73.7% (repair) | — | — | — | — |
| DeepSeek-R1-Distill-32B | — | — | — | — | 1691 | — | — |
| GPT-OSS 20B | — | Matches o3-mini | — | — | — | — | — |
| Devstral-Small-2 24B | 68% | — | — | — | — | — | — |
| Gemma 4 26B | — | — | — | — | 1718 | 77.1% | 82.6% |
| Nemotron 3 Nano 30B-A3B | — | 78.1% | — | — | — | 68.3% | — |

---

## VRAM Budget (32GB)

### Architecture-Split 5090 Profiles

| Component | VRAM |
|---|---|
| OS / display compositor | ~1 GB |
| Model weights | Ollama Q4_K_M compatibility fallbacks |
| KV cache | q4_0 |
| Compute buffers / overhead | ~0.5 GB |
| **Total** | **verify with `ollama ps`** |

### Max Context by Model (32GB, architecture split)

| Model | VRAM for Weights | Remaining for KV | Approx Max Context |
|---|---|---|---|
| Qwen3-14B | ~9 GB | ~22 GB | ~128K (full) |
| GPT-OSS 20B | ~13 GB | ~18 GB | ~128K (full) |
| Devstral-Small-2 24B | ~15 GB | ~16 GB | ~128K+ |
| Mistral Small 3.2 24B | ~15 GB | ~16 GB | ~128K (full) |
| Gemma 4 26B (MoE, Q4_K_M fallback) | ~17 GB | tuned | 256K |
| GLM-4.7-Flash (MoE) | ~18.3 GB | ~12.7 GB | ~96-128K |
| Qwen3-Coder 30B (MoE) | ~18.6 GB | ~12.4 GB | ~96-128K |
| DeepSeek R1 32B | ~19 GB | ~12 GB | ~64-96K |
| Qwen 2.5 Coder 32B | ~19 GB | ~12 GB | ~64-96K |
| Gemma 4 31B (Q4_K_M fallback) | ~19 GB | tuned | 150K |
| Qwen 3.6 27B (Q4_K_M fallback) | ~17 GB | tuned | 190K |
| Qwen 3.6 35B-A3B (Q4_K_M fallback) | ~23 GB | tuned | 190K |
| Granite 4.0 H-Small | ~19.5 GB | ~11.5 GB | ~64-96K |
| GLM-4-32B-0414 | ~20 GB | ~11 GB | ~64-96K |
| Qwen3 32B | ~20 GB | ~11 GB | ~64-96K |

**32GB advantage:** Dense 32B models get 64-96K context here vs. only ~24-32K on 24GB GPUs. This is why 32B dense models belong on 32GB cards.

---

## Recommended Context Size (num_ctx)

Ollama defaults to 4096 tokens. Always increase this after pulling a model.

| Model | Ollama Tag | num_ctx | Context |
|---|---|---|---|
| Gemma 4 26B 5090 Q4 fallback | `odytrice/gemma4:5090-26b` | 262144 | 256K |
| Gemma 4 31B 5090 Q4 fallback | `odytrice/gemma4:5090-31b` | 153600 | 150K |
| Qwen 3.6 27B 5090 Q4 fallback | `odytrice/qwen3.6:5090-27b` | 190000 | 190K |
| Qwen 3.6 35B-A3B 5090 Q4 fallback | `odytrice/qwen3.6:5090-35b` | 190000 | 190K |
| GLM-4.7-Flash | `glm-4.7-flash` | 204800 | 200K |
| Qwen3-Coder 30B-A3B | `qwen3-coder:30b` | 225280 | 220K |
| Gemma 4 31B Q4 | `gemma4:31b` | 131072 | 128K |
| GLM-4-32B-0414 | `sammcj/glm-4-32b-0414` | 131072 | 128K |
| Qwen3 32B | `qwen3:32b` | 32768 | 32K |
| Qwen 2.5 Coder 32B | `qwen2.5-coder:32b` | 131072 | 128K |
| DeepSeek R1 Distill 32B | `deepseek-r1:32b` | 51200 | 50K |
| GPT-OSS 20B | `gpt-oss:20b` | 131072 | 128K |
| Devstral-Small-2 24B | `devstral-small-2:24b` | 174080 | 170K |
| Gemma 4 26B Q4 | `gemma4:26b` | 131072 | 128K |

Run the model, set the context, and save back to the same tag to update in place:

```
ollama run <model:tag>
/set parameter num_ctx <value>
/save <model:tag>
```

Verify with `ollama ps` — if you see any CPU percentage, reduce `num_ctx`.

---

## OpenCode Configuration

### Recommended model pairing

- **Primary:** `qwen3-coder:30b` or `glm-4.7-flash` — agentic coding, tool calling, file edits
- **Reasoning fallback:** `qwen3:32b` or `deepseek-r1:32b` — complex problems requiring step-by-step reasoning

### Inference settings (Qwen3-Coder recommended)

- temperature: 0.7
- top_p: 0.8
- top_k: 20
- repetition_penalty: 1.05

---

## Verify GPU Offload

After loading a model, verify full GPU offload and check VRAM usage:

```bash
ollama ps
```

Expected output should show **100% GPU**. If you see any CPU percentage, the model is partially running on system RAM — reduce `num_ctx` or switch to `q4_0` KV cache. See [OLLAMA-GUIDE.md](OLLAMA-GUIDE.md#verifying-gpu-offload-and-vram-usage) for details.

---

## Model Selection Guide

| Task | Use This |
|---|---|
| Best SWE-bench coding performance | GLM-4.7-Flash |
| Day-to-day coding with OpenCode/Aider | Qwen3-Coder-30B-A3B |
| Best reasoning + vision + tool calling | Gemma 4 31B |
| Best tool calling reliability | GLM-4-32B-0414 |
| Proven code completion / repair | Qwen2.5-Coder-32B |
| Deep reasoning with traces | DeepSeek-R1-Distill-32B |
| General reasoning + coding | Qwen3 32B |
| Need speed or large context headroom | GPT-OSS 20B |
| Multi-file repo edits | Devstral-Small-2 24B |
| Fast agentic coding with vision | Gemma 4 26B |
| Enterprise / compliance requirements | IBM Granite 4.0 H-Small |

## Gemma 4 Notes

Gemma 4 is a major upgrade from Gemma 3 — it adds **native function calling** (Gemma 3 was prompt-based only and was excluded from this guide). Key details for the 32GB tier:

### Gemma 4 31B (Dense)
- **30.7B dense params**, 60 layers, 256K context, text+image+vision
- **Ollama Q4_K_M compatibility fallback** on 32GB targets q4_0 KV cache at 150K context; direct HF NVFP4-GGUF failed to load on the remote Ollama 0.23.x server
- **Best reasoning in class:** MMLU Pro 85.2%, AIME 2026 89.2%, Codeforces Elo 2150, LiveCodeBench v6 80.0%
- **Arena AI rank #3** among all open models (score 1452)
- **Native tool calling** with structured JSON, configurable thinking mode
- **Apache 2.0 license** — fully permissive for commercial use
- Sampling: `temperature=1.0`, `top_p=0.95`, `top_k=64`

### Gemma 4 26B (MoE)
- **25.2B total / 3.8B active**, 128 experts (8 active + 1 shared), 30 layers, 256K context
- **Ollama Q4_K_M compatibility fallback** on 32GB fits with q4_0 KV cache at 256K context
- **Extremely fast:** ~150 tok/s due to only 3.8B active params
- **Arena AI rank #6** (score 1441), LiveCodeBench v6 77.1%, Codeforces Elo 1718
- On 32GB, this MoE profile targets the tuned Q4 fallback at 256K context - much better than the 32-48K limit on 24GB

---

## Tips

- **GLM-4-32B-0414:** Use the `sammcj/glm-4-32b-0414` Ollama model — it includes a fixed GGUF with correct tool calling template (the native GLM format is XML; this adapts it for JSON)
- **GLM-4.7-Flash:** Ollama handles the chat template automatically. If using llama.cpp directly, pass the `--jinja` flag
- **Gemma 4 sampling:** Use `temperature=1.0`, `top_p=0.95`, `top_k=64` (different from other models' 0.7/0.8/20)
- **Gemma 4 thinking mode:** Controlled via `<|think|>` token in system prompt — Ollama handles this automatically
- **DeepSeek R1 temperature:** Set between 0.5-0.7 (0.6 recommended) to avoid incoherent outputs
- **DeepSeek R1 system prompt:** Works best without one — put all instructions in the user message
- **Qwen3-Coder mode:** Non-thinking only — no `ühl` blocks. Use Qwen3 32B if you need thinking mode
- **System RAM:** 64GB recommended alongside 32GB VRAM for smooth operation
