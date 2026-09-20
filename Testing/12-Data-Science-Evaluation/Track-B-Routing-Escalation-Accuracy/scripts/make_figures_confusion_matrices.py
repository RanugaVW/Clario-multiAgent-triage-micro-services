"""Generates the two confusion-matrix figures for Track B's viva
presentation - routing (which domain a ticket got sent to) and escalation
(did it correctly go to a human). Same visual style as
make_figures_conclusion.py (validated palette, rounded corners, hairline
gridlines, direct value labels).

Numbers are hardcoded here on purpose, transcribed straight from
../results/routing_eval_summary.json's "live_routing" and
"live_escalation" sections (the final, after-all-fixes, 70-real-ticket
run - the number that matters for the presentation).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SEQ_LOW = "#eef2fb"
SEQ_HIGH = "#2a78d6"
STATUS_GOOD = "#2e9e5b"
STATUS_BAD = "#c94f3d"

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"
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


def _cell_color(value: float, vmax: float) -> tuple:
    from matplotlib.colors import to_rgb
    lo, hi = np.array(to_rgb(SEQ_LOW)), np.array(to_rgb(SEQ_HIGH))
    t = 0 if vmax == 0 else value / vmax
    return tuple(lo + (hi - lo) * t)


# --- Figure 3: routing confusion matrix (70 real tickets, live, after fixes) ---
labels = ["technical", "billing", "both", "hr", "escalation"]
matrix = np.array([
    [17, 0, 0, 0, 6],
    [0, 16, 1, 0, 1],
    [0, 0, 1, 0, 0],
    [0, 1, 0, 13, 0],
    [0, 0, 0, 0, 0],
])
n = len(labels)
vmax = matrix.max()

fig, ax = plt.subplots(figsize=(7.8, 7))
fig.suptitle("Track B — Routing Confusion Matrix", fontsize=14, color=INK_PRIMARY, x=0.5, y=0.97)
ax.set_title("70 real tickets, live routing, after all fixes  |  rows = correct domain, columns = what Clario picked",
             fontsize=10, color=INK_MUTED, pad=14)

for i in range(n):
    for j in range(n):
        v = matrix[i, j]
        color = _cell_color(v, vmax)
        ax.add_patch(plt.Rectangle((j, n - 1 - i), 0.96, 0.96, facecolor=color,
                                    edgecolor=SURFACE, linewidth=2))
        if v > 0:
            text_color = "#ffffff" if v / vmax > 0.55 else INK_PRIMARY
            weight = "bold" if i == j else "normal"
            ax.text(j + 0.48, n - 1 - i + 0.48, str(v), ha="center", va="center",
                    fontsize=15, color=text_color, fontweight=weight)

ax.set_xlim(0, n)
ax.set_ylim(0, n)
ax.set_xticks(np.arange(n) + 0.48)
ax.set_xticklabels(labels, fontsize=10.5, color=INK_PRIMARY, rotation=20, ha="right")
ax.set_yticks(np.arange(n) + 0.48)
ax.set_yticklabels(list(reversed(labels)), fontsize=10.5, color=INK_PRIMARY)
ax.set_xlabel("Predicted (what Clario routed to)", fontsize=10.5, color=INK_SECONDARY)
ax.set_ylabel("Actual (correct domain)", fontsize=10.5, color=INK_SECONDARY)
for spine in ax.spines.values():
    spine.set_visible(False)
ax.tick_params(length=0)

fig.tight_layout(rect=(0, 0, 1, 0.88))
fig.savefig(FIG_DIR / "03_routing_confusion_matrix.png", dpi=200)
plt.close(fig)

# --- Figure 4: escalation confusion matrix (binary: should this have gone to a human) ---
tp, fn, fp, tn = 13, 6, 7, 30
esc_matrix = np.array([[tp, fn], [fp, tn]])  # rows: actual Yes/No, cols: predicted Yes/No
esc_labels = ["Yes", "No"]

fig, ax = plt.subplots(figsize=(6, 5.6))
fig.suptitle("Track B — Escalation Confusion Matrix", fontsize=14, color=INK_PRIMARY, x=0.5, y=0.97)
ax.set_title("70 real tickets, after all fixes  |  should this ticket have gone to a human?",
             fontsize=10, color=INK_MUTED, pad=14)

vmax2 = esc_matrix.max()
cell_colors = [
    [STATUS_GOOD, STATUS_BAD],   # actual Yes: predicted Yes (correct) / predicted No (missed)
    [STATUS_BAD, STATUS_GOOD],   # actual No: predicted Yes (unnecessary) / predicted No (correct)
]
for i in range(2):
    for j in range(2):
        v = esc_matrix[i, j]
        from matplotlib.colors import to_rgb
        base = np.array(to_rgb(cell_colors[i][j]))
        alpha = 0.30 + 0.55 * (v / vmax2)
        color = tuple(base * alpha + np.array(to_rgb(SURFACE)) * (1 - alpha))
        ax.add_patch(plt.Rectangle((j, 1 - i), 0.96, 0.96, facecolor=color,
                                    edgecolor=SURFACE, linewidth=3))
        ax.text(j + 0.48, 1 - i + 0.48, str(v), ha="center", va="center",
                fontsize=22, color=INK_PRIMARY, fontweight="bold")

ax.set_xlim(0, 2)
ax.set_ylim(0, 2)
ax.set_xticks([0.48, 1.48])
ax.set_xticklabels(esc_labels, fontsize=11, color=INK_PRIMARY)
ax.set_yticks([0.48, 1.48])
ax.set_yticklabels(list(reversed(esc_labels)), fontsize=11, color=INK_PRIMARY)
ax.set_xlabel("Predicted: sent to human?", fontsize=10.5, color=INK_SECONDARY)
ax.set_ylabel("Actual: should go to human?", fontsize=10.5, color=INK_SECONDARY)
for spine in ax.spines.values():
    spine.set_visible(False)
ax.tick_params(length=0)

fig.tight_layout(rect=(0, 0, 1, 0.86))
fig.savefig(FIG_DIR / "04_escalation_confusion_matrix.png", dpi=200)
plt.close(fig)

print(f"Wrote 2 figures to {FIG_DIR}")
