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
#   - RunPod A100 80GB pod (PCIe or SXM)
#   - PyTorch 2.4+ CUDA image (RunPod's default pytorch template)
#
# Usage:
#   # 1. SSH into RunPod instance
#   # 2. Clone the repo:
#   cd /workspace && git clone https://github.com/odytrice/models.git && cd models
#   # 3. Run setup:
#   bash configs/runpod_setup.sh              # Flash only (skips GDN deps)
#   bash configs/runpod_setup.sh --thinking   # Include Qwen3.5 GDN deps
#   # 4. Train (pick one):
#   python configs/train_kenichi_thinking.py   # Pod A (needs --thinking)
#   python configs/train_kenichi_flash.py      # Pod B
#
# ============================================================================

set -e

# ── Parse arguments ──────────────────────────────────────────────────
INSTALL_THINKING=false
for arg in "$@"; do
  case $arg in
    --thinking) INSTALL_THINKING=true ;;
  esac
done

echo "============================================"
echo "  Kenichi Training — RunPod Setup"
echo "============================================"

# ── Symlink HF cache to /workspace ───────────────────────────────────
# Model weights (~55GB) overflow the container disk (20GB default).
# Redirect HF cache to /workspace which has hundreds of GB available.
# NOTE: Do NOT symlink pip cache — causes "Invalid cross-device link"
# errors when pip tries to hardlink wheel files across filesystems.
echo ""
echo "[0/6] Redirecting HuggingFace cache to /workspace..."
mkdir -p /workspace/.cache/huggingface
rm -rf /root/.cache/huggingface 2>/dev/null || true
ln -sf /workspace/.cache/huggingface /root/.cache/huggingface
echo "  HF cache -> /workspace/.cache/huggingface"

# ── System packages ──────────────────────────────────────────────────
echo ""
echo "[1/6] Installing system dependencies..."
apt-get update -qq && apt-get install -y -qq git-lfs htop nvtop 2>/dev/null || true

# ── Upgrade PyTorch ──────────────────────────────────────────────────
echo ""
echo "[2/6] Setting up PyTorch 2.5.1 + CUDA 12.4..."
pip install -q --upgrade pip

# Upgrade to PyTorch 2.5.1 (compatible with latest Unsloth)
# The RunPod image ships 2.4.1 which is too old for current Unsloth.
pip install torch==2.5.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

echo "  $(python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA {torch.version.cuda}')")"

# ── flash-attn ───────────────────────────────────────────────────────
echo ""
echo "[3/7] Installing flash-attn (may take a few minutes if building from source)..."
pip install -q flash-attn --no-build-isolation --no-cache-dir

# ── Qwen3.5 GDN dependencies (optional) ─────────────────────────────
echo ""
if [ "$INSTALL_THINKING" = true ]; then
  echo "[4/7] Installing causal-conv1d + flash-linear-attention (required for Qwen3.5 GDN layers)..."
  # Without these, Qwen3.5's Gated DeltaNet layers fall back to a slow torch
  # implementation that OOMs on long sequences.
  pip install -q causal-conv1d --no-build-isolation --no-cache-dir
  # Pin fla versions — latest requires Triton 3.2+ but torch 2.5.1 ships Triton 3.1.0
  pip install -q fla-core==0.3.2 flash-linear-attention==0.3.2 --no-build-isolation --no-cache-dir
else
  echo "[4/7] Skipping Qwen3.5 GDN deps (pass --thinking to install)"
fi

# ── Unsloth + dependencies ───────────────────────────────────────────
echo ""
echo "[5/7] Installing Unsloth + dependencies..."

# Install Unsloth with cu124-ampere-torch250 extras (manages its own version pins)
pip install "unsloth[cu124-ampere-torch250] @ git+https://github.com/unslothai/unsloth.git"

# Downgrade torchao — latest (0.13) uses torch.int1 which doesn't exist in torch 2.5
pip install -q "torchao==0.7.0"

# hf_transfer for fast dataset downloads
pip install -q hf_transfer

# ── Verify GPU ───────────────────────────────────────────────────────
echo ""
echo "[6/7] Verifying GPU..."
python -c "
import torch
print(f'PyTorch:    {torch.__version__}')
print(f'CUDA:       {torch.version.cuda}')
print(f'GPU count:  {torch.cuda.device_count()}')
for i in range(torch.cuda.device_count()):
    name = torch.cuda.get_device_name(i)
    mem = torch.cuda.get_device_properties(i).total_memory / 1024**3
    print(f'  GPU {i}: {name} ({mem:.1f} GB)')
"

# ── Verify Unsloth ───────────────────────────────────────────────────
echo ""
echo "[7/7] Verifying Unsloth..."
python -c "
from unsloth import FastLanguageModel
print('Unsloth:  OK')
from trl import SFTTrainer
print('TRL:      OK')
from datasets import load_dataset
print('Datasets: OK')
print('All checks passed!')
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
echo ""
