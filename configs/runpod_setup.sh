#!/bin/bash
# ============================================================================
# RunPod A100 80GB Setup Script for Kenichi Training
# ============================================================================
#
# This script sets up a RunPod instance for training either:
#   - Kenichi Thinking (Qwen3.5-27B) — run on Pod A
#   - Kenichi Flash (Devstral Small 2) — run on Pod B
#
# Prerequisites:
#   - RunPod A100 80GB SXM pod
#   - PyTorch 2.4+ CUDA image (RunPod's default pytorch template works)
#
# Usage:
#   # 1. SSH into RunPod instance
#   # 2. Upload or clone this repo:
#   git clone https://github.com/<your-repo>/Models.git && cd Models
#   # 3. Run setup:
#   bash configs/runpod_setup.sh
#   # 4. Train (pick one):
#   python configs/train_kenichi_thinking.py   # Pod A
#   python configs/train_kenichi_flash.py      # Pod B
#
# ============================================================================

set -e

echo "============================================"
echo "  Kenichi Training — RunPod Setup"
echo "============================================"

# ── System packages ──────────────────────────────────────────────────
echo ""
echo "[1/5] Installing system dependencies..."
apt-get update -qq && apt-get install -y -qq git-lfs htop nvtop 2>/dev/null || true

# ── Python packages ──────────────────────────────────────────────────
echo ""
echo "[2/5] Installing Python packages..."

# Unsloth (optimized LoRA training — 2x faster, 30% less VRAM)
pip install -q --upgrade pip
pip install -q "unsloth[cu124-ampere-torch250] @ git+https://github.com/unslothai/unsloth.git"

# TRL (SFTTrainer) and datasets
pip install -q --upgrade trl datasets transformers accelerate peft bitsandbytes

# HuggingFace transfer (fast dataset downloads)
pip install -q hf_transfer

# ── Verify GPU ───────────────────────────────────────────────────────
echo ""
echo "[3/5] Verifying GPU..."
python -c "
import torch
print(f'PyTorch:    {torch.__version__}')
print(f'CUDA:       {torch.version.cuda}')
print(f'GPU count:  {torch.cuda.device_count()}')
for i in range(torch.cuda.device_count()):
    name = torch.cuda.get_device_name(i)
    mem = torch.cuda.get_device_properties(i).total_mem / 1024**3
    print(f'  GPU {i}: {name} ({mem:.1f} GB)')
"

# ── Verify Unsloth ───────────────────────────────────────────────────
echo ""
echo "[4/5] Verifying Unsloth..."
python -c "
from unsloth import FastLanguageModel
print(f'Unsloth loaded successfully')
from trl import SFTTrainer
print(f'TRL SFTTrainer loaded successfully')
"

# ── Download dataset ─────────────────────────────────────────────────
echo ""
echo "[5/5] Pre-downloading dataset from HuggingFace..."
export HF_HUB_ENABLE_HF_TRANSFER=1
python -c "
from datasets import load_dataset
ds = load_dataset('odytrice/kenichi-sft')
print('Dataset splits:')
for name, split in ds.items():
    print(f'  {name}: {len(split):,} samples')
print('Dataset cached successfully.')
"

# ── Ready ────────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  Setup complete! Ready to train."
echo "============================================"
echo ""
echo "  To train Kenichi Thinking (Qwen3.5-27B):"
echo "    python configs/train_kenichi_thinking.py"
echo ""
echo "  To train Kenichi Flash (Devstral Small 2):"
echo "    python configs/train_kenichi_flash.py"
echo ""
echo "  After training, merge and export:"
echo "    python configs/merge_and_export.py --help"
echo ""
echo "  Monitor GPU usage:"
echo "    watch -n1 nvidia-smi"
echo "    nvtop"
echo ""
