# Kenichi -- Multi-Teacher Distilled F# Coding Models (CLOSED)

> **Status: Project closed.** SFT fine-tuning cannot inject domain knowledge — it only steers response style. The trained models performed worse than the base models. See [events.md](events.md) for full post-mortem.

> Named after the anime **"Kenichi: The Mightiest Disciple"** -- a student who trains under multiple masters to become the strongest.

## What Happened

This project attempted to distill domain-specialized coding capabilities (F#, .NET, Svelte, TypeScript, Docker, Kubernetes) from three cloud teacher models into two smaller local student models via LoRA SFT.

**Result**: The fine-tuned models generated incoherent output. SFT with ~8K synthetic single-turn coding samples cannot meaningfully improve F# coding ability over base model pre-training. The LoRA weights degraded the models rather than improving them.

**Resolution**: Use the cloud teacher models directly through OpenCode with skills, sub-agents, and context management for F# library documentation.

## Artifacts Produced

| Artifact | Description | Link |
|----------|-------------|------|
| **kenichi-sft** | 7,953 verified coding samples (ChatML + Mistral) | [odytrice/kenichi-sft](https://huggingface.co/datasets/odytrice/kenichi-sft) |
| **F# verification pipeline** | Automated F# compiler verification with NuGet routing | `pipeline/scripts/verify_fsharp.py` |
| **Teacher benchmarks** | Empirical F# pass rates for all six teachers | [events.md](events.md) |

## Document Index

| File | Contents |
|------|----------|
| [00-overview.md](00-overview.md) | This file -- project overview and post-mortem |
| [01-teacher-models.md](01-teacher-models.md) | Teacher model specs, strengths/weaknesses, comparison matrix |
| [02-domain-specialization.md](02-domain-specialization.md) | Training data composition, F# libraries, training topics |
| [03-distillation-pipeline.md](03-distillation-pipeline.md) | Data generation, F# compiler verification, doc sources |
| [04-training-config.md](04-training-config.md) | LoRA config, cloud GPU providers, cost estimates |
| [05-resolved-questions.md](05-resolved-questions.md) | All resolved and open questions |
| [events.md](events.md) | Chronological log of all events, decisions, results, and post-mortem |

## Key Lesson

**SFT adjusts behavior, not knowledge.** To genuinely improve a model's F# coding ability, you would need Continued Pre-Training (CPT) on millions of tokens of raw F# code — a fundamentally different (and much larger) undertaking. For practical purposes, using capable cloud models directly with good prompting and context management is the better approach.

## Teachers (For Direct Use)

| Teacher | Best For | Ollama Command |
|---------|----------|----------------|
| **Kimi K2.6** | F# core, F# libraries (78.1%, 96.6% pass rates) | `ollama run kimi-k2.6:cloud` |
| **GLM-5.1** | .NET/ASP.NET (97.5% pass rate), F# secondary | `ollama run glm-5.1:cloud` |
| **Kimi K2.5** | Svelte, TypeScript, long-context, cross-domain | `ollama run kimi-k2.5:cloud` |
| **MiniMax M2.7** | Docker, Kubernetes, agentic/DevOps | `ollama run minimax-m2.7:cloud` |
