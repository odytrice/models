"""
Kenichi Thinking: Qwen3.5-27B Domain-Specialized SFT
=====================================================

Reasoning-first coding model specialized for F#, Svelte 5, TypeScript,
.NET, Docker, and Kubernetes. Has native <think> mode for step-by-step
reasoning before generating code.

- Base model: Qwen/Qwen3.5-27B (dense, 27B params, 256K native context)
- Format: ChatML (Qwen native)
- Data: 7,556 train / 397 val samples from odytrice/kenichi-sft
- Training: BF16 LoRA on A100 80GB, single-stage SFT
- Expected: ~2-3 hours on A100 80GB

Usage:
  # From HuggingFace dataset (recommended on RunPod):
  python train_kenichi_thinking.py

  # From local JSONL files:
  python train_kenichi_thinking.py --data ./data/chatml/stage1_train.jsonl --val ./data/chatml/stage1_val.jsonl

  # Resume from checkpoint:
  python train_kenichi_thinking.py --resume ./outputs/kenichi-thinking/checkpoint-500
"""

import argparse
from pathlib import Path

from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

# ── Model Configuration ──────────────────────────────────────────────
MODEL_NAME = "Qwen/Qwen3.5-27B"
MAX_SEQ_LENGTH = 32768  # 32K — covers 95.4% of samples, 4x better packing density
LOAD_IN_4BIT = False  # Train in BF16, NOT QLoRA
DTYPE = None  # Auto-detect (BF16 on A100)

# ── LoRA Configuration ───────────────────────────────────────────────
LORA_R = 16
LORA_ALPHA = 32  # alpha/r ratio of 2
LORA_DROPOUT = 0.0
TARGET_MODULES = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
]

# ── Training Hyperparameters ─────────────────────────────────────────
BATCH_SIZE = 1
GRADIENT_ACCUMULATION = 8  # Effective batch size = 8
EPOCHS = 3  # 3 epochs for 7,556 samples
LEARNING_RATE = 2e-4
WARMUP_RATIO = 0.05  # 5% warmup (more robust than fixed steps)
WEIGHT_DECAY = 0.01
LR_SCHEDULER = "cosine"
SEED = 3407
OUTPUT_DIR = "./outputs/kenichi-thinking"

# ── System Prompt ────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are Kenichi, an expert coding assistant specialized in "
    "F#, .NET, Svelte 5, SvelteKit, TypeScript, Docker, and Kubernetes. "
    "You write clean, idiomatic, and well-structured code with clear explanations."
)

# ── HuggingFace Dataset ─────────────────────────────────────────────
HF_DATASET = "odytrice/kenichi-sft"
HF_TRAIN_SPLIT = "chatml_train"
HF_VAL_SPLIT = "chatml_val"


def main(data_path: str = None, val_path: str = None, resume: str = None):
    print("=" * 60)
    print("  Kenichi Thinking — Qwen3.5-27B Domain-Specialized SFT")
    print("=" * 60)
    print(f"  Model:          {MODEL_NAME}")
    print(f"  Max seq length: {MAX_SEQ_LENGTH:,}")
    print(f"  LoRA rank:      {LORA_R} (alpha={LORA_ALPHA})")
    print(f"  Epochs:         {EPOCHS}")
    print(f"  Effective batch: {BATCH_SIZE * GRADIENT_ACCUMULATION}")
    print(f"  Output:         {OUTPUT_DIR}")
    print("=" * 60)

    # ── Load Model ───────────────────────────────────────────────────
    print("\n[1/5] Loading model...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=LOAD_IN_4BIT,
        dtype=DTYPE,
    )

    # ── Apply LoRA ───────────────────────────────────────────────────
    print("[2/5] Applying LoRA adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        target_modules=TARGET_MODULES,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        use_gradient_checkpointing="unsloth",  # 30% less VRAM
        random_state=SEED,
        max_seq_length=MAX_SEQ_LENGTH,
    )

    # ── Chat Template ────────────────────────────────────────────────
    tokenizer = get_chat_template(tokenizer, chat_template="qwen-2.5")

    def formatting_func(examples):
        texts = []
        for messages in examples["messages"]:
            # Inject system prompt at the start of every conversation
            messages_with_system = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *messages,
            ]
            text = tokenizer.apply_chat_template(
                messages_with_system, tokenize=False, add_generation_prompt=False
            )
            texts.append(text)
        return {"text": texts}

    # ── Load Dataset ─────────────────────────────────────────────────
    print("[3/5] Loading dataset...")
    if data_path and Path(data_path).exists():
        print(f"  Source: local file {data_path}")
        dataset = load_dataset("json", data_files=data_path, split="train")
    else:
        print(f"  Source: {HF_DATASET} ({HF_TRAIN_SPLIT})")
        dataset = load_dataset(HF_DATASET, split=HF_TRAIN_SPLIT)

    dataset = dataset.map(formatting_func, batched=True)

    eval_dataset = None
    if val_path and Path(val_path).exists():
        eval_dataset = load_dataset("json", data_files=val_path, split="train")
        eval_dataset = eval_dataset.map(formatting_func, batched=True)
    elif not data_path:
        eval_dataset = load_dataset(HF_DATASET, split=HF_VAL_SPLIT)
        eval_dataset = eval_dataset.map(formatting_func, batched=True)

    print(f"  Training samples:   {len(dataset):,}")
    if eval_dataset:
        print(f"  Validation samples: {len(eval_dataset):,}")

    # ── Training Arguments ───────────────────────────────────────────
    print("[4/5] Configuring trainer...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION,
        learning_rate=LEARNING_RATE,
        warmup_ratio=WARMUP_RATIO,
        weight_decay=WEIGHT_DECAY,
        lr_scheduler_type=LR_SCHEDULER,
        bf16=True,
        fp16=False,
        logging_steps=10,
        save_strategy="steps",
        save_steps=250,
        save_total_limit=3,
        eval_strategy="steps" if eval_dataset else "no",
        eval_steps=250 if eval_dataset else None,
        load_best_model_at_end=True if eval_dataset else False,
        metric_for_best_model="eval_loss" if eval_dataset else None,
        seed=SEED,
        report_to="none",  # Set to "wandb" for Weights & Biases tracking
        gradient_checkpointing=True,
        optim="adamw_8bit",
        dataloader_num_workers=4,
    )

    # ── Trainer ──────────────────────────────────────────────────────
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        eval_dataset=eval_dataset,
        args=training_args,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        packing=True,  # Pack short sequences together — critical for efficiency
    )

    # ── Train ────────────────────────────────────────────────────────
    print("[5/5] Starting training...")
    if resume and Path(resume).exists():
        print(f"  Resuming from checkpoint: {resume}")
        trainer.train(resume_from_checkpoint=resume)
    else:
        trainer.train()

    # ── Save ─────────────────────────────────────────────────────────
    adapter_dir = f"{OUTPUT_DIR}/lora_adapter"
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    print(f"\nTraining complete!")
    print(f"LoRA adapter saved to: {adapter_dir}")
    print(
        f"\nNext step: python merge_and_export.py --model {MODEL_NAME} --adapter {adapter_dir} --name kenichi-thinking"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Kenichi Thinking (Qwen3.5-27B)")
    parser.add_argument(
        "--data", default=None, help="Training JSONL (default: HuggingFace)"
    )
    parser.add_argument(
        "--val", default=None, help="Validation JSONL (default: HuggingFace)"
    )
    parser.add_argument(
        "--resume", default=None, help="Resume from checkpoint directory"
    )
    args = parser.parse_args()
    main(args.data, args.val, args.resume)
