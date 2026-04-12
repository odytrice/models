# Ollama Local Inference Guide

Configuration guides for running large language models locally with Ollama on consumer GPUs, organized by VRAM tier.

> This file was previously `README.md`. See [README.md](README.md) for the repository overview.

## GPU-Specific Guides

| Guide | VRAM | Example GPUs | Dense Model Range |
|---|---|---|---|
| [24GB GPU Guide](24GB-GPU.md) | 24 GB | RTX 4090, RTX 3090, RTX A5000 | 14-25B params (MoE up to 26B total) |
| [32GB GPU Guide](32GB-GPU.md) | 32 GB | RTX 5090 | 20-32B params (MoE up to 30B total) |

## Custom Models

| Guide | Description |
|---|---|
| [Creating Ollama Models from Hugging Face](creating-ollama-models.md) | How to download GGUFs from Hugging Face and create custom Ollama models with your own configuration |

---

## Model Selection Principles

### Parameter Ranges by VRAM

- **24GB GPUs** should target **14-25B parameter dense models**. Quantizing model weights to Q4_K_M frees up VRAM for KV cache, which directly determines how much context the model can use.
- **32GB GPUs** should target **20-32B parameter dense models**. The extra 8GB of headroom allows dense 32B models to run with usable context windows (64-96K).
- **MoE models are the exception:** Models like Qwen3-Coder-30B-A3B have 30B total parameters but only 3.3B active parameters per token. They fit on 24GB GPUs despite the high total parameter count because all weights must be loaded, but the active compute is small — resulting in faster inference than equivalently-sized dense models.

### Context Minimums

- **Reasoning/planning models:** Need **64K+ native context** minimum. Models trained below this cannot hold enough working memory for multi-step reasoning.
- **Coding agent models:** Need **128K+ native context** minimum. Agentic workflows (OpenCode, Aider, Cline) pass entire files, tool outputs, and conversation history. Anything less is too cramped for the model to work effectively.

### Tool Calling Requirement

**All recommended models must have native tool/function calling support.**

Models without native tool calling are excluded regardless of benchmark performance. Native tool calling means the model was trained with tool-use tokens and can reliably generate structured function calls without prompt engineering hacks.

Examples of excluded models:
- **Phi-4-Reasoning** — no native tool calling support
- **DeepCoder-14B** — weak/community-patched tool calling only

**Note on Gemma:** Gemma 3 was previously excluded for prompt-based tool calling only. **Gemma 4 adds native function calling** and is now included in both the 24GB and 32GB guides.

---

## Quantization and KV Cache

### Model Quantization

| Format | Bits/Weight | Quality | VRAM Savings vs f16 |
|---|---|---|---|
| Q4_K_M | ~4.5 | Good (sweet spot) | ~75% |
| Q5_K_M | ~5.5 | Better | ~65% |

Q4_K_M is the default recommendation. Q5_K_M is worth using when VRAM budget allows. Both use mixed precision — more important layers keep higher precision.

### KV Cache Quantization

The KV cache stores attention state and grows linearly with context length. Quantizing it is essential for fitting long contexts in VRAM.

| KV Cache Type | Bits | Quality Impact | Memory vs f16 |
|---|---|---|---|
| f16 (default) | 16 | Baseline | 1x |
| q8_0 | 8 | Negligible loss | 0.5x |
| q4_0 | 4 | Slight degradation at very high context | 0.25x |

**Recommendation:** Use q8_0 as default. Switch to q4_0 only when you need to push context length further and accept minor quality tradeoffs.

### KV Cache Memory by Type and Context Size

| KV Cache Type | 32K ctx | 64K ctx | 128K ctx |
|---|---|---|---|
| f16 (default) | ~10 GB | ~20 GB | ~40 GB |
| q8_0 | ~5 GB | ~10 GB | ~20 GB |
| q4_0 | ~2.5 GB | ~5 GB | ~10 GB |

---

## Environment Variables

Set these before launching Ollama. On Windows, set as user environment variables and restart Ollama.

| Variable | Value | Purpose |
|---|---|---|
| `OLLAMA_FLASH_ATTENTION` | `1` | Enables flash attention, reduces memory overhead |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` | Quantizes KV cache to ~half memory usage |

**Important:** `OLLAMA_KV_CACHE_TYPE` requires `OLLAMA_FLASH_ATTENTION=1`. Without it, KV cache silently falls back to f16.

### Setting Environment Variables on Windows

1. Quit Ollama from the system tray (right-click icon > Quit)
2. Open **Settings** > search **"environment variables"** > **"Edit environment variables for your account"**
3. Add the two variables above as new user variables
4. Click OK to save
5. Relaunch Ollama from the Start menu

---

## Context Size Reference

| Label | num_ctx Value |
|-------|---------------|
| 16K   | 16384         |
| 32K   | 32768         |
| 64K   | 65536         |
| 128K  | 131072        |
| 256K  | 262144        |

### Setting Context Size in Ollama

#### Method 1: Update the model in place (recommended)

Run the model, set the context, and save back to the same tag:

```
ollama run deepseek-r1:32b
/set parameter num_ctx 49152
/save deepseek-r1:32b
```

This overwrites the model's default context permanently. The weight blobs are shared — no extra disk space is used.

#### Method 2: Via the API (per request)

```json
{
  "model": "deepseek-r1:32b",
  "messages": [...],
  "options": {
    "num_ctx": 49152
  }
}
```

**Important:** Ollama defaults to 4096 tokens regardless of model capability. OpenCode and similar tools require at least 64K. Always increase this.

---

## Verifying GPU Offload and VRAM Usage

After loading a model, check its distribution and VRAM usage in another terminal:

```bash
ollama ps
```

This shows:
- **Model name** and size on disk
- **Processor split** — `100% GPU` means fully offloaded. Any CPU percentage means the model is partially running on system RAM, which dramatically reduces speed.
- **VRAM used** — total GPU memory consumed by weights + KV cache

If you see CPU offloading, reduce `num_ctx` or switch to `q4_0` KV cache. The goal is always 100% GPU.

### Forcing All Layers to GPU

Set `num_gpu` to `999` to force all model layers onto the GPU:

```
ollama run <model:tag>
/set parameter num_gpu 999
/save <model:tag>
```

`999` means "all layers" — Ollama will load as many as exist. If the model doesn't fully fit in VRAM, Ollama will silently offload remaining layers to CPU regardless of this setting. Always verify with `ollama ps`.

---

## Warning: Do Not Exceed a Model's Trained Context Length

Setting `num_ctx` beyond what a model was trained for causes problems:

- **Broken positional embeddings:** The model's RoPE embeddings were only trained up to its stated limit. Beyond that, the model has never learned to attend to those positions, leading to degraded output quality — ignored context, incoherent responses, or repetition loops.
- **Distant tokens become invisible:** Even though tokens are in the KV cache, the model's attention patterns break down past the training length. Information in the extended region is effectively unreliable or ignored.
- **VRAM cost is still real:** You pay the full memory cost for the oversized KV cache even though the model can't use it properly.
- **What to do instead:** Stay at or below the model's stated context limit. If you need more context, pick a model trained for it (e.g. Qwen3-Coder supports 256K natively). Alternatively, use RAG or summarization to fit large codebases into the available window.

---

## API Usage

Ollama exposes a REST API on port 11434:

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "qwen3-coder:30b",
  "messages": [{"role": "user", "content": "Your prompt here"}]
}'
```

Python client:

```bash
pip install ollama
```

```python
from ollama import chat

response = chat(
    model='qwen3-coder:30b',
    messages=[{'role': 'user', 'content': 'Your prompt here'}],
)
print(response.message.content)
```

---

## Repository Structure

```
models/
├── README.md                      # Repository overview
├── OLLAMA-GUIDE.md                # This file — Ollama setup and reference
├── 24GB-GPU.md                    # Models and config for 24GB GPUs
├── 32GB-GPU.md                    # Models and config for 32GB GPUs
├── creating-ollama-models.md      # Guide: custom Ollama models from HF
├── Training/                      # Multi-teacher distillation project docs
└── LICENSE
```

---

## Tips

- **System RAM:** 64GB recommended alongside your GPU VRAM for smooth operation
- **Quantization quality:** q8_0 KV cache has negligible quality loss. q4_0 may show slight degradation at very high context sizes
- **Qwen3-Coder inference settings:** temperature=0.7, top_p=0.8, top_k=20, repetition_penalty=1.05 (recommended by Qwen)
- **Qwen3-Coder mode:** Non-thinking only — no `ühl` blocks. Use Qwen3 32B if you need thinking mode
- **DeepSeek R1 temperature:** Set between 0.5-0.7 (0.6 recommended) to avoid incoherent outputs
- **DeepSeek R1 system prompt:** Works best without one — put all instructions in the user message
- **Gemma 4 inference settings:** temperature=1.0, top_p=0.95, top_k=64 (different from other models' 0.7/0.8/20)
- **Gemma 4 thinking mode:** Controlled via `<|think|>` token in system prompt — Ollama handles this automatically
- **Gemma 4 26B on 24GB:** Tight KV budget — verify with `ollama ps` and reduce `num_ctx` or use `q4_0` KV cache if you see CPU offloading
