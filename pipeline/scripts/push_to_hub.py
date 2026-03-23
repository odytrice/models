"""
Push Kenichi datasets to HuggingFace Hub.

Usage:
    python push_to_hub.py --repo odytrice/kenichi-sft
    python push_to_hub.py --repo odytrice/kenichi-sft --private
"""

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
FORMATTED_DIR = PROJECT_DIR / "data" / "formatted"

DATASET_CARD = """---
language:
  - en
license: apache-2.0
task_categories:
  - text-generation
tags:
  - code
  - fsharp
  - svelte
  - typescript
  - dotnet
  - docker
  - kubernetes
  - distillation
  - instruction-tuning
pretty_name: Kenichi SFT
size_categories:
  - 1K<n<10K
---

# Kenichi SFT -- Multi-Teacher Distilled F# / Full-Stack Coding Dataset

> Named after the anime **"Kenichi: The Mightiest Disciple"** -- a student who trains under multiple masters to become the strongest.

A domain-specialized instruction-tuning dataset distilled from three teacher models for training F#-focused coding LLMs. All F# samples are compiler-verified.

## Student Models (Intended Use)

| Model | Base | Role | Context |
|-------|------|------|---------|
| **Kenichi Thinking** | Qwen3.5-27B | Reasoning-first, `<think>` mode | 256K |
| **Kenichi Flash** | Devstral Small 2 (24B) | Fast agentic coding | 128K |

Both target local inference on 32GB VRAM.

## Dataset Stats

| Metric | Value |
|--------|-------|
| Total samples | 6,558 |
| Train split | 6,231 |
| Validation split | 327 |
| Formats | ChatML (Qwen) + Mistral Instruct (Devstral) |
| F# compiler verified | Yes (all F# samples) |

## Domain Distribution

| Domain | Samples | % | Description |
|--------|---------|---|-------------|
| fsharp_libraries | 1,695 | 25.8% | Giraffe, FsToolkit, Akka.NET, linq2db, Thoth.Json, and 20+ libraries |
| fsharp_core | 1,003 | 15.3% | DUs, pattern matching, CEs, SRTP, agents, type providers |
| general_coding | 950 | 14.5% | Algorithms, data structures, design patterns (450 distilled + 500 OpenCodeInstruct) |
| svelte_typescript | 676 | 10.3% | Svelte 5 runes, SvelteKit 2, TypeScript patterns |
| dotnet_aspnet | 689 | 10.5% | ASP.NET Core with F#, DI, middleware, auth, health checks |
| cross_domain | 585 | 8.9% | Full-stack F# + Svelte + Docker integration |
| docker_kubernetes | 414 | 6.3% | Dockerfiles, K8s manifests, Helm, CI/CD |
| agentic_swe | 279 | 4.3% | Multi-step debugging, refactoring, migration tasks |
| long_context | 267 | 4.1% | Full project walkthroughs, multi-file implementations |

F# total (core + libraries): 2,698 samples (41.1%) -- intentionally high given F#'s scarcity in pre-training data (<0.1% of The Stack v2).

## Teacher Models

Teacher assignments were empirically determined through head-to-head F# compiler verification benchmarks on 549 prompts across 4 teacher models.

| Teacher | Params | Domains | F# Pass Rate | Role |
|---------|--------|---------|-------------|------|
| **MiniMax M2.7** | 229B MoE | F# core, F# libraries | 76.6% | F# specialist |
| **GLM-5** | 744B MoE | .NET/ASP.NET, Docker/K8s, agentic, general | 97.1% (dotnet) | .NET/general powerhouse |
| **Kimi K2.5** | -- | Svelte/TypeScript, cross-domain, long-context | 90.0% (cross-domain) | Frontend/long-context specialist |
| *DeepSeek V3.2* | 685B MoE | *(Round 1 only, replaced after benchmarking)* | 43.1% | *Retired* |

### Why MiniMax for F#?

Benchmark results on 427 F# prompts that DeepSeek failed on:

| Teacher | Passed | Pass Rate | Skip Rate |
|---------|--------|-----------|-----------|
| MiniMax M2.7 | 327/427 | **76.6%** | 0.7% |
| GLM-5 | 149/427 | 70.6% | 3.5% |
| Kimi K2.5 | 149/427 | 34.9% | 41.2% |

MiniMax's near-zero skip rate (almost always generates code) combined with the highest pass rate made it the clear choice for F# domains.

## Data Generation Pipeline

```
185 seed prompts (9 domains)
    |
    v
expand_prompts.py (30 variations per seed via teachers)
    |
    v
~5,169 unique expanded prompts
    |
    v
generate_data.py (2 rounds: default temp + temp 0.9)
    |
    v
~9,138 raw responses (4,569 per round)
    |
    v
verify_fsharp.py (F# compiler verification)
    |
    v
format_dataset.py (ChatML + Mistral formats)
    |
    v
6,558 verified training samples
```

### Two Generation Rounds

- **Round 1**: Default teacher temperatures (0.4-0.7), original teacher assignments
- **Round 2**: Temperature 0.9, optimized teacher assignments based on benchmark results

Running the same prompts at different temperatures with different teachers produces structurally diverse solutions to the same problems, improving student generalization.

### F# Compiler Verification

All samples containing F# code are verified through a two-stage pipeline:

1. **Compile check**: Code extracted from teacher responses and compiled via `dotnet fsi` (scripts) or `dotnet build` (namespace/module code)
2. **Execution check**: Samples with test assertions are executed to verify runtime correctness

The verification project includes 30+ NuGet packages: Giraffe, FsToolkit.ErrorHandling, Akka.NET, linq2db, Serilog, Thoth.Json.Net, FSharp.SystemTextJson, FSharp.Control.AsyncSeq, and more.

Samples that fail compilation are excluded from the dataset. Three verification improvements were developed during the project:
- Truncated response extraction (handles unclosed code fences from max_token cutoffs)
- Namespace/module routing (routes `namespace X` code through project build instead of .fsx)
- Multi-block conflict resolution (uses largest block when multiple blocks have conflicting declarations)

### Supplemental Data

500 samples from [NVIDIA OpenCodeInstruct](https://huggingface.co/datasets/nvidia/OpenCodeInstruct) (5M Python coding samples), filtered with strict quality thresholds:
- Unit test pass rate >= 0.9 (passes 9+ of 10 tests)
- LLM judgement scores >= 4/5 on requirement conformance, logical correctness, and edge case consideration

## Formats

Two formats are provided for different model families:

### ChatML (for Qwen3.5 / Kenichi Thinking)

Split names: `chatml_train`, `chatml_val`

```json
{
  "messages": [
    {"role": "user", "content": "Write an F# discriminated union..."},
    {"role": "assistant", "content": "Here's an F# DU for..."}
  ],
  "id": "fsharp_core_0001_exp_003",
  "domain": "fsharp_core",
  "teacher": "minimax"
}
```

### Mistral Instruct (for Devstral Small 2 / Kenichi Flash)

Split names: `mistral_train`, `mistral_val`

Same `messages` structure -- the Mistral special tokens (`[INST]`, `[/INST]`) are applied at training time by the tokenizer when `chat_template="mistral"` is set.

## Usage

```python
from datasets import load_dataset

# For Qwen3.5 / ChatML models
ds = load_dataset("odytrice/kenichi-sft", split="chatml_train")

# For Devstral / Mistral models
ds = load_dataset("odytrice/kenichi-sft", split="mistral_train")

# Filter by domain
fsharp_ds = ds.filter(lambda x: x["domain"].startswith("fsharp"))

# Filter by teacher
minimax_ds = ds.filter(lambda x: x["teacher"] == "minimax")
```

## License

Apache 2.0

## Acknowledgments

- **Teacher models**: MiniMax M2.7, GLM-5, Kimi K2.5, DeepSeek V3.2
- **Supplemental data**: NVIDIA OpenCodeInstruct (CC-BY-4.0)
- **Infrastructure**: Ollama Max subscription for teacher inference
- **F# verification**: .NET SDK with 30+ NuGet packages
"""


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file into a list of dicts."""
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            samples.append(json.loads(line))
    return samples


def main():
    parser = argparse.ArgumentParser(
        description="Push Kenichi dataset to HuggingFace Hub"
    )
    parser.add_argument(
        "--repo",
        type=str,
        required=True,
        help="HuggingFace repo ID (e.g., odytrice/kenichi-sft)",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create as a private dataset",
    )
    args = parser.parse_args()

    try:
        from datasets import Dataset, DatasetDict
        from huggingface_hub import HfApi
    except ImportError:
        log.error("Required packages: pip install datasets huggingface_hub")
        return

    log.info("=" * 60)
    log.info(f"PUBLISHING TO HUGGINGFACE: {args.repo}")
    log.info("=" * 60)

    # Load all splits
    splits = {}
    for fmt in ["chatml", "mistral"]:
        for split_name in ["stage1_train", "stage1_val"]:
            path = FORMATTED_DIR / fmt / f"{split_name}.jsonl"
            if not path.exists():
                log.warning(f"  {path} not found, skipping")
                continue

            # Map stage1_train -> chatml_train, stage1_val -> chatml_val
            hf_split = f"{fmt}_{split_name.replace('stage1_', '')}"
            data = load_jsonl(path)
            splits[hf_split] = Dataset.from_list(data)
            log.info(f"  Loaded {hf_split}: {len(data)} samples")

    if not splits:
        log.error("No data found to publish")
        return

    ds_dict = DatasetDict(splits)

    log.info(f"\nDataset splits:")
    for name, ds in ds_dict.items():
        log.info(f"  {name}: {len(ds)} samples, columns: {ds.column_names}")

    # Push to hub
    log.info(f"\nPushing to {args.repo}...")
    ds_dict.push_to_hub(
        args.repo,
        private=args.private,
    )

    # Upload the README/dataset card
    log.info("Uploading dataset card...")
    api = HfApi()
    api.upload_file(
        path_or_fileobj=DATASET_CARD.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=args.repo,
        repo_type="dataset",
    )

    log.info(f"\n{'=' * 60}")
    log.info(f"PUBLISHED: https://huggingface.co/datasets/{args.repo}")
    log.info(f"{'=' * 60}")


if __name__ == "__main__":
    main()
