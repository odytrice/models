# Training Configuration & Cost Estimates

## Precision Strategy: Train in BF16, Quantize After

**Train at full BF16 precision with LoRA, then quantize to 4-bit GGUF/GPTQ for inference.**

Do NOT train on a pre-quantized (4-bit QLoRA) model. Post-training quantization produces better results because:

1. LoRA adapters learn on full-precision weights -- no quantization noise during training
2. After training, merge LoRA into the full-precision model, then quantize once
3. You keep the full BF16 merged model as an artifact -- can quantize to any precision (Q4_K_M, Q5_K_M, Q6_K, Q8_0)
4. Research consistently shows PTQ of a well-trained model outperforms training on a pre-quantized model

---

## Context Length: Single-Stage at 128K

**Train at 128K (131072 tokens), inference at 204800.**

Both Qwen3.5-27B and Devstral Small 2 already support 256K context natively from their base pretraining. The `max_seq_length` parameter during LoRA SFT only controls:
- How long the training examples are (padding/truncation boundary)
- How much VRAM the training run uses

It does NOT retrain or damage the model's RoPE/YaRN positional embeddings. The base model's context handling is untouched — our LoRA adapter only teaches domain knowledge.

### Why 128K and not smaller?

Token distribution analysis of the 7,556 training samples (character-based estimates):

| Percentile | Est. Tokens | Chars |
|-----------|-------------|-------|
| Median (P50) | ~3,500-4,000 | 13,831 |
| P90 | ~5,900-6,800 | 23,761 |
| P95 | ~8,000-9,100 | 31,993 |
| P99 | ~16,300-18,600 | 65,069 |
| Max | ~21,300-24,300 | 85,129 |

| max_seq_length | Samples that fit | Coverage |
|----------------|-----------------|----------|
| 16384 (16K) | ~4,615 | 61.1% |
| 32768 (32K) | ~7,208 | 95.4% |
| 65536 (64K) | ~7,483 | 99.0% |
| **131072 (128K)** | **7,556** | **100%** |

128K fits all samples with zero truncation. On A100 80GB, this is comfortable with packing enabled.

### No progressive context stages needed

The original plan had 4 progressive stages (8K → 16K → 128K → 256K) for training models to handle increasing context lengths. This was abandoned because:

1. We only have short-context training data (all 7,953 samples are ≤24K tokens estimated)
2. Both base models already handle 256K natively — no need to re-teach positional encoding
3. Progressive stages are for extending context beyond what the base model was pretrained on

---

## Training Plan: 2× A100 80GB in Parallel

| Pod | Model | Student | Format | Time | Cost (est) |
|-----|-------|---------|--------|------|------------|
| A | Qwen/Qwen3.5-27B | Kenichi Thinking | ChatML | ~2-3 hrs | ~$4-6 |
| B | Devstral Small 2 24B | Kenichi Flash | Mistral | ~2-3 hrs | ~$4-6 |

**Total estimated cost: ~$8-12** (2× A100 80GB at ~$1.79/hr each for ~2-3 hours)

Both models train on the same 7,953 samples (7,556 train / 397 val). The only difference is the chat template format applied at training time.

---

## LoRA Training Configuration

Identical for both models:

```python
# LoRA config
r = 16
lora_alpha = 32           # alpha/r ratio of 2
lora_dropout = 0.0
target_modules = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]
bias = "none"
use_gradient_checkpointing = "unsloth"  # 30% VRAM savings

# Training hyperparameters
max_seq_length = 131072   # 128K — zero truncation
batch_size = 1
gradient_accumulation = 8  # Effective batch size = 8
epochs = 3
learning_rate = 2e-4
warmup_ratio = 0.05       # 5% warmup
weight_decay = 0.01
lr_scheduler = "cosine"
optimizer = "adamw_8bit"
packing = True            # Critical — packs short sequences together
bf16 = True
```

### Model-specific differences

| Setting | Kenichi Thinking | Kenichi Flash |
|---------|-----------------|---------------|
| Base model | `Qwen/Qwen3.5-27B` | `unsloth/Devstral-Small-2-24B-Instruct-2512` |
| Chat template | `qwen-2.5` | `mistral` |
| Data split | `chatml_train` / `chatml_val` | `mistral_train` / `mistral_val` |
| Architecture | Dense 27B, 88 layers | Dense 24B (Ministral 3), 40 layers |
| Parameters | 27B | 24B |

---

## Training Scripts

| Script | Purpose |
|--------|---------|
| `configs/train_kenichi_thinking.py` | Qwen3.5-27B SFT with ChatML |
| `configs/train_kenichi_flash.py` | Devstral Small 2 SFT with Mistral format |
| `configs/merge_and_export.py` | Merge LoRA → GGUF export → HuggingFace push |
| `configs/runpod_setup.sh` | RunPod instance setup (deps, GPU verify, data download) |

### Quick start on RunPod

```bash
# 1. Clone repo on RunPod A100 instance
git clone https://github.com/<repo>/Models.git && cd Models

# 2. Run setup
bash configs/runpod_setup.sh

# 3. Train (Pod A: Thinking, Pod B: Flash)
python configs/train_kenichi_thinking.py   # Pod A
python configs/train_kenichi_flash.py      # Pod B

# 4. After training, merge and export
python configs/merge_and_export.py \
  --model Qwen/Qwen3.5-27B \
  --adapter ./outputs/kenichi-thinking/lora_adapter \
  --name kenichi-thinking \
  --push odytrice/kenichi-thinking

python configs/merge_and_export.py \
  --model unsloth/Devstral-Small-2-24B-Instruct-2512 \
  --adapter ./outputs/kenichi-flash/lora_adapter \
  --name kenichi-flash \
  --push odytrice/kenichi-flash
```

---

## Cost Summary

### Data Generation (Teachers)
- All three teachers accessible via **Ollama cloud subscription** -- no additional per-token API costs
- Data generation cost is effectively **$0 beyond the existing Ollama subscription**

### Training Cost

| Item | Cost |
|------|------|
| 2× A100 80GB RunPod (~2-3 hrs each) | ~$8-12 |
| Ollama Max subscription | Existing $100/mo |
| **Total** | **~$8-12** |

### Post-training: Quantization and Export
After training completes, merge LoRA adapters and export:
- **GGUF** (Q4_K_M, Q5_K_M, Q8_0) for llama.cpp / Ollama local inference
- Merged BF16 for HuggingFace
- Both fit comfortably in 32GB VRAM at Q4_K_M quantization
