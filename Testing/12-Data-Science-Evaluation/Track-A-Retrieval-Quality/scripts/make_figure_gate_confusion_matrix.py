"""Track A figures 16-17 — relevance-gate confusion matrix, before and after
the fix (see TRACK_A_FINAL_CONCLUSION_REPORT.md, Sections 2 and 3, wherever
the gate's TP/FP/FN/TN numbers are discussed). The existing gate figures (03,
08) are bar charts of the same four numbers - readable, but not the real 2x2
confusion-matrix picture Track B uses for its own binary decision
(escalation). This is that same picture, for Track A's binary decision:
"should the gate trust this top result?"

Rows = actual (was the system's top-1 result really correct), columns =
predicted (did the gate approve it). Same visual convention as Track B's
escalation matrix: diagonal = correct decision (green), off-diagonal =
error (red).

Figure 16 (before) uses the pre-fix baseline counts quoted in the report
text (TP=16/FP=83 for 99-query, TP=16/FP=54 for 70-ticket - the threshold
was so loose it never rejected anything, so FN=TN=0 in both). Figure 17
(after) reads the post-fix gate_confusion_matrix live from
results/v1_summary_metrics.json (99-query, final state) and
results/v3_summary_metrics.json (70-ticket, final corrected state) - the
same two files every other final-round number in the report comes from.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgb

matplotlib.use("Agg")

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
BASELINE = "#c3c2b7"
STATUS_GOOD = "#2e9e5b"
STATUS_BAD = "#c94f3d"

_HERE = Path(__file__).resolve().parent
RESULTS_DIR = _HERE.parent / "results"
FIG_DIR = _HERE.parent / "figures"
FIG_DIR.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "text.color": INK_PRIMARY,
    "axes.edgecolor": BASELINE,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})

labels = ["Approved", "Rejected"]

# --- before: pre-fix baseline, hardcoded (quoted directly in the report text) ---
before_datasets = [
    ("99-query baseline", 16, 0, 83, 0),
    ("70-ticket baseline", 16, 0, 54, 0),
]

# --- after: post-fix, read live from the same JSON files every other final-round number uses ---
v1 = json.loads((RESULTS_DIR / "v1_summary_metrics.json").read_text())  # 99-query, final state
v3 = json.loads((RESULTS_DIR / "v3_summary_metrics.json").read_text())  # 70-ticket, final corrected state
after_datasets = [
    ("99-query, after fixes", v1["gate_confusion_matrix"]["tp"], v1["gate_confusion_matrix"]["fn"],
     v1["gate_confusion_matrix"]["fp"], v1["gate_confusion_matrix"]["tn"]),
    ("70-ticket, after fixes", v3["gate_confusion_matrix"]["tp"], v3["gate_confusion_matrix"]["fn"],
     v3["gate_confusion_matrix"]["fp"], v3["gate_confusion_matrix"]["tn"]),
]


def draw_gate_matrix(ax, tp, fn, fp, tn, title):
    matrix = np.array([[tp, fn], [fp, tn]])  # rows: actual Yes/No, cols: predicted Approved/Rejected
    vmax = matrix.max() if matrix.max() > 0 else 1
    cell_colors = [
        [STATUS_GOOD, STATUS_BAD],   # actual correct: approved (right) / rejected (missed a real hit)
        [STATUS_BAD, STATUS_GOOD],   # actual wrong: approved (false pass) / rejected (correctly caught)
    ]
    for i in range(2):
        for j in range(2):
            v = matrix[i, j]
            base = np.array(to_rgb(cell_colors[i][j]))
            alpha = 0.18 if v == 0 else 0.30 + 0.55 * (v / vmax)
            color = tuple(base * alpha + np.array(to_rgb(SURFACE)) * (1 - alpha))
            ax.add_patch(plt.Rectangle((j, 1 - i), 0.96, 0.96, facecolor=color,
                                        edgecolor=SURFACE, linewidth=3))
            ax.text(j + 0.48, 1 - i + 0.48, str(v), ha="center", va="center",
                    fontsize=22, color=INK_PRIMARY, fontweight="bold")
    ax.set_xlim(0, 2)
    ax.set_ylim(0, 2)
    ax.set_xticks([0.48, 1.48])
    ax.set_xticklabels(labels, fontsize=11, color=INK_PRIMARY)
    ax.set_yticks([0.48, 1.48])
    ax.set_yticklabels(["Wrong", "Correct"], fontsize=11, color=INK_PRIMARY)
    ax.set_xlabel("Predicted: gate's decision", fontsize=10.5, color=INK_SECONDARY)
    ax.set_title(title, fontsize=11.5, color=INK_PRIMARY, pad=12)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)


def make_figure(datasets, subtitle, footnote, filename):
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.8))
    fig.suptitle("Track A — Relevance-Gate Confusion Matrix", fontsize=14, color=INK_PRIMARY, x=0.5, y=0.98)
    fig.text(0.5, 0.905, subtitle, fontsize=9.5, color=INK_MUTED, ha="center")

    for ax, (name, tp, fn, fp, tn) in zip(axes, datasets):
        draw_gate_matrix(ax, tp, fn, fp, tn, name)
    axes[0].set_ylabel("Actual: was the top-1 result correct?", fontsize=10.5, color=INK_SECONDARY)

    fig.text(0.5, 0.03, footnote, fontsize=9, color=INK_MUTED, ha="center", style="italic")

    fig.tight_layout(rect=(0, 0.06, 1, 0.86))
    fig.savefig(FIG_DIR / filename, dpi=200)
    plt.close(fig)
    print(f"Wrote figures/{filename}")


make_figure(
    before_datasets,
    "Before any fix — actual: was the top-1 result really correct? predicted: did the gate approve it?",
    "The entire \"Rejected\" column is empty — the gate approved every single result, right or wrong, "
    "and never once said no.",
    "16_gate_confusion_matrix.png",
)

make_figure(
    after_datasets,
    "After the threshold fix — actual: was the top-1 result really correct? predicted: did the gate approve it?",
    "The \"Rejected\" column is finally in use on both datasets — the gate now actually turns some matches away.",
    "17_gate_confusion_matrix_after.png",
)
