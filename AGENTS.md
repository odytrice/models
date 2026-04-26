# Repository Guidelines

## Project Overview

This is an AI/LLM workbench for running, configuring, and fine-tuning open-source language models on consumer GPUs (24–32GB VRAM). It includes inference guides (Ollama, llama.cpp), GPU hardware benchmarks, and a training pipeline for distilling domain-specialized models.

## Project Structure

```
models/
├── pipeline/
│   ├── scripts/        # Python data generation, benchmarking, and verification scripts
│   ├── prompts/        # YAML prompt templates for each domain (F#, Svelte, Docker, etc.)
│   ├── verify/         # F# compiler verification project (verify.fsproj)
│   └── docs/           # Scraped documentation (gitignored)
├── configs/
│   ├── rounds/         # YAML run configs for each data generation round
│   ├── Modelfile.*     # Ollama Modelfiles for different VRAM tiers
│   └── train_*.py      # LoRA training configs
├── data/               # Generated training data (gitignored: raw/, verified/, formatted/)
├── Training/           # Distillation plan docs (00-overview.md through 05-resolved-questions.md)
├── Llama/              # llama.cpp management CLI (llama.sh, llama.ps1, install guide)
├── cards/              # Model cards (Flash.md, Thinking.md)
├── OLLAMA-GUIDE.md     # Ollama setup and API reference
├── 24GB-GPU.md         # Model selection for 24GB GPUs
├── 32GB-GPU.md         # Model selection for 32GB GPUs
└── hardware-comparison.md  # Hardware benchmarks
```

## Build, Test, and Development Commands

```bash
# Install Python dependencies (data pipeline)
pip install -r requirements.txt

# Generate training data (multi-provider)
python pipeline/scripts/run_generation.py

# Run benchmarks
python pipeline/scripts/run_benchmark.py

# Verify F# outputs (requires .NET SDK)
dotnet run --project pipeline/verify

# Push model to Hugging Face Hub
python pipeline/scripts/push_to_hub.py
```

## Coding Style & Naming Conventions

- **Python**: Follow PEP 8. Use `snake_case` for files and functions. The project uses `ruff` for linting (`.ruff_cache/` present).
- **YAML configs**: Use `snake_case` keys. Organize prompt templates by domain (`fsharp_core.yaml`, `svelte_typescript.yaml`).
- **Markdown docs**: Use numbered prefix for ordered docs (e.g., `00-overview.md`, `01-teacher-models.md`). Use `UPPERCASE-HYPHENATED.md` for top-level guides.
- **Modelfiles**: Name as `Modelfile.<variant>-<vram>` (e.g., `Modelfile.kenichi-flash-24gb`).
- **Cross-platform scripts**: Provide both `.sh` and `.ps1` for CLI tools (see `Llama/llama.sh` and `Llama/llama.ps1`).

## Testing Guidelines

- F# verification is the primary test harness — it compiles and runs generated F# code via the .NET compiler.
- There is no formal unit test framework. Validation happens through the pipeline: generate → verify → analyze failures → fix → re-verify.
- Use `python pipeline/scripts/reverify_failures.py` to recheck previously failing outputs.

## Commit & PR Guidelines

- **Commit style**: Imperative mood, concise descriptions. Examples from history:
  - `Add K2.6 and GLM-5.1 benchmarks with multi-provider pipeline`
  - `docs: integrate Gemma 4 26B and 31B across hardware guides`
  - `Fix Flash Modelfile download URLs to point to -GGUF repo`
- Use `docs:` prefix for documentation-only changes.
- Use `Fix` prefix for bug fixes.
- Use `Add` prefix for new features or content.

## Architecture Notes

- The pipeline is multi-provider: it calls cloud teacher APIs (Kimi K2.5, MiniMax M2.7, DeepSeek V3.2) to generate training data.
- Data flows: `prompts/` → `run_generation.py` → `data/raw/` → `verify/` → `data/verified/` → `format_dataset.py` → `data/formatted/`.
- Large generated data, model weights, and scraped docs are gitignored.
- This project targets Windows primarily (PowerShell scripts, .bat files), but bash scripts are provided for Linux/macOS.
