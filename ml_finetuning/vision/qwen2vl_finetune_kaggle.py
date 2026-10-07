"""QLoRA fine-tune of Qwen2-VL-2B-Instruct for error-text extraction from screenshots.

Written to run top-to-bottom in a single Kaggle notebook cell (or as a Kaggle Script)
on one T4/P100. Same QLoRA settings as our Llama-3.2 fine-tune: r=16, alpha=32, lr=2e-4.

WHAT IT LEARNS
    input   : a screenshot + a fixed instruction
    output  : only the literal error text, nothing else
The whole point is to beat the prompt-only baseline on the task Tesseract fails at -
ignoring buttons, menus and watermarks - and to cut the 41% "NO_ERROR_TEXT_FOUND"
false-negative rate the prompt-only 2B model showed in Testing/11.

KAGGLE SETUP
    1. Notebook settings -> Accelerator: GPU T4 x2 (one is used) -> Internet: ON
    2. Add Data -> upload the folder produced by generate_error_screenshots.py
       as a dataset named  clario-vision-train   (images/ + labels.jsonl)
    3. Add Data -> upload Testing/11's sample_images/ + ground_truth.csv
       as a dataset named  clario-vision-test    (held out, never trained on)
    4. Paste this file into a cell and run.

OUTPUT
    /kaggle/working/qwen2vl-clario-adapter/   LoRA adapter + processor (small, ~80MB)
    /kaggle/working/qwen2vl-clario-adapter.zip
    /kaggle/working/eval_after_finetune.csv   per-image scores on the 34 real screenshots
"""
from __future__ import annotations

import csv
import difflib
import inspect
import json
import os
import random
import subprocess
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# 0. Dependencies.  Qwen2-VL needs transformers >= 4.45.  Note this is a FLOOR, not a
#    pin: Kaggle now preinstalls transformers 5.x, which satisfies it and installs
#    nothing.  v5 removed `warmup_ratio`, so the training args below feature-detect.
# ─────────────────────────────────────────────────────────────────────────────
if os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                    "transformers>=4.45.0", "accelerate>=0.34", "peft>=0.13",
                    "bitsandbytes>=0.44", "qwen-vl-utils", "Pillow"], check=True)

# Read at the first CUDA allocation, so it has to be set before torch initialises
# the device. The OOM report showed 695 MiB reserved-but-unallocated: that is
# fragmentation, and expandable segments let those blocks be reused.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from PIL import Image
from torch.utils.data import Dataset
from transformers import (AutoProcessor, BitsAndBytesConfig,
                          Qwen2VLForConditionalGeneration, Trainer, TrainingArguments)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

import transformers
print("transformers", transformers.__version__, "| torch", torch.__version__)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Config
# ─────────────────────────────────────────────────────────────────────────────
MODEL_ID = "Qwen/Qwen2-VL-2B-Instruct"
OUT_DIR = Path("/kaggle/working/qwen2vl-clario-adapter")


def find_input(marker: str) -> Path | None:
    """Locate a dataset folder under /kaggle/input by a file it must contain.

    Kaggle mounts a dataset at /kaggle/input/<slug>/, and the slug is not the
    URL you see in the browser. Searching for the marker file means the script
    works whether you uploaded one combined dataset or two separate ones, and
    whatever Kaggle did with the zip structure.
    """
    base = Path("/kaggle/input")
    if not base.exists():
        return None
    hits = sorted(base.rglob(marker))
    return hits[0].parent if hits else None


TRAIN_DIR = find_input("labels.jsonl")
TEST_DIR = find_input("ground_truth.csv")
print("TRAIN_DIR ->", TRAIN_DIR)
print("TEST_DIR  ->", TEST_DIR)
assert TRAIN_DIR is not None, (
    "labels.jsonl not found anywhere under /kaggle/input. "
    "Did you attach the training dataset? Run: !find /kaggle/input -maxdepth 3")
assert (TRAIN_DIR / "images").is_dir(), f"no images/ folder beside labels.jsonl in {TRAIN_DIR}"
if TEST_DIR is None:
    print("WARNING: ground_truth.csv not found - training will run, "
          "but the held-out evaluation at the end will be skipped.")

# Visual-token budget. Qwen2-VL turns an image into (h/28)*(w/28) tokens, so an
# uncapped 1440x900 screenshot costs ~1,600 tokens and will OOM a T4. 256..768
# patches keeps the error text readable while fitting comfortably in 16GB.
MIN_PIXELS = 256 * 28 * 28
MAX_PIXELS = 768 * 28 * 28

# The exact prompt production uses, so the adapter is trained for the real call.
PROMPT = (
    "You are an error-log extractor analyzing a screenshot. Identify and "
    "output ONLY the literal error message(s), exception text, stack trace "
    "lines, or warning/error codes visible in the image. Do not include "
    "button labels, menu items, navigation bars, timestamps, watermarks, "
    "decorative graphics, background patterns, or any other visual noise. "
    "Do not summarize, paraphrase, or add commentary - reproduce the error "
    "text exactly as it appears. If no error text is visible in the image, "
    "respond with exactly: NO_ERROR_TEXT_FOUND"
)

# 1 epoch over 3,000 images is ~3-4h on a Kaggle T4 and is usually enough for a task
# this narrow. Raise to 2 only if the held-out score at the end says it is still learning.
EPOCHS = 1
SEED = 42
random.seed(SEED)
torch.manual_seed(SEED)

# ─────────────────────────────────────────────────────────────────────────────
# 2. Processor and 4-bit model
# ─────────────────────────────────────────────────────────────────────────────
processor = AutoProcessor.from_pretrained(MODEL_ID, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS)
processor.tokenizer.padding_side = "right"

bnb = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)
try:
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        MODEL_ID, quantization_config=bnb, dtype=torch.float16, device_map={"": 0})
except TypeError:            # transformers 4.x still calls it torch_dtype
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        MODEL_ID, quantization_config=bnb, torch_dtype=torch.float16, device_map={"": 0})
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
model.config.use_cache = False
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})

# LoRA on the language model only - the vision tower uses different module names
# (attn.qkv / attn.proj / mlp.fc1), so this list cannot touch it. We freeze the
# vision encoder on purpose: 3k screenshots is far too little to retrain sight.
TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
hit = {n.split(".")[-1] for n, _ in model.named_modules() if n.split(".")[-1] in TARGETS}
print("LoRA will wrap:", sorted(hit))
assert not any("visual" in n for n, _ in model.named_modules()
               if n.split(".")[-1] in TARGETS), "vision tower would be trained - check targets"

model = get_peft_model(model, LoraConfig(
    r=16, lora_alpha=32, target_modules=TARGETS,
    lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
))
model.print_trainable_parameters()

IMAGE_PAD_ID = processor.tokenizer.convert_tokens_to_ids("<|image_pad|>")
ASSISTANT_MARK = processor.tokenizer("<|im_start|>assistant\n", add_special_tokens=False).input_ids


# ─────────────────────────────────────────────────────────────────────────────
# 3. Dataset
# ─────────────────────────────────────────────────────────────────────────────
class ErrorShotDataset(Dataset):
    """One screenshot -> the error text that should be read out of it."""

    def __init__(self, root: Path, rows: list[dict]):
        self.root, self.rows = root, rows

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, i: int) -> dict:
        r = self.rows[i]
        return {"image": Image.open(self.root / r["image"]).convert("RGB"), "answer": r["error"]}


def collate(batch: list[dict]) -> dict:
    texts, images = [], []
    for b in batch:
        msgs = [
            {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]},
            {"role": "assistant", "content": [{"type": "text", "text": b["answer"]}]},
        ]
        texts.append(processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False))
        images.append(b["image"])

    enc = processor(text=texts, images=images, return_tensors="pt", padding=True)
    labels = enc["input_ids"].clone()
    labels[labels == processor.tokenizer.pad_token_id] = -100
    labels[labels == IMAGE_PAD_ID] = -100  # never ask it to predict image tokens

    # Train only on the assistant's answer: mask everything up to and including
    # the "<|im_start|>assistant\n" header on each row.
    m = len(ASSISTANT_MARK)
    for row in range(labels.size(0)):
        ids = enc["input_ids"][row].tolist()
        cut = 0
        for j in range(len(ids) - m, -1, -1):
            if ids[j:j + m] == ASSISTANT_MARK:
                cut = j + m
                break
        labels[row, :cut] = -100
    enc["labels"] = labels
    return enc


rows = [json.loads(l) for l in open(TRAIN_DIR / "labels.jsonl", encoding="utf-8")]
random.shuffle(rows)
split = max(1, int(len(rows) * 0.05))
train_ds = ErrorShotDataset(TRAIN_DIR, rows[split:])
val_ds = ErrorShotDataset(TRAIN_DIR, rows[:split])
print(f"train {len(train_ds)}  |  val {len(val_ds)}")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Train
# ─────────────────────────────────────────────────────────────────────────────
# Kaggle's preinstalled transformers moves between 4.x and 5.x, and several
# TrainingArguments kwargs were renamed across that boundary. Rather than guess,
# inspect the installed signature and send only what it accepts.
_TA_PARAMS = set(inspect.signature(TrainingArguments.__init__).parameters)

# The asymmetric one, and the reason this block exists: v5 removed `warmup_ratio`
# and folded it into `warmup_steps`, which now reads a float < 1 as a fraction.
# v5 raises TypeError on `warmup_ratio` - loud, you would notice. But v4 happily
# accepts `warmup_steps=0.03` and warms up for 0.03 steps, i.e. not at all. That
# failure is silent, so picking the right name matters more than it looks.
WARMUP_FRACTION = 0.03
warmup_kwargs = ({"warmup_ratio": WARMUP_FRACTION} if "warmup_ratio" in _TA_PARAMS
                 else {"warmup_steps": WARMUP_FRACTION})

# `evaluation_strategy` was renamed `eval_strategy` in 4.41 and the old name is gone in v5.
eval_key = "eval_strategy" if "eval_strategy" in _TA_PARAMS else "evaluation_strategy"

wanted = {
    "output_dir": "/kaggle/working/ckpt",
    "per_device_train_batch_size": 1,     # one screenshot at a time - they are token-heavy
    # Must be set explicitly: the default is 8, and eval ignores the train batch
    # size. A 2.5-hour run died at the first eval because 8 screenshots of logits
    # (8 x ~1.9k tokens x 151,936 vocab) hit `logits.float()` in ForCausalLMLoss
    # and asked CUDA for 8.51 GiB in one allocation. Screenshots are token-heavy
    # at eval for exactly the same reason they are at train time.
    "per_device_eval_batch_size": 1,
    # Only the eval loss is used (checkpoint selection). Without this the Trainer
    # gathers every batch's logits to compare predictions - across 150 validation
    # screenshots that is far larger than the model itself.
    "prediction_loss_only": True,
    "eval_accumulation_steps": 1,         # anything retained moves to CPU each step
    "gradient_accumulation_steps": 16,    # effective batch 16, same ballpark as the Llama run
    "num_train_epochs": EPOCHS,
    "learning_rate": 2e-4,
    "lr_scheduler_type": "cosine",
    **warmup_kwargs,
    "logging_steps": 25,
    eval_key: "steps",
    "eval_steps": 200,
    "save_strategy": "steps",
    # Deliberately smaller than eval_steps. Transformers evaluates *before* it
    # saves inside the same _maybe_log_save_evaluate call, so when save_steps and
    # eval_steps were both 200 a crash in the first eval threw away every one of
    # the 200 steps that preceded it. Saving more often caps what a failure costs.
    "save_steps": 50,
    "save_total_limit": 2,
    "fp16": True,
    "optim": "paged_adamw_8bit",          # pages optimiser state to CPU - keeps a T4 alive
    "gradient_checkpointing": True,
    "gradient_checkpointing_kwargs": {"use_reentrant": False},
    "dataloader_num_workers": 2,
    "remove_unused_columns": False,       # our collator needs the raw PIL images
    "report_to": "none",
    "seed": SEED,
}
accepted = {k: v for k, v in wanted.items() if k in _TA_PARAMS}
dropped = sorted(set(wanted) - set(accepted))
print("warmup kwarg ->", list(warmup_kwargs)[0], "| eval kwarg ->", eval_key)
if dropped:
    print("NOTE: this transformers version does not accept:", dropped)
args = TrainingArguments(**accepted)

_TR_PARAMS = set(inspect.signature(Trainer.__init__).parameters)
trainer_kwargs = dict(model=model, args=args, train_dataset=train_ds,
                      eval_dataset=val_ds, data_collator=collate)
# v5 renamed `tokenizer` to `processing_class`; passing the processor lets Trainer
# save it alongside checkpoints, which is harmless and occasionally useful.
if "processing_class" in _TR_PARAMS:
    trainer_kwargs["processing_class"] = processor
trainer = Trainer(**trainer_kwargs)
trainer.train()

# ─────────────────────────────────────────────────────────────────────────────
# 5. Save the adapter (and the processor, or inference will mis-size images)
# ─────────────────────────────────────────────────────────────────────────────
OUT_DIR.mkdir(parents=True, exist_ok=True)
model.save_pretrained(OUT_DIR)
processor.save_pretrained(OUT_DIR)
(OUT_DIR / "training_notes.json").write_text(json.dumps({
    "base_model": MODEL_ID,
    "method": "QLoRA (4-bit NF4) on the language model; vision encoder frozen",
    "lora": {"r": 16, "alpha": 32, "dropout": 0.05, "targets": TARGETS},
    "train_images": len(train_ds),
    "epochs": EPOCHS,
    "learning_rate": args.learning_rate,
    "min_pixels": MIN_PIXELS, "max_pixels": MAX_PIXELS,
    "prompt": PROMPT,
    "test_set": "Testing/11 34 real screenshots - held out, never trained on",
}, indent=2))
subprocess.run(["zip", "-qr", "/kaggle/working/qwen2vl-clario-adapter.zip", str(OUT_DIR)], check=False)
print("saved ->", OUT_DIR)

# ─────────────────────────────────────────────────────────────────────────────
# 6. Score the 34 real screenshots - the same difflib ratio Testing/11 uses,
#    so the number is directly comparable to Tesseract 0.38 / prompt-only 0.59
# ─────────────────────────────────────────────────────────────────────────────
model.eval()
model.config.use_cache = True

gt_path = next(TEST_DIR.rglob("ground_truth.csv"), None) if TEST_DIR else None
if gt_path is None:
    print("No ground_truth.csv found - skipping the held-out evaluation.")
else:
    img_root = gt_path.parent
    results, misses = [], 0
    with open(gt_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name, truth = row["Image Name"], row["Original Error"]
            path = next(img_root.rglob(name), None)
            if path is None:
                continue
            msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]}]
            text = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            img = Image.open(path).convert("RGB")
            enc = processor(text=[text], images=[img], return_tensors="pt").to(model.device)
            with torch.no_grad():
                out = model.generate(**enc, max_new_tokens=256, do_sample=False)
            pred = processor.batch_decode(out[:, enc["input_ids"].shape[1]:],
                                          skip_special_tokens=True)[0].strip()
            sim = difflib.SequenceMatcher(None, pred, truth).ratio()
            misses += int("NO_ERROR_TEXT_FOUND" in pred)
            results.append({"image": name, "similarity": round(sim, 4),
                            "false_negative": "NO_ERROR_TEXT_FOUND" in pred,
                            "prediction": pred, "ground_truth": truth})

    with open("/kaggle/working/eval_after_finetune.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)

    mean = sum(r["similarity"] for r in results) / len(results)
    print(f"\nHeld-out set: {len(results)} real screenshots")
    print(f"  mean similarity      {mean:.3f}   (Tesseract 0.38 | prompt-only Qwen2-VL 0.59)")
    print(f"  false negatives      {misses}/{len(results)} = {misses / len(results):.0%}"
          f"   (prompt-only was 41%)")
    print("  per-image scores -> /kaggle/working/eval_after_finetune.csv")
