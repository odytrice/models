# Kenichi -- Multi-Teacher Distilled F# Coding Models

> Named after the anime **"Kenichi: The Mightiest Disciple"** -- a student who trains under multiple masters to become the strongest.

## Overview

Distill domain-specialized coding capabilities from multiple teacher models into two student models for local inference. The distilled models are **domain-specialized** for full-stack web development with F#, Svelte, TypeScript, .NET, Docker, and Kubernetes.

## HuggingFace Datasets

| Dataset | Contents | Link |
|---------|----------|------|
| **kenichi-sft** | 6,558 instruction-tuning samples (ChatML + Mistral formats) | [odytrice/kenichi-sft](https://huggingface.co/datasets/odytrice/kenichi-sft) |
| **kenichi-logprob** | Logprob distillation dataset (planned) | TBD |

## Document Index

| File | Contents |
|------|----------|
| [00-overview.md](00-overview.md) | This file -- project overview, strategy, student models |
| [01-teacher-models.md](01-teacher-models.md) | Teacher model specs, strengths/weaknesses, comparison matrix |
| [02-domain-specialization.md](02-domain-specialization.md) | Training data composition, F# libraries, training topics |
| [03-distillation-pipeline.md](03-distillation-pipeline.md) | Data generation, F# compiler verification, doc sources, training steps |
| [04-training-config.md](04-training-config.md) | LoRA config, cloud GPU providers, cost estimates |
| [05-resolved-questions.md](05-resolved-questions.md) | All resolved and open questions |
| [events.md](events.md) | Chronological log of all pipeline events, decisions, and results |

## Multi-Teacher Strategy

Rather than relying on a single teacher, this project uses three complementary teachers -- each assigned to the domains where they are strongest. Teacher assignments were determined through empirical benchmarking (see events.md for full results).

| Teacher | Domains | Ollama Command |
|---------|---------|----------------|
| **MiniMax M2.7** | F#, F# libraries, Docker/K8s, agentic coding, general coding | `ollama run minimax-m2.7:cloud` |
| **Kimi K2.5** | Svelte, TypeScript, long-context, cross-domain prompts | `ollama run kimi-k2.5:cloud` |
| **GLM-5** | .NET/ASP.NET Core, Docker/K8s, agentic coding, general coding | `ollama run glm-5:cloud` |

**Note:** DeepSeek V3.2 was the original F# teacher but was replaced after benchmarking showed MiniMax achieves 76.6% pass rate on F# verification vs DeepSeek's 43.1%. GLM-5 (77.8% SWE-bench Verified, 73.3% Multilingual) replaces DeepSeek for non-F# .NET domains.

All teachers are accessible via Ollama cloud subscription (Max plan).

---

## Student Models

### Kenichi Thinking: Qwen3.5-27B (Dense)

- **Source**: `Qwen/Qwen3.5-27B` ([HuggingFace](https://huggingface.co/Qwen/Qwen3.5-27B))
- **Architecture**: Dense transformer (NOT MoE)
- **Parameters**: 27B
- **Native Context**: 256K tokens (trained with YaRN rope scaling)
- **Target Context**: 204,800 tokens
- **Quantized variant**: `Qwen/Qwen3.5-27B-GPTQ-Int4` for inference
- **GGUF variant**: `unsloth/Qwen3.5-27B-GGUF` for llama.cpp
- **Inference VRAM**: ~16GB at 4-bit quantization, fits 32GB VRAM comfortably
- **Training VRAM**: ~32-48GB with LoRA + gradient checkpointing (16-bit)

### Kenichi Flash: Devstral Small 2 (24B)

- **Source**: `mistralai/Devstral-Small-2` ([HuggingFace](https://huggingface.co/mistralai/Devstral-Small-2))
- **Architecture**: Dense transformer
- **Parameters**: 24B
- **Native Context**: 256K tokens
- **SWE-bench Verified**: 65.8% (strong baseline for a 24B model)
- **Ollama**: `devstral-small-2` (available locally at ~15GB quantized)
- **License**: Apache 2.0
- **Inference VRAM**: ~14GB at 4-bit quantization
- **Training VRAM**: ~28-40GB with LoRA + gradient checkpointing (16-bit)

**Why two variants?**
- **Kenichi Thinking** (Qwen3.5-27B) -- the reasoning variant. Has native `<think>` mode for step-by-step reasoning before generating code. Stronger on architecture decisions, system design, and complex debugging. Deliberate and strategic.
- **Kenichi Flash** (Devstral Small 2) -- the execution variant. Purpose-built for agentic coding: multi-file editing, codebase exploration, IDE integration. Slightly smaller (24B vs 27B), faster inference, lower VRAM. Instinctive and fast.

Both models are trained on the same distilled dataset using LoRA with a combined CE + KL-divergence loss (SFT curated data + logprob distillation data).

---

## Key Libraries
- **Training**: [Unsloth](https://github.com/unslothai/unsloth) (efficient LoRA), [Axolotl](https://github.com/OpenAccess-AI-Collective/axolotl)
- **Inference**: [llama.cpp](https://github.com/ggerganov/llama.cpp), [vLLM](https://github.com/vllm-project/vllm), [SGLang](https://github.com/sgl-project/sglang)
- **Dataset**: HuggingFace `datasets`
- **Teacher access**: All teachers via Ollama cloud subscription (Max plan)
- **Supplemental data**: NVIDIA OpenCodeInstruct (2,500 Python samples, CC-BY-4.0)
