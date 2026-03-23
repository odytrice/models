# Multi-Teacher Distillation for Domain-Specialized Coding Models

## Overview

Distill domain-specialized coding capabilities from multiple teacher models into two student models for local inference. The distilled models are **domain-specialized** for full-stack web development with F#, Svelte, TypeScript, .NET, Docker, and Kubernetes.

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

### Student 1: Qwen3.5-27B (Dense) -- Primary

- **Source**: `Qwen/Qwen3.5-27B` ([HuggingFace](https://huggingface.co/Qwen/Qwen3.5-27B))
- **Architecture**: Dense transformer (NOT MoE)
- **Parameters**: 27B
- **Native Context**: 256K tokens (trained with YaRN rope scaling)
- **Target Context**: 204,800 tokens
- **Quantized variant**: `Qwen/Qwen3.5-27B-GPTQ-Int4` for inference
- **GGUF variant**: `unsloth/Qwen3.5-27B-GGUF` for llama.cpp
- **Inference VRAM**: ~16GB at 4-bit quantization, fits 32GB VRAM comfortably
- **Training VRAM**: ~32-48GB with LoRA + gradient checkpointing (16-bit)

### Student 2: Devstral Small 2 (24B) -- Secondary

- **Source**: `mistralai/Devstral-Small-2` ([HuggingFace](https://huggingface.co/mistralai/Devstral-Small-2))
- **Architecture**: Dense transformer
- **Parameters**: 24B
- **Native Context**: 256K tokens
- **SWE-bench Verified**: 65.8% (strong baseline for a 24B model)
- **Ollama**: `devstral-small-2` (available locally at ~15GB quantized)
- **License**: Modified MIT (revenue cap: $20M/month)
- **Inference VRAM**: ~14GB at 4-bit quantization
- **Training VRAM**: ~28-40GB with LoRA + gradient checkpointing (16-bit)

**Why two students?**
- **Qwen3.5-27B** is the primary target -- strongest overall base model, Apache 2.0 license, 201-language support
- **Devstral Small 2** is purpose-built for agentic coding -- trained for multi-file editing, codebase exploration, and IDE integration. Slightly smaller (24B vs 27B), meaning faster inference and lower VRAM. Its SWE-bench baseline of 65.8% at 24B is exceptional. The same training data can be used for both models with minimal config changes.

Both models will be trained on the same distilled dataset using the same 4-stage progressive LoRA approach. The resulting models can be compared and the better performer used in production.

---

## Key Libraries
- **Training**: [Unsloth](https://github.com/unslothai/unsloth) (efficient LoRA), [Axolotl](https://github.com/OpenAccess-AI-Collective/axolotl)
- **Inference**: [llama.cpp](https://github.com/ggerganov/llama.cpp), [vLLM](https://github.com/vllm-project/vllm), [SGLang](https://github.com/sgl-project/sglang)
- **Dataset**: HuggingFace `datasets`
- **Teacher access**: All teachers via Ollama cloud subscription (Max plan)
- **Supplemental data**: NVIDIA OpenCodeInstruct (2,500 Python samples, CC-BY-4.0)
