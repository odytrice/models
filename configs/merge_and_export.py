"""
Merge LoRA Adapter & Export to GGUF/HuggingFace
================================================

After training, this script:
1. Merges the LoRA adapter into the base model (full BF16)
2. Saves the merged model in HuggingFace format
3. Exports to GGUF (Q4_K_M, Q5_K_M, Q8_0) for llama.cpp / Ollama
4. Optionally pushes to HuggingFace Hub

Usage:
  # Kenichi Thinking (after training completes):
  python merge_and_export.py \\
    --model Qwen/Qwen3.5-27B \\
    --adapter ./outputs/kenichi-thinking/lora_adapter \\
    --name kenichi-thinking \\
    --push odytrice/kenichi-thinking

  # Kenichi Flash (after training completes):
  python merge_and_export.py \\
    --model unsloth/Devstral-Small-2-24B-Instruct-2512 \\
    --adapter ./outputs/kenichi-flash/lora_adapter \\
    --name kenichi-flash \\
    --push odytrice/kenichi-flash

  # GGUF only (skip HuggingFace push):
  python merge_and_export.py \\
    --model Qwen/Qwen3.5-27B \\
    --adapter ./outputs/kenichi-thinking/lora_adapter \\
    --name kenichi-thinking \\
    --gguf-only

  # Specific quantization types:
  python merge_and_export.py \\
    --model Qwen/Qwen3.5-27B \\
    --adapter ./outputs/kenichi-thinking/lora_adapter \\
    --name kenichi-thinking \\
    --quant q4_k_m q8_0
"""

import argparse
from pathlib import Path

from unsloth import FastLanguageModel


# Default GGUF quantization types to export
DEFAULT_QUANTS = ["q4_k_m", "q5_k_m", "q8_0", "f16"]


def main(
    model_name: str,
    adapter_path: str,
    name: str,
    push_repo: str = None,
    gguf_only: bool = False,
    quants: list = None,
):
    if quants is None:
        quants = DEFAULT_QUANTS

    output_dir = f"./outputs/{name}"
    merged_dir = f"{output_dir}/merged"
    gguf_dir = f"{output_dir}/gguf"

    print("=" * 60)
    print(f"  Merge & Export: {name}")
    print("=" * 60)
    print(f"  Base model:  {model_name}")
    print(f"  Adapter:     {adapter_path}")
    print(f"  Merged dir:  {merged_dir}")
    print(f"  GGUF dir:    {gguf_dir}")
    print(f"  Quants:      {', '.join(quants)}")
    if push_repo:
        print(f"  Push to:     {push_repo}")
    print("=" * 60)

    # ── Load model with adapter ──────────────────────────────────────
    print("\n[1/4] Loading base model + LoRA adapter...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=adapter_path,
        max_seq_length=131072,
        load_in_4bit=False,
        dtype=None,
    )

    # ── Save merged model (HuggingFace format) ───────────────────────
    if not gguf_only:
        print("\n[2/4] Saving merged model (BF16, HuggingFace format)...")
        Path(merged_dir).mkdir(parents=True, exist_ok=True)
        model.save_pretrained_merged(
            merged_dir,
            tokenizer,
            save_method="merged_16bit",
        )
        print(f"  Saved to: {merged_dir}")

        # ── Push to HuggingFace ──────────────────────────────────────
        if push_repo:
            print(f"\n[3/4] Pushing to HuggingFace: {push_repo}...")
            model.push_to_hub_merged(
                push_repo,
                tokenizer,
                save_method="merged_16bit",
            )
            print(f"  Pushed BF16 model to: https://huggingface.co/{push_repo}")
        else:
            print("\n[3/4] Skipping HuggingFace push (no --push specified)")
    else:
        print("\n[2/4] Skipping merged save (--gguf-only)")
        print("[3/4] Skipping HuggingFace push (--gguf-only)")

    # ── Export to GGUF ───────────────────────────────────────────────
    print(f"\n[4/4] Exporting GGUF quantizations...")
    Path(gguf_dir).mkdir(parents=True, exist_ok=True)
    for quant in quants:
        print(f"\n  Exporting {quant.upper()}...")
        model.save_pretrained_gguf(
            gguf_dir,
            tokenizer,
            quantization_method=quant,
        )
        print(f"  Saved to: {gguf_dir}/")

        # Optionally push GGUF to HuggingFace
        if push_repo and not gguf_only:
            gguf_repo = f"{push_repo}-GGUF"
            print(f"  Pushing {quant.upper()} to {gguf_repo}...")
            model.push_to_hub_gguf(
                gguf_repo,
                tokenizer,
                quantization_method=quant,
            )

    # ── Done ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  Export complete: {name}")
    print("=" * 60)
    if not gguf_only:
        print(f"\n  Merged model:  {merged_dir}")
    print(f"  GGUF files:    {gguf_dir}")
    if push_repo:
        print(f"  HuggingFace:   https://huggingface.co/{push_repo}")
        print(f"  GGUF repo:     https://huggingface.co/{push_repo}-GGUF")
    print(f"\n  To run locally with Ollama:")
    print(f"    ollama create {name} -f Modelfile")
    print(f"\n  To run with llama.cpp:")
    print(f"    ./llama-cli -m {gguf_dir}/unsloth.Q4_K_M.gguf --jinja -ngl 99")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge LoRA & Export to GGUF/HuggingFace"
    )
    parser.add_argument(
        "--model", required=True, help="Base model name (e.g., Qwen/Qwen3.5-27B)"
    )
    parser.add_argument(
        "--adapter", required=True, help="Path to LoRA adapter directory"
    )
    parser.add_argument(
        "--name", required=True, help="Output name (e.g., kenichi-thinking)"
    )
    parser.add_argument(
        "--push",
        default=None,
        help="HuggingFace repo to push to (e.g., odytrice/kenichi-thinking)",
    )
    parser.add_argument(
        "--gguf-only",
        action="store_true",
        help="Only export GGUF, skip merged save and HF push",
    )
    parser.add_argument(
        "--quant",
        nargs="+",
        default=None,
        help=f"GGUF quantization types (default: {DEFAULT_QUANTS})",
    )
    args = parser.parse_args()
    main(args.model, args.adapter, args.name, args.push, args.gguf_only, args.quant)
