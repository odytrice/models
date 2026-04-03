# Models

An AI/LLM workbench for running, configuring, and fine-tuning open-source language models on consumer GPUs.

This repository collects everything needed to go from a stock GPU to a productive local AI setup: model selection guidance, inference engine configuration (Ollama and llama.cpp), quantization strategies, and a full training plan for distilling domain-specialized models.

---

## Local Inference with Ollama

The **[Ollama Guide](OLLAMA-GUIDE.md)** covers everything needed to run models locally:

- Model selection principles (parameter sizing by VRAM, context minimums, tool calling requirements)
- Quantization formats (Q4_K_M, Q5_K_M) and KV cache quantization (q8_0, q4_0)
- Environment variables and Windows setup
- Context size configuration and limits
- GPU offload verification
- API usage (REST and Python)

### GPU-Specific Guides

| Guide | VRAM | Example GPUs | Dense Model Range |
|---|---|---|---|
| [24GB GPU Guide](24GB-GPU.md) | 24 GB | RTX 4090, RTX 3090, RTX A5000 | 14-25B params |
| [32GB GPU Guide](32GB-GPU.md) | 32 GB | RTX 5090 | 20-32B params |

### Custom Models

| Guide | Description |
|---|---|
| [Creating Ollama Models from Hugging Face](creating-ollama-models.md) | Download GGUFs from Hugging Face and create custom Ollama models with your own configuration |

---

## Local Inference with llama.cpp

The **[llama.cpp Guide](Llama/LLAMA-CPP-GUIDE.md)** covers setting up a server from scratch on any platform using llama.cpp + llama-swap:

- Full server setup guides for Linux (NVIDIA CUDA, AMD Vulkan), Windows, and macOS
- Model selection, quantization, and VRAM budgeting
- llama-swap configuration (auto-swap, TTL idle unloading)
- OpenAI-compatible API usage (REST and Python)
- `llama` CLI for remote management ([install guide](Llama/install.md))
- Troubleshooting (VRAM spill, DLL loading, CUDA vs Vulkan)

| File | Description |
|------|-------------|
| [LLAMA-CPP-GUIDE.md](Llama/LLAMA-CPP-GUIDE.md) | Complete setup and reference guide |
| [install.md](Llama/install.md) | CLI script installation (bash + PowerShell) |
| [llama.sh](Llama/llama.sh) | Management CLI (bash) |
| [llama.ps1](Llama/llama.ps1) | Management CLI (PowerShell) |

---

## Training & Distillation

The **[Training](Training/)** directory contains a complete plan for multi-teacher distillation into a domain-specialized local model.

**Goal:** Distill coding capabilities from three cloud-scale teacher models into Qwen3.5-27B (dense) for local inference on 32GB VRAM with 204K token context. The resulting model is specialized for full-stack web development with F#, Svelte, TypeScript, .NET, Docker, and Kubernetes.

**Teacher models:** Kimi K2.5, MiniMax M2.7, DeepSeek V3.2 -- each assigned to the domains where they are strongest.

| Document | Contents |
|----------|----------|
| [00-overview.md](Training/00-overview.md) | Project overview, multi-teacher strategy, student model specs |
| [01-teacher-models.md](Training/01-teacher-models.md) | Teacher model specs, strengths/weaknesses, comparison matrix |
| [02-domain-specialization.md](Training/02-domain-specialization.md) | Training data composition, F# libraries, training topics |
| [03-distillation-pipeline.md](Training/03-distillation-pipeline.md) | Data generation, F# compiler verification, doc sources, training steps |
| [04-training-config.md](Training/04-training-config.md) | LoRA config, cloud GPU providers, cost estimates |
| [05-resolved-questions.md](Training/05-resolved-questions.md) | Resolved and open questions |

---

## Repository Structure

```
models/
├── README.md                      # This file -- repository overview
├── OLLAMA-GUIDE.md                # Ollama setup, quantization, KV cache, API reference
├── 24GB-GPU.md                    # Models and config for 24GB GPUs
├── 32GB-GPU.md                    # Models and config for 32GB GPUs
├── creating-ollama-models.md      # Guide: custom Ollama models from HF
├── Llama/
│   ├── LLAMA-CPP-GUIDE.md         # llama.cpp + llama-swap setup and reference
│   ├── install.md                 # CLI script installation guide
│   ├── llama.sh                   # Management CLI (bash)
│   └── llama.ps1                  # Management CLI (PowerShell)
├── Training/
│   ├── 00-overview.md             # Distillation project overview
│   ├── 01-teacher-models.md       # Teacher model analysis
│   ├── 02-domain-specialization.md# Training data and domains
│   ├── 03-distillation-pipeline.md# Pipeline and verification
│   ├── 04-training-config.md      # LoRA, hardware, costs
│   └── 05-resolved-questions.md   # Q&A log
└── LICENSE
```
