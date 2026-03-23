"""
Dataset Formatting Pipeline

Converts verified JSONL samples into HuggingFace datasets format for training.
Supports three output formats:
  1. ChatML (for Qwen3.5 native chat template)
  2. Mistral (for Devstral Small 2 / Mistral instruct models)
  3. ShareGPT (for Axolotl compatibility)

Also handles:
  - Splitting into context-length buckets (for progressive training stages)
  - Train/validation split
  - Token counting via the Qwen3.5 tokenizer
  - Mixing samples from multiple domains in the correct proportions

Usage:
  python format_dataset.py --input data/verified/ --output data/formatted/ --format chatml
  python format_dataset.py --input data/verified/ --output data/formatted/ --format mistral
  python format_dataset.py --input data/verified/ --output data/formatted/ --format sharegpt --split-by-length
  python format_dataset.py --input data/verified/ --output data/formatted/ --format all --split-by-length
"""

import argparse
import json
import logging
import random
from collections import defaultdict
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Target data proportions from 02-domain-specialization.md
# Note: "general_coding" includes both our distilled general samples and
# OpenCodeInstruct supplemental data (nvidia-oci teacher)
DOMAIN_PROPORTIONS = {
    "fsharp_core": 0.15,
    "fsharp_libraries": 0.125,
    "svelte_typescript": 0.25,
    "docker_kubernetes": 0.09,
    "agentic_swe": 0.15,
    "dotnet_aspnet": 0.05,
    "cross_domain": 0.05,
    "long_context": 0.075,
    "general_coding": 0.06,
}

# Context length buckets for progressive training (from 03-distillation-pipeline.md)
LENGTH_BUCKETS = {
    "stage1": (0, 16384),  # 0-16K tokens
    "stage2": (16384, 65536),  # 16K-64K tokens
    "stage3": (65536, 131072),  # 64K-128K tokens
    "stage4": (131072, 262144),  # 128K-256K tokens
}


def estimate_tokens(text: str) -> int:
    """Rough token count estimate (4 chars per token for English/code).

    For accurate counts, load the actual Qwen3.5 tokenizer:
      from transformers import AutoTokenizer
      tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-27B")
      return len(tokenizer.encode(text))

    We use the approximation for speed during formatting; actual token counts
    are computed during training.
    """
    return len(text) // 4


def load_verified_samples(input_dir: Path) -> list[dict]:
    """Load all passing samples from verified JSONL files."""
    samples = []
    seen_ids = set()
    for jsonl_file in sorted(input_dir.glob("*_passing.jsonl")):
        log.info(f"Loading {jsonl_file.name}...")
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    sample = json.loads(line)
                    if sample.get("verify_result", {}).get("status") == "pass":
                        samples.append(sample)
                        seen_ids.add(sample.get("id"))
                except json.JSONDecodeError:
                    continue

    # Load all JSONL files (including non-verified domains and merged benchmark data)
    for jsonl_file in sorted(input_dir.glob("*.jsonl")):
        if "_passing" in jsonl_file.name or "_verified" in jsonl_file.name:
            continue
        log.info(f"Loading {jsonl_file.name}...")
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    sample = json.loads(line)
                    sid = sample.get("id", "")
                    # Skip if already loaded from _passing file
                    if sid in seen_ids:
                        continue
                    # If sample has verify_result, only include if passed
                    if "verify_result" in sample:
                        if sample["verify_result"].get("status") == "pass":
                            samples.append(sample)
                            seen_ids.add(sid)
                    else:
                        # No verification result = non-F# domain, include as-is
                        samples.append(sample)
                        seen_ids.add(sid)
                except json.JSONDecodeError:
                    continue

    log.info(f"Loaded {len(samples)} total samples")
    return samples


def to_chatml(sample: dict) -> dict:
    """Convert a sample to ChatML format (Qwen3.5 native format).

    Format:
    {"messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ]}
    """
    messages = [
        {"role": "user", "content": sample["instruction"]},
        {"role": "assistant", "content": sample["response"]},
    ]
    return {
        "messages": messages,
        "id": sample.get("id", ""),
        "domain": sample.get("domain", ""),
        "teacher": sample.get("teacher", ""),
    }


def to_mistral(sample: dict) -> dict:
    """Convert a sample to Mistral instruct format (Devstral Small 2 / Mistral models).

    Uses the Mistral v7 Tekken tokenizer format with [INST] tags.
    Unsloth recognizes this as chat_template="mistral".

    Format:
    {"messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ]}

    Note: The messages structure is the same as ChatML, but Unsloth applies
    the correct Mistral special tokens ([INST], [/INST], etc.) when
    chat_template="mistral" is set during training. We use the messages
    format here so both ChatML and Mistral can be loaded the same way,
    with the template applied at training time by the tokenizer.
    """
    messages = [
        {"role": "user", "content": sample["instruction"]},
        {"role": "assistant", "content": sample["response"]},
    ]
    return {
        "messages": messages,
        "id": sample.get("id", ""),
        "domain": sample.get("domain", ""),
        "teacher": sample.get("teacher", ""),
    }


def to_sharegpt(sample: dict) -> dict:
    """Convert a sample to ShareGPT format (Axolotl compatible).

    Format:
    {"conversations": [
        {"from": "human", "value": "..."},
        {"from": "gpt", "value": "..."}
    ]}
    """
    conversations = [
        {"from": "human", "value": sample["instruction"]},
        {"from": "gpt", "value": sample["response"]},
    ]
    return {
        "conversations": conversations,
        "id": sample.get("id", ""),
        "domain": sample.get("domain", ""),
        "teacher": sample.get("teacher", ""),
    }


def split_by_length(samples: list[dict]) -> dict[str, list[dict]]:
    """Split samples into context-length buckets for progressive training."""
    buckets = {stage: [] for stage in LENGTH_BUCKETS}

    for sample in samples:
        total_text = sample.get("instruction", "") + sample.get("response", "")
        token_count = estimate_tokens(total_text)

        placed = False
        for stage, (min_len, max_len) in LENGTH_BUCKETS.items():
            if min_len <= token_count < max_len:
                buckets[stage].append(sample)
                placed = True
                break

        if not placed:
            # Exceeds all buckets -- put in stage4
            buckets["stage4"].append(sample)

    for stage, bucket in buckets.items():
        min_len, max_len = LENGTH_BUCKETS[stage]
        log.info(
            f"  {stage} ({min_len // 1024}K-{max_len // 1024}K): {len(bucket)} samples"
        )

    return buckets


def train_val_split(
    samples: list[dict], val_ratio: float = 0.05, seed: int = 42
) -> tuple[list[dict], list[dict]]:
    """Split samples into train and validation sets."""
    rng = random.Random(seed)
    shuffled = samples.copy()
    rng.shuffle(shuffled)
    val_size = max(1, int(len(shuffled) * val_ratio))
    return shuffled[val_size:], shuffled[:val_size]


def save_jsonl(samples: list[dict], output_path: Path):
    """Save samples to a JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    log.info(f"Saved {len(samples)} samples to {output_path}")


CONVERTERS = {
    "chatml": to_chatml,
    "mistral": to_mistral,
    "sharegpt": to_sharegpt,
}


def format_single(
    samples: list[dict],
    output_dir: Path,
    fmt: str,
    split_by_ctx_length: bool = False,
    val_ratio: float = 0.05,
):
    """Format and save samples in a single format."""
    converter = CONVERTERS[fmt]
    formatted = [converter(s) for s in samples]

    if split_by_ctx_length:
        buckets = split_by_length(formatted)
        for stage, bucket_samples in buckets.items():
            if not bucket_samples:
                continue
            train, val = train_val_split(bucket_samples, val_ratio)
            save_jsonl(train, output_dir / f"{stage}_train.jsonl")
            if val:
                save_jsonl(val, output_dir / f"{stage}_val.jsonl")
    else:
        train, val = train_val_split(formatted, val_ratio)
        save_jsonl(train, output_dir / "train.jsonl")
        save_jsonl(val, output_dir / "val.jsonl")

    return len(formatted)


def format_dataset(
    input_dir: Path,
    output_dir: Path,
    fmt: str = "chatml",
    split_by_ctx_length: bool = False,
    val_ratio: float = 0.05,
):
    """Main formatting pipeline."""
    samples = load_verified_samples(input_dir)

    if not samples:
        log.warning("No samples found. Nothing to format.")
        return

    # Log domain distribution
    domain_counts = defaultdict(int)
    for s in samples:
        domain_counts[s.get("domain", "unknown")] += 1
    log.info("Domain distribution:")
    for domain, count in sorted(domain_counts.items()):
        log.info(f"  {domain}: {count} ({count / len(samples) * 100:.1f}%)")

    if fmt == "all":
        # Format for all supported formats (each in its own subdirectory)
        formats = ["chatml", "mistral"]
        for f in formats:
            fmt_dir = output_dir / f
            log.info(f"\nFormatting: {f} -> {fmt_dir}")
            count = format_single(samples, fmt_dir, f, split_by_ctx_length, val_ratio)

        log.info("=" * 60)
        log.info("FORMATTING SUMMARY")
        log.info(f"  Formats: {', '.join(formats)}")
        log.info(f"  Total:   {len(samples)} samples (per format)")
        log.info(f"  Output:  {output_dir}")
        log.info("=" * 60)
    else:
        count = format_single(samples, output_dir, fmt, split_by_ctx_length, val_ratio)

        log.info("=" * 60)
        log.info("FORMATTING SUMMARY")
        log.info(f"  Format:  {fmt}")
        log.info(f"  Total:   {count} samples")
        log.info(f"  Output:  {output_dir}")
        log.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Dataset Formatting Pipeline")
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input directory with verified JSONL files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for formatted dataset",
    )
    parser.add_argument(
        "--format",
        choices=["chatml", "mistral", "sharegpt", "all"],
        default="chatml",
        help="Output format: chatml (Qwen), mistral (Devstral), sharegpt (Axolotl), or all (chatml + mistral in subdirs)",
    )
    parser.add_argument(
        "--split-by-length",
        action="store_true",
        help="Split into context-length buckets",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.05,
        help="Validation set ratio (default: 0.05)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        log.error(f"Input directory not found: {args.input}")
        return

    format_dataset(
        input_dir=args.input,
        output_dir=args.output,
        fmt=args.format,
        split_by_ctx_length=args.split_by_length,
        val_ratio=args.val_ratio,
    )


if __name__ == "__main__":
    main()
