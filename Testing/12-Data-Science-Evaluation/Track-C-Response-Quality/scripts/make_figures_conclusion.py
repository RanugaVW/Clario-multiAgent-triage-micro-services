"""Generates Track C's viva presentation figures. Same visual style as
Track A/B's make_figures_conclusion.py (validated palette, rounded-cap
bars, hairline gridlines, direct value labels).

Numbers are hardcoded here on purpose, transcribed straight from the real
evaluation runs this session:
  - "before" = 99-query pilot, before the priority/sentiment-aware
    drafting fix (see ../pilot-99-query/TRACK_C_PILOT_99_REPORT.md).
  - "after" = 70 real tickets, after the fix (see ../TRACK_C_70_TICKET_REPORT.md).
  - Pairwise and semantic similarity only exist for the "after" round -
    the 99-query pilot has no real human reply to compare against.
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
CAT = {"blue": "#2a78d6", "orange": "#eb6834", "green": "#2e9e5b", "grey": "#b6b4ac"}

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

DOMAINS = ["billing", "hr", "technical"]


def rounded_bar(ax, x, height, width, color, rounding=0.05):
    if height <= 0:
        return
    box = FancyBboxPatch((x - width / 2, 0), width, height,
                          boxstyle=f"round,pad=0,rounding_size={rounding}",
                          linewidth=0, facecolor=color, mutation_aspect=1)
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


def value_label(ax, x, y, text, color=INK_PRIMARY, ymax=None, fontsize=10.5):
    scale = ymax if ymax is not None else ax.get_ylim()[1]
    ax.text(x, y + 0.02 * scale, text, ha="center", va="bottom",
             fontsize=fontsize, color=color, fontweight="bold")


def grouped_bars(ax, before, after, ymax, fmt="{:.2f}"):
    x = np.arange(len(DOMAINS)) * 1.3
    w = 0.42
    for xi, v in zip(x - w / 2 - 0.02, before):
        rounded_bar(ax, xi, v, w, CAT["grey"])
        value_label(ax, xi, v, fmt.format(v), ymax=ymax)
    for xi, v in zip(x + w / 2 + 0.02, after):
        rounded_bar(ax, xi, v, w, CAT["blue"])
        value_label(ax, xi, v, fmt.format(v), ymax=ymax)
    ax.set_xticks(x)
    ax.set_xticklabels(DOMAINS, fontsize=11, color=INK_PRIMARY)
    ax.set_xlim(x[0] - 0.85, x[-1] + 0.85)
    style_axis(ax, ymax)
    return x


# --- Figure 1: overall judge score + tone match, before/after ------------
overall_before = [2.82, 3.67, 2.81]
overall_after = [4.50, 4.92, 3.95]
tone_before = [2.22, 3.06, 2.24]
tone_after = [4.75, 4.85, 3.75]

fig, axes = plt.subplots(1, 2, figsize=(12, 5.6))
fig.suptitle("Track C — Judge Score, Before vs After the Fix", fontsize=14, color=INK_PRIMARY, x=0.5, y=0.98)
fig.text(0.5, 0.90, "99-query pilot (before) vs 70 real tickets (after)  |  scale: 1-5",
         fontsize=10, color=INK_MUTED, ha="center")

grouped_bars(axes[0], overall_before, overall_after, 5.6)
axes[0].set_title("Overall score", fontsize=11.5, color=INK_PRIMARY, pad=10)
axes[0].set_ylabel("Score (1-5)", fontsize=10.5)

grouped_bars(axes[1], tone_before, tone_after, 5.6)
axes[1].set_title("Tone match", fontsize=11.5, color=INK_PRIMARY, pad=10)

handles = [plt.Rectangle((0, 0), 1, 1, fc=CAT["grey"]), plt.Rectangle((0, 0), 1, 1, fc=CAT["blue"])]
fig.legend(handles, ["Before (pilot)", "After (fix applied)"], frameon=False,
           loc="upper center", bbox_to_anchor=(0.5, 0.86), ncol=2, fontsize=10.5, labelcolor=INK_SECONDARY)

fig.tight_layout(rect=(0, 0, 1, 0.82))
fig.savefig(FIG_DIR / "01_judge_score_before_after.png", dpi=200)
plt.close(fig)

# --- Figure 2: groundedness before/after ----------------------------------
ground_before = [77.0, 86.4, 59.2]
ground_after = [80.0, 83.3, 80.0]

fig, ax = plt.subplots(figsize=(8, 5.8))
fig.suptitle("Track C — Groundedness, Before vs After", fontsize=14, color=INK_PRIMARY, x=0.5, y=0.98)
fig.text(0.5, 0.90, "% of customer-facing sentences backed by retrieved KB content",
         fontsize=10, color=INK_MUTED, ha="center")
grouped_bars(ax, ground_before, ground_after, 110, fmt="{:.1f}%")
ax.set_ylabel("Percent supported", fontsize=10.5)
ax.set_yticks([0, 20, 40, 60, 80, 100])
handles = [plt.Rectangle((0, 0), 1, 1, fc=CAT["grey"]), plt.Rectangle((0, 0), 1, 1, fc=CAT["blue"])]
fig.legend(handles, ["Before (pilot)", "After (fix applied)"], frameon=False,
           loc="upper center", bbox_to_anchor=(0.5, 0.86), ncol=2, fontsize=10.5, labelcolor=INK_SECONDARY)

fig.tight_layout(rect=(0, 0, 1, 0.80))
fig.savefig(FIG_DIR / "02_groundedness_before_after.png", dpi=200)
plt.close(fig)

# --- Figure 3: pairwise win/tie/loss (stacked, %) + semantic similarity --
pairwise_counts = {"billing": (20, 2, 2), "hr": (11, 1, 1), "technical": (11, 4, 3)}
similarity = {"billing": 0.633, "hr": 0.666, "technical": 0.588}

fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.8))
fig.suptitle("Track C — Head-to-Head vs Real Human Reply (70 Real Tickets)", fontsize=14, color=INK_PRIMARY, x=0.5, y=0.98)

ax = axes[0]
x = np.arange(len(DOMAINS))
bottoms = np.zeros(len(DOMAINS))
seg_colors = [CAT["blue"], CAT["grey"], CAT["orange"]]
seg_names = ["Human reply wins", "Tie", "Clario wins"]
for seg_idx in range(3):
    vals = []
    for d in DOMAINS:
        ref, tie, draft = pairwise_counts[d]
        total = ref + tie + draft
        pct = [ref, tie, draft][seg_idx] / total * 100
        vals.append(pct)
    ax.bar(x, vals, bottom=bottoms, width=0.55, color=seg_colors[seg_idx],
           label=seg_names[seg_idx], zorder=3)
    for xi, v, b in zip(x, vals, bottoms):
        if v >= 6:
            ax.text(xi, b + v / 2, f"{v:.0f}%", ha="center", va="center",
                     fontsize=10, color="#ffffff", fontweight="bold")
    bottoms += np.array(vals)
ax.set_xticks(x)
ax.set_xticklabels(DOMAINS, fontsize=11, color=INK_PRIMARY)
ax.set_ylim(0, 100)
ax.set_ylabel("% of comparisons", fontsize=10.5)
ax.set_title("Judge's pick: Clario's draft vs the real reply", fontsize=11.5, color=INK_PRIMARY, pad=10)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.tick_params(length=0)
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3,
          fontsize=9.5, labelcolor=INK_SECONDARY)

ax = axes[1]
vals = [similarity[d] for d in DOMAINS]
xg = np.arange(len(DOMAINS))
for xi, v in zip(xg, vals):
    rounded_bar(ax, xi, v, 0.5, CAT["green"])
    value_label(ax, xi, v, f"{v:.2f}", ymax=1.0)
ax.set_xticks(xg)
ax.set_xticklabels(DOMAINS, fontsize=11, color=INK_PRIMARY)
ax.set_ylabel("Mean cosine similarity", fontsize=10.5)
ax.set_title("Wording closeness to the real reply", fontsize=11.5, color=INK_PRIMARY, pad=10)
style_axis(ax, 1.0)

fig.tight_layout(rect=(0, 0, 1, 0.90))
fig.savefig(FIG_DIR / "03_pairwise_and_similarity.png", dpi=200)
plt.close(fig)

print(f"Wrote 3 figures to {FIG_DIR}")
