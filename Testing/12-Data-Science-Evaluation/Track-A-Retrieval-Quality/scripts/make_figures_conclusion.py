"""Generates the two clean, presentation-ready charts for Track A's
conclusion (see TRACK_A_CONCLUSION.md): one for the very first evaluation
(99-query baseline, before any fix) and one for the final evaluation
(after all fixes, both datasets). Same visual style as make_figures_lms.py
(validated palette, rounded-cap bars, hairline gridlines, direct value
labels) but deliberately carries NO explanatory caption on the image
itself — the image is chart-only; the explanation lives in
TRACK_A_CONCLUSION.md next to it. Only the two metrics judged most
presentation-worthy are shown (Precision and Recall), not the full metric
set already covered in TEST_REPORT_V1.md / TEST_REPORT_V2.md.

Numbers are hardcoded here on purpose: the baseline numbers are frozen
history (TEST_REPORT_V1.md §2.1, before any KB fix — the underlying index
has since been permanently changed, so they cannot be regenerated), and
the final numbers are transcribed from TEST_REPORT_V2.md §6.5/§6.6 (which
are themselves generated live from results/v2_summary_metrics.json and
results/v1_summary_metrics.json) so this script has no import-time
dependency on the sidecar app.

Figure 14's "70 real tickets" bars were updated once, after TEST_REPORT_V2.md's
Correction section: the original annotator CSVs behind the 70-ticket ground
truth were the wrong version, and re-running against the corrected ground
truth (results/v3_summary_metrics.json) changed Precision@1 and Recall@4.
The 99-query baseline bars are untouched - that is a separate dataset the
correction does not affect.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

matplotlib.use("Agg")

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
CAT = {"blue": "#2a78d6", "orange": "#eb6834"}

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"
FIG_DIR.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "text.color": INK_PRIMARY,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK_SECONDARY,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})


def rounded_bar(ax, x, height, width, color, rounding=0.05):
    if height <= 0:
        return
    box = FancyBboxPatch(
        (x - width / 2, 0), width, height,
        boxstyle=f"round,pad=0,rounding_size={rounding}",
        linewidth=0, facecolor=color, mutation_aspect=1,
    )
    ax.add_patch(box)


def style_axis(ax, ymax):
    ax.set_ylim(0, ymax)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)


def value_label(ax, x, y, text, color=INK_PRIMARY, ymax=None, fontsize=13):
    scale = ymax if ymax is not None else ax.get_ylim()[1]
    ax.text(x, y + 0.02 * scale, text, ha="center", va="bottom",
             fontsize=fontsize, color=color, fontweight="bold")


# --- Figure 13: first evaluation (99-query baseline, before any fix) ----
fig, ax = plt.subplots(figsize=(6.4, 5.6))
fig.suptitle("Track A — First Evaluation (99-Query Baseline)", fontsize=14,
             color=INK_PRIMARY, x=0.5, y=0.96, ha="center")
ax.set_title("Before any fix", fontsize=10.5, color=INK_MUTED, pad=14)

labels = ["Precision@4", "Recall@4"]
values = [20.3, 70.3]
x = np.arange(len(labels))
for xi, v in zip(x, values):
    rounded_bar(ax, xi, v, 0.5, CAT["blue"])
    value_label(ax, xi, v, f"{v:.1f}%", ymax=100)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=13, color=INK_PRIMARY)
ax.set_ylabel("Percent", fontsize=11)
style_axis(ax, 100)

fig.tight_layout(rect=(0, 0, 1, 0.88))
fig.savefig(FIG_DIR / "13_conclusion_baseline.png", dpi=200)
plt.close(fig)

# --- Figure 14: final evaluation, after all fixes, both datasets --------
fig, ax = plt.subplots(figsize=(8, 5.8))
fig.suptitle("Track A — Final Evaluation (After All Fixes)", fontsize=14,
             color=INK_PRIMARY, x=0.5, y=0.96, ha="center")
ax.set_title("Precision@1 and Recall@4, both real datasets", fontsize=10.5, color=INK_MUTED, pad=14)

metrics = ["Precision@1", "Recall@4"]
real_tickets = [71.4, 89.0]
q99_baseline = [64.4, 86.4]
x = np.arange(len(metrics)) * 1.3
w = 0.42

for xi, v in zip(x - w / 2 - 0.02, real_tickets):
    rounded_bar(ax, xi, v, w, CAT["blue"])
    value_label(ax, xi, v, f"{v:.1f}%", ymax=110)
for xi, v in zip(x + w / 2 + 0.02, q99_baseline):
    rounded_bar(ax, xi, v, w, CAT["orange"])
    value_label(ax, xi, v, f"{v:.1f}%", ymax=110)

ax.set_xticks(x)
ax.set_xticklabels(metrics, fontsize=13, color=INK_PRIMARY)
ax.set_xlim(x[0] - 0.85, x[-1] + 0.85)
ax.set_ylabel("Percent", fontsize=11)
style_axis(ax, 110)
ax.set_yticks([0, 20, 40, 60, 80, 100])

handles = [plt.Rectangle((0, 0), 1, 1, fc=CAT["blue"]), plt.Rectangle((0, 0), 1, 1, fc=CAT["orange"])]
ax.legend(handles, ["70 real tickets", "99-query baseline"], frameon=False,
          loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=2,
          fontsize=10.5, labelcolor=INK_SECONDARY)

fig.tight_layout(rect=(0, 0, 1, 0.88))
fig.savefig(FIG_DIR / "14_conclusion_final.png", dpi=200)
plt.close(fig)

print(f"Wrote 2 figures to {FIG_DIR}")
