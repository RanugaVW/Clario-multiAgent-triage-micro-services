
# ============================================================
# EXTRA CELL A: Full Metrics Tables (Precision / Recall / F1 per class)
# Matches the spreadsheet format shown — one table per task
# ============================================================
from sklearn.metrics import classification_report, accuracy_score
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

def build_metrics_table(y_true, y_pred, task_name: str) -> pd.DataFrame:
    """
    Builds a DataFrame matching the spreadsheet layout:
    Class/Metric | Precision | Recall | F1-Score
    With rows for each class + Overall Accuracy + Macro Avg + Weighted Avg
    """
    report = classification_report(
        y_true, y_pred,
        output_dict=True,
        zero_division=0
    )
    rows = []
    # Per-class rows (skip 'accuracy', 'macro avg', 'weighted avg' keys)
    skip_keys = {"accuracy", "macro avg", "weighted avg"}
    for label, vals in report.items():
        if label in skip_keys:
            continue
        rows.append({
            "Class / Metric": label,
            "Precision": round(vals["precision"], 4),
            "Recall":    round(vals["recall"],    4),
            "F1-Score":  round(vals["f1-score"],  4),
        })

    # Overall Accuracy row
    acc = accuracy_score(y_true, y_pred)
    rows.append({
        "Class / Metric": "Overall Accuracy",
        "Precision": "",
        "Recall":    "",
        "F1-Score":  round(acc, 4),
    })

    # Macro Avg
    m = report["macro avg"]
    rows.append({
        "Class / Metric": "Macro Avg",
        "Precision": round(m["precision"], 4),
        "Recall":    round(m["recall"],    4),
        "F1-Score":  round(m["f1-score"],  4),
    })

    # Weighted Avg
    w = report["weighted avg"]
    rows.append({
        "Class / Metric": "Weighted Avg",
        "Precision": round(w["precision"], 4),
        "Recall":    round(w["recall"],    4),
        "F1-Score":  round(w["f1-score"],  4),
    })

    df = pd.DataFrame(rows)
    df.index = [""] * len(df)   # hide numeric index for clean display
    print(f"\n{'='*55}")
    print(f"  {task_name.upper()} — Classification Metrics")
    print(f"{'='*55}")
    print(df.to_string(index=False))
    return df


df_metrics_priority  = build_metrics_table(y_true_priority,  y_pred_priority,  "Priority")
df_metrics_sentiment = build_metrics_table(y_true_sentiment, y_pred_sentiment, "Sentiment")
df_metrics_category  = build_metrics_table(y_true_category,  y_pred_category,  "Category")


# ============================================================
# EXTRA CELL B: Save all metrics to Excel (one sheet per task)
# ============================================================
import os

metrics_excel_path = os.path.join(OUTPUT_DIR, "clario_llm_metrics.xlsx")

with pd.ExcelWriter(metrics_excel_path, engine="openpyxl") as writer:
    df_metrics_priority.to_excel(writer,  sheet_name="Priority",  index=False)
    df_metrics_sentiment.to_excel(writer, sheet_name="Sentiment", index=False)
    df_metrics_category.to_excel(writer,  sheet_name="Category",  index=False)

print(f"\nMetrics saved to Excel: {metrics_excel_path}")

# Also save as individual CSVs
df_metrics_priority.to_csv( os.path.join(OUTPUT_DIR, "metrics_priority.csv"),  index=False)
df_metrics_sentiment.to_csv(os.path.join(OUTPUT_DIR, "metrics_sentiment.csv"), index=False)
df_metrics_category.to_csv( os.path.join(OUTPUT_DIR, "metrics_category.csv"),  index=False)
print("Individual CSVs saved.")


# ============================================================
# EXTRA CELL C: Visualise metrics — side-by-side bar chart
# per class for all 3 tasks (matches spreadsheet columns)
# ============================================================
import matplotlib.pyplot as plt
import numpy as np

def plot_full_metrics(ax, df_m, task_name, color_p, color_r, color_f):
    # Only class rows (exclude summary rows)
    summary_rows = {"Overall Accuracy", "Macro Avg", "Weighted Avg"}
    class_rows = df_m[~df_m["Class / Metric"].isin(summary_rows)].copy()
    labels     = class_rows["Class / Metric"].tolist()
    precision  = class_rows["Precision"].astype(float).tolist()
    recall     = class_rows["Recall"].astype(float).tolist()
    f1         = class_rows["F1-Score"].astype(float).tolist()

    x  = np.arange(len(labels))
    w  = 0.25
    b1 = ax.bar(x - w, precision, w, label="Precision", color=color_p, alpha=0.85)
    b2 = ax.bar(x,     recall,    w, label="Recall",    color=color_r, alpha=0.85)
    b3 = ax.bar(x + w, f1,        w, label="F1-Score",  color=color_f, alpha=0.85)

    ax.bar_label(b1, fmt="%.2f", fontsize=7, padding=2)
    ax.bar_label(b2, fmt="%.2f", fontsize=7, padding=2)
    ax.bar_label(b3, fmt="%.2f", fontsize=7, padding=2)

    # Add accuracy line
    acc_row = df_m[df_m["Class / Metric"] == "Overall Accuracy"]
    if not acc_row.empty:
        acc_val = float(acc_row["F1-Score"].values[0])
        ax.axhline(acc_val, color="red", linestyle="--", linewidth=1.2,
                   label=f"Accuracy={acc_val:.4f}")

    ax.set_title(task_name, fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Score")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)

fig, axes = plt.subplots(1, 3, figsize=(22, 6))
fig.suptitle("Fine-Tuned Model — Per-Class Metrics", fontsize=15, fontweight="bold", y=1.02)

plot_full_metrics(axes[0], df_metrics_priority,  "Priority",
                  "#4C72B0", "#55A868", "#C44E52")
plot_full_metrics(axes[1], df_metrics_sentiment, "Sentiment",
                  "#4C72B0", "#55A868", "#C44E52")
plot_full_metrics(axes[2], df_metrics_category,  "Category",
                  "#4C72B0", "#55A868", "#C44E52")

plt.tight_layout()
chart_path = os.path.join(OUTPUT_DIR, "metrics_full_chart.png")
plt.savefig(chart_path, dpi=150, bbox_inches="tight")
plt.show()
print(f"Chart saved: {chart_path}")


# ============================================================
# EXTRA CELL D: Save the COMPLETE model (merged weights)
# Merges LoRA adapters into base model → standalone deployable model
# ============================================================
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

print("\nMerging LoRA adapters into base model weights...")

# Load base model (no quantisation for merging)
base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.bfloat16,
    device_map="cpu",          # merge on CPU to avoid VRAM OOM
    token=HF_TOKEN,
    trust_remote_code=True,
)

# Load the LoRA adapter on top
peft_model = PeftModel.from_pretrained(base_model, final_model_path)

# Merge and unload — produces a plain HF model (no PEFT dependency)
merged_model = peft_model.merge_and_unload()
print("Merge complete.")

# Save merged model
merged_path = os.path.join(OUTPUT_DIR, "merged_final")
merged_model.save_pretrained(merged_path, safe_serialization=True)
tokenizer.save_pretrained(merged_path)

print(f"\n{'='*55}")
print(f"  COMPLETE MERGED MODEL SAVED")
print(f"  Path : {merged_path}")
print(f"  Files: {os.listdir(merged_path)}")
print(f"{'='*55}")
print("This folder is a fully self-contained HuggingFace model.")
print("Load it later with:")
print(f'  from transformers import AutoModelForCausalLM, AutoTokenizer')
print(f'  model = AutoModelForCausalLM.from_pretrained("{merged_path}")')
print(f'  tokenizer = AutoTokenizer.from_pretrained("{merged_path}")')
