"""
Generates every figure used in main.tex from numbers already published in:
  - Reserach Paper Comparison/README.md            (Sections 12, 15.2, 15.3)
  - Testing/12-Data-Science-Evaluation/Track-A-Retrieval-Quality/TRACK_A_CONCLUSION.md
  - Testing/12-Data-Science-Evaluation/Track-D-Judge-Reliability/README.md

No numbers here are invented; every value is copy-checked against those files.
Run: python3 generate_figures.py
Output: ./figures/*.pdf (vector, safe to \\includegraphics in LaTeX)
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import os

OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "legend.fontsize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "figure.dpi": 150,
})

C_PAPER = "#7f8c8d"
C_OURS = "#2c6fbb"
C_ACCENT = "#c0392b"
C_GOOD = "#2e8b57"


# ---------------------------------------------------------------------------
# Figure 1: Category classification accuracy, paper vs our reproduction
# Source: README.md Section 15.2
# ---------------------------------------------------------------------------
models_cat = ["Logistic\nRegression", "SVM", "XGBoost", "Gradient\nBoosting",
              "Random\nForest", "Decision\nTree", "Naive\nBayes", "BERT", "RNN\n(BiLSTM)", "CNN\n(TextCNN)"]
paper_cat = [0.9199, 0.9151, 0.9117, 0.9045, 0.8113, 0.7844, 0.7187, 0.81, 0.80, 0.80]
ours_cat = [0.93475, 0.94175, 0.92375, 0.90600, 0.91625, 0.88850, 0.90700, 0.95350, 0.95000, 0.93750]

fig, ax = plt.subplots(figsize=(7.0, 2.6))
x = np.arange(len(models_cat))
w = 0.38
ax.bar(x - w/2, paper_cat, w, label="Paper (78,313 financial complaints)", color=C_PAPER)
ax.bar(x + w/2, ours_cat, w, label="Our reproduction (20,000 LMS tickets)", color=C_OURS)
ax.set_ylabel("Accuracy")
ax.set_ylim(0.6, 1.0)
ax.set_xticks(x)
ax.set_xticklabels(models_cat)
ax.set_title("Category classification accuracy: paper's method reproduced on our data (8 classes)")
ax.legend(loc="lower right", frameon=False)
ax.spines[["top", "right"]].set_visible(False)
ax.axhline(1/8, color="gray", ls=":", lw=0.8)
ax.text(len(models_cat) - 0.6, 1/8 + 0.012, "random guess (1/8)", fontsize=6, color="gray")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig1_category_accuracy.pdf"), bbox_inches='tight')
plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 2: Priority classification accuracy, paper (binary) vs ours (4-class)
# Source: README.md Section 15.3 -- NOT directly comparable, task shape differs.
# ---------------------------------------------------------------------------
models_pri = ["Decision\nTree", "XGBoost", "Gradient\nBoosting", "SVM", "Random\nForest",
              "Logistic\nRegression", "Naive\nBayes", "BERT", "RNN\n(BiLSTM)", "CNN\n(TextCNN)"]
paper_pri = [0.9996, 0.9973, 0.9884, 0.9468, 0.9003, 0.9011, 0.8939, 0.92, 0.92, 0.91]
ours_pri = [0.48650, 0.55900, 0.53025, 0.58225, 0.55475, 0.58075, 0.56500, 0.61150, 0.57850, 0.56075]

fig, ax = plt.subplots(figsize=(7.0, 2.8))
x = np.arange(len(models_pri))
w = 0.38
ax.bar(x - w/2, paper_pri, w, label="Paper: binary (urgent / not urgent)", color=C_PAPER)
ax.bar(x + w/2, ours_pri, w, label="Ours: 4-class ordinal (Low/Med/High/Urgent)", color=C_OURS)
ax.set_ylabel("Accuracy")
ax.set_ylim(0, 1.05)
ax.set_xticks(x)
ax.set_xticklabels(models_pri)
ax.set_title("Priority accuracy: NOT directly comparable — different task shapes (see Sec. IV-C)")
line_guess = ax.axhline(0.5, color="gray", ls=":", lw=0.9, label="Binary random guess (0.50)")
line_base = ax.axhline(0.414, color=C_ACCENT, ls="--", lw=0.9, label="Our majority-class baseline (0.414)")
handles, labs = ax.get_legend_handles_labels()
ax.legend(handles=handles, labels=labs, loc="upper right", frameon=False, fontsize=6.3)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig2_priority_accuracy.pdf"), bbox_inches='tight')
plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 3: Clario retrieval quality, before vs after fix (Track A)
# Source: Track-A-Retrieval-Quality/TRACK_A_CONCLUSION.md
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6))

# Recall@4 is measured identically before and after on the 99-query set,
# so that comparison is apples-to-apples.
labels_r = ["99-query\n(before fix)", "99-query\n(after fix)", "70 real tickets\n(after fix)"]
recall_vals = [70.3, 86.4, 89.0]
colors_r = [C_PAPER, C_OURS, C_GOOD]
axes[0].bar(labels_r, recall_vals, color=colors_r)
axes[0].set_ylabel("Recall@4 (%)")
axes[0].set_ylim(0, 100)
axes[0].set_title("Recall@4")
for i, v in enumerate(recall_vals):
    axes[0].text(i, v + 1.5, f"{v:.1f}%", ha="center", fontsize=7)
axes[0].spines[["top", "right"]].set_visible(False)

# Precision changed measurement point (P@4 before -> P@1 after) -- labelled
# explicitly rather than implying a like-for-like jump.
labels_p = ["99-query\nP@4 (before)", "99-query\nP@1 (after)", "70 tickets\nP@1 (after)"]
prec_vals = [20.3, 64.4, 71.4]
axes[1].bar(labels_p, prec_vals, color=colors_r)
axes[1].set_ylabel("Precision (%)")
axes[1].set_ylim(0, 100)
axes[1].set_title("Precision (metric changes @k — see caption)")
for i, v in enumerate(prec_vals):
    axes[1].text(i, v + 1.5, f"{v:.1f}%", ha="center", fontsize=7)
axes[1].spines[["top", "right"]].set_visible(False)

fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig3_retrieval_quality.pdf"), bbox_inches='tight')
plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 4: Architecture comparison — paper's classification-only pipeline
# vs Clario's full resolution pipeline.
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.0, 4.6))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis("off")


def box(x, y, w, h, text, color, fontsize=6.3, textcolor="white"):
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.08",
                        linewidth=0.8, edgecolor="black", facecolor=color, zorder=2)
    ax.add_patch(b)
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fontsize,
             color=textcolor, zorder=3, wrap=True)


def arrow(x1, y1, x2, y2, color="black", style="-|>"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=8,
                         linewidth=0.9, color=color, zorder=1)
    ax.add_patch(a)


# --- Row 1: reference paper pipeline ---
ax.text(0.05, 9.55, "(a) Reference paper — classification-only pipeline", fontsize=8, weight="bold")
py = 8.3
boxes_a = [
    (0.1, "Raw ticket\ntext"),
    (2.0, "Preprocess\n(clean, lemmatize)"),
    (4.1, "Feature extraction\n(TF-IDF / WordPiece /\nlearned embedding)"),
    (6.6, "Trained classifier\n(1 of 10 fixed models)"),
    (8.7, "Category label\n+ priority label"),
]
w_a = [1.6, 1.85, 2.25, 1.85, 1.15]
for i, ((x, t), w) in enumerate(zip(boxes_a, w_a)):
    box(x, py, w, 1.0, t, C_PAPER)
for i in range(len(boxes_a) - 1):
    x1 = boxes_a[i][0] + w_a[i]
    x2 = boxes_a[i+1][0]
    arrow(x1, py + 0.5, x2, py + 0.5)
ax.text(0.1, py - 0.35, "Output: a label. No answer is produced; the ticket is not resolved.",
         fontsize=6.3, style="italic", color="#555555")

# --- Row 2: Clario pipeline ---
ax.text(0.05, 6.9, "(b) Clario — retrieval-augmented, judge-evaluated resolution pipeline", fontsize=8, weight="bold")

box(0.1, 5.6, 1.5, 1.0, "PII-redacted\nticket text", C_OURS)
box(1.9, 5.6, 1.7, 1.0, "Local LLM classifier\n+ confidence score", C_OURS)
arrow(1.6, 6.1, 1.9, 6.1)

box(3.9, 5.6, 1.55, 1.0, "Confidence\ngate (0.70)", C_ACCENT)
arrow(3.6, 6.1, 3.9, 6.1)

box(3.2, 3.9, 1.15, 0.9, "conf < 0.7:\nhedge to\nBOTH specialists", C_ACCENT, fontsize=5.8)
box(4.55, 3.9, 1.9, 0.9, "conf >= 0.7:\nkeyword router\n(technical/billing/hr)", C_OURS, fontsize=5.8)
arrow(4.2, 5.6, 3.85, 4.8)
arrow(4.9, 5.6, 5.4, 4.8)

box(6.85, 5.6, 1.6, 1.0, "Adaptive RAG:\nretrieve KB docs\n(skip if trivial)", C_OURS)
arrow(5.75, 4.35, 6.85, 5.8, style="-|>")
arrow(4.35, 4.35, 6.85, 5.9, style="-|>")

box(8.6, 5.6, 1.3, 1.0, "Specialist LLM\ndraft (grounded,\nfew-shot)", C_OURS, fontsize=6.0)
arrow(8.45, 6.1, 8.6, 6.1)

box(8.6, 3.9, 1.3, 1.0, "ResponseJudge\n(6-dim LLM judge:\naccuracy, groundedness,\ntone, policy, ...)", C_OURS, fontsize=5.6)
arrow(9.25, 5.6, 9.25, 4.9)

box(6.7, 3.9, 1.55, 1.0, "Human judge\ncalibration\n(Track D, in progress)", C_GOOD, fontsize=5.8)
arrow(8.6, 4.35, 8.25, 4.35)

box(8.6, 2.2, 1.3, 1.0, "Final grounded\nreply / escalation", C_GOOD, fontsize=6.0)
arrow(9.25, 3.9, 9.25, 3.2)

ax.text(0.1, 3.55,
        "Every stage can say \"I'm not sure\": low-confidence hedging, adaptive retrieval,\n"
        "and an automatic quality judge checked against human raters (Track D).",
        fontsize=6.3, style="italic", color="#555555")

fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig4_architecture.pdf"), bbox_inches='tight')
plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 5: Track D judge-score clustering finding
# Source: Track-D-Judge-Reliability/README.md
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(3.4, 2.5))
cats = ["overall_score", "priority_tone_\nmatch_score", "policy_\ncompliance_score"]
at_2 = [67, 64, 52]
total = 70
other = [total - v for v in at_2]

x = np.arange(len(cats))
ax.bar(x, at_2, color=C_ACCENT, label="Scored exactly 2/5")
ax.bar(x, other, bottom=at_2, color="#dddddd", label="All other scores")
for i, v in enumerate(at_2):
    ax.text(i, v/2, f"{v}/{total}\n({v/total*100:.0f}%)", ha="center", va="center", fontsize=6.5, color="white")
ax.set_xticks(x)
ax.set_xticklabels(cats, fontsize=6.5)
ax.set_ylabel("Drafts (of 70)")
ax.set_title("Judge scores clustering at 2/5\n(prompt/rubric mismatch, see Sec. VI-D)", fontsize=7.5)
ax.legend(loc="upper right", fontsize=6, frameon=False)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig5_judge_scores.pdf"), bbox_inches='tight')
plt.close(fig)

print("Wrote figures to", OUT)
for f in sorted(os.listdir(OUT)):
    print(" -", f)
