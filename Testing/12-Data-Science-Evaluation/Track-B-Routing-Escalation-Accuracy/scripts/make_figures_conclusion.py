"""Generates the two clean, presentation-ready charts for Track B's
conclusion (see ../TRACK_B_CONCLUSION.md). Same visual style as Track A's
make_figures_conclusion.py (validated palette, rounded-cap bars, hairline
gridlines, direct value labels) - chart-only, no explanatory caption on
the image itself.

Numbers are hardcoded here on purpose, transcribed straight from the real
evaluation runs (frozen history - the "before" run reflects code that has
since been fixed and can't be regenerated as-is):
  - "before" (99-query, pre-fix): results/../pilot-99-query/results/
    routing_eval_summary_99.json, captured before any Track B code fix
    (saved as /tmp/baseline_summary_99.json during that session).
  - "after" (99-query, all fixes applied): pilot-99-query/results/
    routing_eval_summary_99.json, current.
  - "after" (70 real tickets, all fixes applied): results/
    routing_eval_summary.json, current.

Only the live run's numbers are shown (the real, end-to-end result) -
the routing-logic-only run is a diagnostic tool covered in the report
text, not a headline presentation number.
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
CAT = {"blue": "#2a78d6", "orange": "#eb6834", "green": "#2e9e5b"}

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


# --- Figure 1: 99-query pilot, before any Track B fix --------------------
fig, ax = plt.subplots(figsize=(7, 5.8))
fig.suptitle("Track B — Before Enhancements (99-Query Pilot)", fontsize=14,
             color=INK_PRIMARY, x=0.5, y=0.96, ha="center")
ax.set_title("Live routing + escalation, before any fix", fontsize=10.5, color=INK_MUTED, pad=14)

labels = ["Routing\naccuracy", "HR ticket\nrecall", "Escalation\nF1 score"]
values = [63.4, 36.8, 51.9]
x = np.arange(len(labels))
for xi, v in zip(x, values):
    rounded_bar(ax, xi, v, 0.5, CAT["blue"])
    value_label(ax, xi, v, f"{v:.1f}%", ymax=100)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=12, color=INK_PRIMARY)
ax.set_ylabel("Percent", fontsize=11)
style_axis(ax, 100)

fig.tight_layout(rect=(0, 0, 1, 0.88))
fig.savefig(FIG_DIR / "01_conclusion_before.png", dpi=200)
plt.close(fig)

# --- Figure 2: after all fixes, both datasets -----------------------------
fig, ax = plt.subplots(figsize=(9, 6))
fig.suptitle("Track B — After Enhancements", fontsize=14,
             color=INK_PRIMARY, x=0.5, y=0.96, ha="center")
ax.set_title("Live routing + escalation, both datasets, after all fixes", fontsize=10.5, color=INK_MUTED, pad=14)

metrics = ["Routing\naccuracy", "HR ticket\nrecall", "Escalation\nF1 score"]
q99_after = [76.1, 78.9, 74.1]
real70_after = [83.9, 92.9, 66.7]
x = np.arange(len(metrics)) * 1.3
w = 0.42

for xi, v in zip(x - w / 2 - 0.02, q99_after):
    rounded_bar(ax, xi, v, w, CAT["orange"])
    value_label(ax, xi, v, f"{v:.1f}%", ymax=110)
for xi, v in zip(x + w / 2 + 0.02, real70_after):
    rounded_bar(ax, xi, v, w, CAT["blue"])
    value_label(ax, xi, v, f"{v:.1f}%", ymax=110)

ax.set_xticks(x)
ax.set_xticklabels(metrics, fontsize=12, color=INK_PRIMARY)
ax.set_xlim(x[0] - 0.85, x[-1] + 0.85)
ax.set_ylabel("Percent", fontsize=11)
style_axis(ax, 110)
ax.set_yticks([0, 20, 40, 60, 80, 100])

handles = [plt.Rectangle((0, 0), 1, 1, fc=CAT["orange"]), plt.Rectangle((0, 0), 1, 1, fc=CAT["blue"])]
ax.legend(handles, ["99-query pilot", "70 real tickets"], frameon=False,
          loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=2,
          fontsize=10.5, labelcolor=INK_SECONDARY)

fig.tight_layout(rect=(0, 0, 1, 0.88))
fig.savefig(FIG_DIR / "02_conclusion_after.png", dpi=200)
plt.close(fig)

print(f"Wrote 2 figures to {FIG_DIR}")
