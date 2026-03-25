"""
Merge LoRA Adapter & Export to GGUF/HuggingFace
================================================

After training, this script:
1. Merges the LoRA adapter into the base model (full BF16)
2. Saves the merged model in HuggingFace format
3. Exports to GGUF (Q4_K_M, Q5_K_M, Q8_0, F16) for llama.cpp / Ollama
4. Optionally pushes to HuggingFace Hub

Supports two merge backends:
- Unsloth (default): Used for Kenichi Flash (Devstral, trained with Unsloth)
- peft: Used for Kenichi Thinking (Qwen3.5-27B VL, trained without Unsloth)

Usage:
  # Kenichi Flash (Unsloth backend — default):
  python merge_and_export.py \\
    --model akoumpa/Devstral-Small-2-24B-Instruct-2512-BF16 \\
    --adapter ./outputs/kenichi-flash/lora_adapter \\
    --name kenichi-flash \\
    --push odytrice/kenichi-flash

  # Kenichi Thinking (peft backend — use --peft flag):
  python merge_and_export.py \\
    --model Qwen/Qwen3.5-27B \\
    --adapter ./outputs/kenichi-thinking/lora_adapter \\
    --name kenichi-thinking \\
    --push odytrice/kenichi-thinking \\
    --peft

  # GGUF only (skip HuggingFace push):
  python merge_and_export.py \\
    --model Qwen/Qwen3.5-27B \\
    --adapter ./outputs/kenichi-thinking/lora_adapter \\
    --name kenichi-thinking \\
    --gguf-only --peft

  # Merge + push BF16 only (no GGUF — saves disk, quantize later on CPU):
  python merge_and_export.py \\
    --model Qwen/Qwen3.5-27B \\
    --adapter ./outputs/kenichi-thinking/lora_adapter \\
    --name kenichi-thinking \\
    --push odytrice/kenichi-thinking \\
    --peft --no-gguf

  # Specific quantization types:
  python merge_and_export.py \\
    --model Qwen/Qwen3.5-27B \\
    --adapter ./outputs/kenichi-thinking/lora_adapter \\
    --name kenichi-thinking \\
    --quant q4_k_m q8_0 --peft
"""

import argparse
import os
from pathlib import Path

# Default GGUF quantization types to export
DEFAULT_QUANTS = ["q4_k_m", "q5_k_m", "q8_0", "f16"]


def merge_unsloth(
    adapter_path: str,
    merged_dir: str,
    push_repo: str,
    gguf_dir: str,
    quants: list,
    gguf_only: bool,
    no_gguf: bool = False,
):
    """Merge and export using Unsloth (for models trained with Unsloth, e.g., Kenichi Flash)."""
    from unsloth import FastLanguageModel

    print("\n[1/4] Loading base model + LoRA adapter (Unsloth)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=adapter_path,
        max_seq_length=131072,
        load_in_4bit=False,
        dtype=None,
    )

    # Save merged model (HuggingFace format)
    if not gguf_only:
        print("\n[2/4] Saving merged model (BF16, HuggingFace format)...")
        Path(merged_dir).mkdir(parents=True, exist_ok=True)
        model.save_pretrained_merged(
            merged_dir,
            tokenizer,
            save_method="merged_16bit",
        )
        print(f"  Saved to: {merged_dir}")

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

    # Export to GGUF
    if no_gguf:
        print(f"\n[4/4] Skipping GGUF export (--no-gguf)")
        return

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

        if push_repo and not gguf_only:
            print(f"  Pushing {quant.upper()} to {push_repo}...")
            model.push_to_hub_gguf(
                push_repo,
                tokenizer,
                quantization_method=quant,
            )


def merge_peft(
    model_name: str,
    adapter_path: str,
    merged_dir: str,
    push_repo: str,
    gguf_dir: str,
    quants: list,
    gguf_only: bool,
    no_gguf: bool = False,
):
    """Merge and export using peft (for models trained without Unsloth, e.g., Kenichi Thinking VL)."""
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer
    from peft import PeftModel

    print("\n[1/4] Loading base model + LoRA adapter (peft)...")
    # Load base model
    model = AutoModelForImageTextToText.from_pretrained(
        model_name,
        dtype=torch.bfloat16,
        device_map="auto",
        attn_implementation="sdpa",
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    # Load and merge LoRA adapter
    print("  Loading LoRA adapter...")
    model = PeftModel.from_pretrained(model, adapter_path)
    print("  Merging LoRA weights into base model...")
    model = model.merge_and_unload()
    print("  Merge complete.")

    # Save merged model (HuggingFace format)
    if not gguf_only:
        print("\n[2/4] Saving merged model (BF16, HuggingFace format)...")
        Path(merged_dir).mkdir(parents=True, exist_ok=True)
        model.save_pretrained(merged_dir)
        tokenizer.save_pretrained(merged_dir)
        print(f"  Saved to: {merged_dir}")

        if push_repo:
            print(f"\n[3/4] Pushing to HuggingFace: {push_repo}...")
            model.push_to_hub(push_repo)
            tokenizer.push_to_hub(push_repo)
            print(f"  Pushed BF16 model to: https://huggingface.co/{push_repo}")
        else:
            print("\n[3/4] Skipping HuggingFace push (no --push specified)")
    else:
        print("\n[2/4] Skipping merged save (--gguf-only)")
        print("[3/4] Skipping HuggingFace push (--gguf-only)")

    # Export to GGUF using llama.cpp converter
    if no_gguf:
        print(f"\n[4/4] Skipping GGUF export (--no-gguf)")
        return

    print(f"\n[4/4] Exporting GGUF quantizations...")
    Path(gguf_dir).mkdir(parents=True, exist_ok=True)

    # Ensure merged model is saved (needed for llama.cpp converter)
    if gguf_only and not Path(merged_dir).exists():
        print("  Saving merged model first (required for GGUF conversion)...")
        Path(merged_dir).mkdir(parents=True, exist_ok=True)
        model.save_pretrained(merged_dir)
        tokenizer.save_pretrained(merged_dir)

    # Check if llama.cpp convert script is available
    convert_script = None
    for candidate in [
        "/workspace/llama.cpp/convert_hf_to_gguf.py",
        "llama.cpp/convert_hf_to_gguf.py",
        os.path.expanduser("~/llama.cpp/convert_hf_to_gguf.py"),
    ]:
        if Path(candidate).exists():
            convert_script = candidate
            break

    if convert_script is None:
        print("\n  WARNING: llama.cpp convert_hf_to_gguf.py not found.")
        print("  To install llama.cpp for GGUF conversion:")
        print(
            "    git clone https://github.com/ggml-org/llama.cpp /workspace/llama.cpp"
        )
        print("    pip install -r /workspace/llama.cpp/requirements.txt")
        print("  Then re-run this script.")
        print(f"\n  Alternatively, use Unsloth to convert the merged model:")
        print(f'    python -c "from unsloth import FastLanguageModel; ..."')
        print(f"\n  Merged model saved at: {merged_dir}")
        return

    import subprocess

    for quant in quants:
        print(f"\n  Exporting {quant.upper()}...")
        outtype_map = {
            "f16": "f16",
            "q8_0": "q8_0",
            "q5_k_m": "q8_0",  # Convert to q8_0 first, then quantize
            "q4_k_m": "q8_0",  # Convert to q8_0 first, then quantize
        }
        outtype = outtype_map.get(quant, "f16")
        gguf_file = f"{gguf_dir}/{quant.upper()}.gguf"

        cmd = [
            "python",
            convert_script,
            merged_dir,
            "--outfile",
            gguf_file,
            "--outtype",
            outtype,
        ]
        print(f"  Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  Saved: {gguf_file}")
        else:
            print(f"  ERROR: {result.stderr[-500:]}")

        # For q4_k_m and q5_k_m, we need an additional quantization step
        if quant in ("q4_k_m", "q5_k_m") and result.returncode == 0:
            quantize_bin = None
            for candidate in [
                "/workspace/llama.cpp/build/bin/llama-quantize",
                "/workspace/llama.cpp/llama-quantize",
                "llama.cpp/build/bin/llama-quantize",
            ]:
                if Path(candidate).exists():
                    quantize_bin = candidate
                    break

            if quantize_bin:
                q8_file = gguf_file  # The q8_0 file we just created
                final_file = f"{gguf_dir}/{quant.upper()}.gguf"
                tmp_file = f"{gguf_dir}/{quant.upper()}_tmp.gguf"
                os.rename(q8_file, tmp_file)
                cmd2 = [quantize_bin, tmp_file, final_file, quant.upper()]
                print(f"  Quantizing: {' '.join(cmd2)}")
                result2 = subprocess.run(cmd2, capture_output=True, text=True)
                if result2.returncode == 0:
                    os.remove(tmp_file)
                    print(f"  Saved: {final_file}")
                else:
                    print(f"  ERROR: {result2.stderr[-500:]}")
            else:
                print(
                    f"  WARNING: llama-quantize not found. {quant.upper()} saved as Q8_0."
                )

        # Push GGUF to HuggingFace (same repo as BF16 model)
        if push_repo and not gguf_only and Path(gguf_file).exists():
            from huggingface_hub import HfApi

            api = HfApi()
            print(f"  Pushing {quant.upper()} to {push_repo}...")
            api.create_repo(push_repo, exist_ok=True)
            api.upload_file(
                path_or_fileobj=gguf_file,
                path_in_repo=f"{quant.upper()}.gguf",
                repo_id=push_repo,
            )


def main(
    model_name: str,
    adapter_path: str,
    name: str,
    push_repo: str = None,
    gguf_only: bool = False,
    no_gguf: bool = False,
    quants: list = None,
    use_peft: bool = False,
):
    if quants is None:
        quants = DEFAULT_QUANTS

    output_dir = f"./outputs/{name}"
    merged_dir = f"{output_dir}/merged"
    gguf_dir = f"{output_dir}/gguf"

    backend = "peft" if use_peft else "Unsloth"
    print("=" * 60)
    print(f"  Merge & Export: {name}")
    print("=" * 60)
    print(f"  Backend:     {backend}")
    print(f"  Base model:  {model_name}")
    print(f"  Adapter:     {adapter_path}")
    print(f"  Merged dir:  {merged_dir}")
    if no_gguf:
        print(f"  GGUF:        SKIPPED (--no-gguf)")
    else:
        print(f"  GGUF dir:    {gguf_dir}")
        print(f"  Quants:      {', '.join(quants)}")
    if push_repo:
        print(f"  Push to:     {push_repo}")
    print("=" * 60)

    if use_peft:
        merge_peft(
            model_name,
            adapter_path,
            merged_dir,
            push_repo,
            gguf_dir,
            quants,
            gguf_only,
            no_gguf,
        )
    else:
        merge_unsloth(
            adapter_path, merged_dir, push_repo, gguf_dir, quants, gguf_only, no_gguf
        )

    # Done
    print("\n" + "=" * 60)
    print(f"  Export complete: {name}")
    print("=" * 60)
    if not gguf_only:
        print(f"\n  Merged model:  {merged_dir}")
    if not no_gguf:
        print(f"  GGUF files:    {gguf_dir}")
    if push_repo:
        print(f"  HuggingFace:   https://huggingface.co/{push_repo}")
    if no_gguf:
        print(f"\n  GGUF export skipped. To quantize later on a CPU machine:")
        print(
            f"    python merge_and_export.py --model {model_name} --adapter {adapter_path} --name {name} --gguf-only"
            + (" --peft" if use_peft else "")
        )
    else:
        print(f"\n  To run locally with Ollama:")
        print(f"    ollama create {name} -f Modelfile")


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
        "--no-gguf",
        action="store_true",
        help="Skip GGUF export entirely (merge + push BF16 only, quantize later on CPU)",
    )
    parser.add_argument(
        "--quant",
        nargs="+",
        default=None,
        help=f"GGUF quantization types (default: {DEFAULT_QUANTS})",
    )
    parser.add_argument(
        "--peft",
        action="store_true",
        help="Use peft merge (for VL models trained without Unsloth)",
    )
    args = parser.parse_args()
    main(
        args.model,
        args.adapter,
        args.name,
        args.push,
        args.gguf_only,
        args.no_gguf,
        args.quant,
        args.peft,
    )
