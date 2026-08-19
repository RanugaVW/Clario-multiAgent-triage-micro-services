
# ============================================================
# Cell 1: Install Dependencies
# ============================================================
# !pip install -q transformers datasets peft trl bitsandbytes accelerate evaluate scikit-learn pandas matplotlib seaborn

# ============================================================
# Cell 2: Imports
# ============================================================
import json
import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

import torch
from datasets import load_dataset, Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    pipeline,
)
from peft import LoraConfig, get_peft_model, PeftModel
from trl import SFTTrainer, SFTConfig
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    f1_score,
)

print("PyTorch version:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    print("VRAM:", round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2), "GB")

# ============================================================
# Cell 3: Configuration
# ============================================================
# ── Model choice ───────────────────────────────────────────────────────────
# Option A: LLaMA 3.2 3B (gated — requires Meta access approval first at
#           https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct )
# MODEL_ID = "meta-llama/Llama-3.2-3B-Instruct"

# Option B: Qwen 2.5 3B Instruct (UNGATED — works immediately, no approval)
#           Same parameter count, strong multilabel classification performance.
MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
# ───────────────────────────────────────────────────────────────────────────

# ── Data path ──────────────────────────────────────────────
# On Kaggle set this to your dataset directory, e.g.:
#   DATA_PATH = "/kaggle/input/datasets/ranugaweerasekara/gemini-distillation-dataset"
# Locally set it to the direct .jsonl file, e.g.:
#   DATA_PATH = "/home/.../distilled_train.jsonl"
DATA_PATH = "/kaggle/input/datasets/ranugaweerasekara/gemini-distillation-dataset"

# ── Output directory ───────────────────────────────────────
# Kaggle only allows writes to /kaggle/working
if os.path.isdir("/kaggle/working"):
    OUTPUT_DIR = "/kaggle/working/llama32_clario_finetuned"
else:
    OUTPUT_DIR = "/home/ranuga-weerasekara/Desktop/clario/ml_finetuning/models/llama32_clario_finetuned"

os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"Output dir: {OUTPUT_DIR}")

MAX_SEQ_LENGTH = 1024
TRAIN_SPLIT = 0.85
VAL_SPLIT   = 0.10
TEST_SPLIT  = 0.05

PRIORITY_LABELS  = ["Low", "Medium", "High", "Critical"]
SENTIMENT_LABELS = ["Positive", "Neutral", "Negative"]

# ============================================================
# Cell 4: Load & Inspect JSONL (no CSV conversion needed)
# ============================================================
# Resolve DATA_PATH → a single .jsonl file whether it is a
# directory (Kaggle dataset mount) or a direct file path.
def resolve_jsonl_path(path: str) -> str:
    p = Path(path)
    if p.is_file():
        return str(p)                        # already a file
    if p.is_dir():
        # Search recursively for any .jsonl file
        matches = sorted(p.rglob("*.jsonl"))
        if not matches:
            raise FileNotFoundError(
                f"No .jsonl file found inside directory: {path}\n"
                f"Contents: {list(p.iterdir())}"
            )
        if len(matches) > 1:
            print(f"[INFO] Multiple .jsonl files found, using first: {matches[0]}")
            for m in matches:
                print(f"  - {m}")
        return str(matches[0])
    raise FileNotFoundError(f"Path does not exist: {path}")

jsonl_file = resolve_jsonl_path(DATA_PATH)
print(f"Loading data from: {jsonl_file}")

records = []
with open(jsonl_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            records.append(json.loads(line))

df = pd.DataFrame(records)
df["category"]  = df["labels"].apply(lambda x: x["category"])
df["priority"]  = df["labels"].apply(lambda x: x["priority"])
df["sentiment"] = df["labels"].apply(lambda x: x["sentiment"])

print(f"Total records: {len(df)}")
print("\nPriority distribution:\n", df["priority"].value_counts())
print("\nSentiment distribution:\n", df["sentiment"].value_counts())
print("\nTop 15 Categories:\n", df["category"].value_counts().head(15))

# ============================================================
# Cell 5: Normalise Category Labels (optional grouping)
# ============================================================
CATEGORY_MAP = {
    # Billing family
    "Billing & Refunds": "Billing & Refunds",
    "Billing & Payments": "Billing & Refunds",
    "Billing and Refunds": "Billing & Refunds",
    "Billing & Subscription": "Billing & Subscription",
    "Billing/Subscription Management": "Billing & Subscription",
    "Subscription & Billing": "Billing & Subscription",
    "Subscription Management": "Billing & Subscription",
    "Subscription Cancellation": "Billing & Subscription",
    "Billing and Subscription": "Billing & Subscription",
    "Billing/Subscription": "Billing & Subscription",
    "Billing and Payments": "Billing & Refunds",
    "Billing & Refund": "Billing & Refunds",
    "Billing & Enrollment": "Billing & Refunds",
    # Account family
    "Account Access": "Account Access",
    "Account Management": "Account Access",
    "User Access / Account Management": "Account Access",
    "Account Management / Access": "Account Access",
    # Auth family
    "Authentication/Access": "Authentication & Access",
    "Authentication & Access": "Authentication & Access",
    "Authentication & Security": "Authentication & Access",
    "Authentication": "Authentication & Access",
    "Access Control": "Authentication & Access",
    # Performance
    "Performance": "Performance",
    "Performance/Latency": "Performance",
    "Performance/Technical Issue": "Performance",
    # Technical Support
    "Technical Support": "Technical Support",
    "Technical Bug": "Technical Support",
    "Software Bug": "Technical Support",
    # Feature Request
    "Feature Request": "Feature Request",
    "Feature Request/Support": "Feature Request",
    # Misc
    "Data Integrity": "Data Integrity",
    "Data Synchronization": "Data Integrity",
    "Video Playback Issue": "Technical Support",
    "Video Playback": "Technical Support",
    "Payment Processing": "Billing & Refunds",
    "Transaction Discrepancy": "Billing & Refunds",
}

def normalise_category(cat):
    return CATEGORY_MAP.get(cat, cat)

df["category_norm"] = df["category"].apply(normalise_category)
CATEGORY_LABELS = sorted(df["category_norm"].unique().tolist())
print(f"\nNormalised categories ({len(CATEGORY_LABELS)}):\n", CATEGORY_LABELS)

# ============================================================
# Cell 6: Build Prompt Template
# ============================================================
SYSTEM_PROMPT = """You are Clario, an intelligent IT support ticket triage assistant.
Given a product name and issue description, predict three labels:
- priority: one of [Low, Medium, High, Critical]
- sentiment: one of [Positive, Neutral, Negative]
- category: one of the standard support categories

Respond ONLY in the following JSON format (no other text):
{"priority": "<value>", "sentiment": "<value>", "category": "<value>"}"""


def build_prompt(row):
    user_msg = (
        f"Product: {row['input_product']}\n"
        f"Issue: {row['input_issue_description']}"
    )
    assistant_msg = json.dumps({
        "priority": row["priority"],
        "sentiment": row["sentiment"],
        "category": row["category_norm"],
    })
    # Llama-3 chat template
    prompt = (
        f"<|begin_of_text|>"
        f"<|start_header_id|>system<|end_header_id|>\n{SYSTEM_PROMPT}<|eot_id|>"
        f"<|start_header_id|>user<|end_header_id|>\n{user_msg}<|eot_id|>"
        f"<|start_header_id|>assistant<|end_header_id|>\n{assistant_msg}<|eot_id|>"
    )
    return prompt


df["text"] = df.apply(build_prompt, axis=1)
print("Sample prompt:\n")
print(df["text"].iloc[0])

# ============================================================
# Cell 7: Train / Val / Test Split
# ============================================================
from sklearn.model_selection import train_test_split

df_train, df_temp = train_test_split(df, test_size=(1 - TRAIN_SPLIT), random_state=42, stratify=df["priority"])
df_val, df_test   = train_test_split(df_temp, test_size=0.33, random_state=42)

print(f"Train: {len(df_train)} | Val: {len(df_val)} | Test: {len(df_test)}")

ds_train = Dataset.from_pandas(df_train[["text"]].reset_index(drop=True))
ds_val   = Dataset.from_pandas(df_val[["text"]].reset_index(drop=True))

# ============================================================
# Cell 8: HuggingFace Authentication + Load Tokenizer & Model (4-bit QLoRA)
# ============================================================
# ── Authenticate with HuggingFace ────────────────────────────
# On Kaggle: Add your HF token under  Notebook → Add-ons → Secrets
#            Name it exactly  HF_TOKEN  and toggle "Attach to notebook"
# Locally:   Set the env var  export HF_TOKEN=hf_xxx...
import os
from huggingface_hub import login

HF_TOKEN = None

# 1) Try Kaggle Secrets first
try:
    from kaggle_secrets import UserSecretsClient
    HF_TOKEN = UserSecretsClient().get_secret("HF_TOKEN")
    print("[Auth] Loaded HF_TOKEN from Kaggle Secrets ✅")
except Exception:
    pass

# 2) Fall back to environment variable
if not HF_TOKEN:
    HF_TOKEN = os.environ.get("HF_TOKEN", None)
    if HF_TOKEN:
        print("[Auth] Loaded HF_TOKEN from environment variable ✅")

if not HF_TOKEN:
    raise ValueError(
        "HF_TOKEN not found!\n"
        "On Kaggle: Notebook → Add-ons → Secrets → add HF_TOKEN\n"
        "Locally  : export HF_TOKEN=hf_your_token_here"
    )

login(token=HF_TOKEN, add_to_git_credential=False)
print("[Auth] Logged in to HuggingFace ✅")

# ── 4-bit quantisation config ────────────────────────────────
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_ID, trust_remote_code=True, token=HF_TOKEN
)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    quantization_config=bnb_config,
    device_map="auto",
    token=HF_TOKEN,
    trust_remote_code=True,
)
model.config.use_cache = False

print("Model loaded. Parameters:")
total = sum(p.numel() for p in model.parameters())
print(f"  Total: {total/1e6:.1f}M")

# ============================================================
# Cell 9: LoRA Configuration
# ============================================================
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# ============================================================
# Cell 10: Training Arguments
# ============================================================
training_args = SFTConfig(
    output_dir=OUTPUT_DIR,
    num_train_epochs=3,
    per_device_train_batch_size=4,
    per_device_eval_batch_size=4,
    gradient_accumulation_steps=4,
    gradient_checkpointing=True,
    optim="paged_adamw_32bit",
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.05,
    logging_steps=50,
    eval_strategy="steps",
    eval_steps=200,
    save_strategy="steps",
    save_steps=200,
    save_total_limit=3,
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
    fp16=False,
    bf16=True,
    max_grad_norm=0.3,
    report_to="none",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_text_field="text",
    packing=False,
)

# ============================================================
# Cell 11: Train
# ============================================================
trainer = SFTTrainer(
    model=model,
    train_dataset=ds_train,
    eval_dataset=ds_val,
    args=training_args,
    tokenizer=tokenizer,
)

print("Starting fine-tuning...")
trainer.train()
print("Training complete!")

# ============================================================
# Cell 12: Save Model
# ============================================================
final_model_path = os.path.join(OUTPUT_DIR, "final")
trainer.model.save_pretrained(final_model_path)
tokenizer.save_pretrained(final_model_path)
print(f"Model saved to: {final_model_path}")

# ============================================================
# Cell 13: Inference Helper
# ============================================================
def build_inference_prompt(product: str, issue: str) -> str:
    return (
        f"<|begin_of_text|>"
        f"<|start_header_id|>system<|end_header_id|>\n{SYSTEM_PROMPT}<|eot_id|>"
        f"<|start_header_id|>user<|end_header_id|>\n"
        f"Product: {product}\nIssue: {issue}<|eot_id|>"
        f"<|start_header_id|>assistant<|end_header_id|>\n"
    )


def predict_single(product: str, issue: str, model, tokenizer, device="cuda") -> dict:
    prompt = build_inference_prompt(product, issue)
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=64,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    try:
        result = json.loads(generated.strip())
    except json.JSONDecodeError:
        # Try to extract JSON from output
        match = re.search(r'\{.*?\}', generated, re.DOTALL)
        result = json.loads(match.group()) if match else {"priority": "Unknown", "sentiment": "Unknown", "category": "Unknown"}
    return result


# ============================================================
# Cell 14: Batch Evaluate on Test Set
# ============================================================
# Load the fine-tuned model fresh for evaluation
eval_model = AutoModelForCausalLM.from_pretrained(
    final_model_path,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
)
eval_model = PeftModel.from_pretrained(eval_model, final_model_path)
eval_model.eval()

y_true_priority  = []
y_pred_priority  = []
y_true_sentiment = []
y_pred_sentiment = []
y_true_category  = []
y_pred_category  = []

print(f"Evaluating on {len(df_test)} test samples...")

for idx, row in df_test.iterrows():
    pred = predict_single(
        row["input_product"],
        row["input_issue_description"],
        eval_model, tokenizer
    )
    y_true_priority.append(row["priority"])
    y_pred_priority.append(pred.get("priority", "Unknown"))

    y_true_sentiment.append(row["sentiment"])
    y_pred_sentiment.append(pred.get("sentiment", "Unknown"))

    y_true_category.append(row["category_norm"])
    y_pred_category.append(pred.get("category", "Unknown"))

print("Evaluation complete!")

# ============================================================
# Cell 15: Metrics - Priority
# ============================================================
print("\n" + "="*60)
print("PRIORITY CLASSIFICATION REPORT")
print("="*60)
print(classification_report(y_true_priority, y_pred_priority, zero_division=0))

priority_acc = accuracy_score(y_true_priority, y_pred_priority)
priority_f1  = f1_score(y_true_priority, y_pred_priority, average="weighted", zero_division=0)
print(f"Priority  Accuracy : {priority_acc:.4f}")
print(f"Priority  F1 (weighted): {priority_f1:.4f}")

# ============================================================
# Cell 16: Metrics - Sentiment
# ============================================================
print("\n" + "="*60)
print("SENTIMENT CLASSIFICATION REPORT")
print("="*60)
print(classification_report(y_true_sentiment, y_pred_sentiment, zero_division=0))

sentiment_acc = accuracy_score(y_true_sentiment, y_pred_sentiment)
sentiment_f1  = f1_score(y_true_sentiment, y_pred_sentiment, average="weighted", zero_division=0)
print(f"Sentiment Accuracy : {sentiment_acc:.4f}")
print(f"Sentiment F1 (weighted): {sentiment_f1:.4f}")

# ============================================================
# Cell 17: Metrics - Category
# ============================================================
print("\n" + "="*60)
print("CATEGORY CLASSIFICATION REPORT")
print("="*60)
print(classification_report(y_true_category, y_pred_category, zero_division=0))

category_acc = accuracy_score(y_true_category, y_pred_category)
category_f1  = f1_score(y_true_category, y_pred_category, average="weighted", zero_division=0)
print(f"Category  Accuracy : {category_acc:.4f}")
print(f"Category  F1 (weighted): {category_f1:.4f}")

# ============================================================
# Cell 18: Summary Table
# ============================================================
summary = pd.DataFrame({
    "Task":     ["Priority", "Sentiment", "Category"],
    "Accuracy": [priority_acc, sentiment_acc, category_acc],
    "F1 (weighted)": [priority_f1, sentiment_f1, category_f1],
})
print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print(summary.to_string(index=False))

# ============================================================
# Cell 19: Confusion Matrices (plots)
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(24, 7))

def plot_cm(ax, y_true, y_pred, title, labels):
    all_labels = sorted(set(y_true + y_pred))
    cm = confusion_matrix(y_true, y_pred, labels=all_labels)
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=all_labels, yticklabels=all_labels, ax=ax)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

plot_cm(axes[0], y_true_priority,  y_pred_priority,  "Priority Confusion Matrix",  PRIORITY_LABELS)
plot_cm(axes[1], y_true_sentiment, y_pred_sentiment, "Sentiment Confusion Matrix", SENTIMENT_LABELS)
plot_cm(axes[2], y_true_category,  y_pred_category,  "Category Confusion Matrix",  CATEGORY_LABELS)

plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "confusion_matrices.png"), dpi=150, bbox_inches="tight")
plt.show()

# ============================================================
# Cell 20: Per-class F1 Bar Charts
# ============================================================
from sklearn.metrics import precision_recall_fscore_support

def plot_per_class_f1(ax, y_true, y_pred, title):
    labels = sorted(set(y_true))
    _, _, f1s, _ = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    bars = ax.barh(labels, f1s, color="steelblue")
    ax.bar_label(bars, fmt="%.2f", padding=3)
    ax.set_xlim(0, 1.1)
    ax.set_title(title, fontweight="bold")
    ax.set_xlabel("F1 Score")

fig2, axes2 = plt.subplots(1, 3, figsize=(22, 6))
plot_per_class_f1(axes2[0], y_true_priority,  y_pred_priority,  "Priority  — Per-class F1")
plot_per_class_f1(axes2[1], y_true_sentiment, y_pred_sentiment, "Sentiment — Per-class F1")
plot_per_class_f1(axes2[2], y_true_category,  y_pred_category,  "Category  — Per-class F1")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "per_class_f1.png"), dpi=150, bbox_inches="tight")
plt.show()

# ============================================================
# Cell 21: Save Detailed Results CSV
# ============================================================
results_df = df_test[["input_product", "input_issue_description", "priority", "sentiment", "category_norm"]].copy()
results_df["pred_priority"]  = y_pred_priority
results_df["pred_sentiment"] = y_pred_sentiment
results_df["pred_category"]  = y_pred_category
results_df["priority_correct"]  = results_df["priority"]      == results_df["pred_priority"]
results_df["sentiment_correct"] = results_df["sentiment"]     == results_df["pred_sentiment"]
results_df["category_correct"]  = results_df["category_norm"] == results_df["pred_category"]

results_csv = os.path.join(OUTPUT_DIR, "test_results.csv")
results_df.to_csv(results_csv, index=False)
print(f"\nDetailed results saved to: {results_csv}")

# ============================================================
# Cell 22: Quick Inference Demo
# ============================================================
demo_cases = [
    ("Video Classroom", "The video player keeps buffering and the course is unusable. I want a refund."),
    ("Payment & Billing", "I was charged twice this month for the same subscription."),
    ("Student Web Portal", "Can you add a dark mode to the portal?"),
    ("Assessment Module", "Cannot login to complete my final assessment exam."),
]

print("\n" + "="*60)
print("DEMO INFERENCE")
print("="*60)
for product, issue in demo_cases:
    pred = predict_single(product, issue, eval_model, tokenizer)
    print(f"\nProduct : {product}")
    print(f"Issue   : {issue}")
    print(f"▶ Priority={pred.get('priority')}  Sentiment={pred.get('sentiment')}  Category={pred.get('category')}")

print("\nAll done! Fine-tuned model saved at:", final_model_path)
