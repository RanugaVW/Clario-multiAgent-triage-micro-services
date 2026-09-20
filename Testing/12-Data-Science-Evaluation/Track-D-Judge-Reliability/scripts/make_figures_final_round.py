"""Generates the two figures for Track D's final-round results (see
../TRACK_D_CONCLUSION.md): did the rubric-anchor fix actually help
(judge-vs-human, pilot vs final), and the systematic rater-offset finding
on the final round itself. Same visual style as the other tracks'
make_figures_conclusion.py scripts.
"""

from __future__ import annotations

import csv
from collections import Counter
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

_HERE = Path(__file__).resolve().parent
DATA_DIR = _HERE.parent / "data"
FIG_DIR = _HERE.parent / "figures"
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


def value_label(ax, x, y, text, ymax, fontsize=11):
    ax.text(x, y + 0.02 * ymax, text, ha="center", va="bottom",
             fontsize=fontsize, color=INK_PRIMARY, fontweight="bold")


# --- Figure 6: did the rubric-anchor fix help? pilot vs final ------------
metrics = ["Mean weighted\nkappa", "Mean Spearman\ncorrelation"]
pilot_vals = [0.075, 0.249]
final_vals = [0.339, 0.764]

fig, ax = plt.subplots(figsize=(8, 5.8))
fig.suptitle("Track D — Did the Rubric-Anchor Fix Help?", fontsize=14, color=INK_PRIMARY, x=0.5, y=0.97)
fig.text(0.5, 0.90, "Automatic judge vs combined human score, old rubric (pilot) vs new rubric (final round)",
         fontsize=9.5, color=INK_MUTED, ha="center")

x = np.arange(len(metrics)) * 1.3
w = 0.42
for xi, v in zip(x - w / 2 - 0.02, pilot_vals):
    rounded_bar(ax, xi, v, w, CAT["grey"])
    value_label(ax, xi, v, f"{v:.2f}", 1.0)
for xi, v in zip(x + w / 2 + 0.02, final_vals):
    rounded_bar(ax, xi, v, w, CAT["blue"])
    value_label(ax, xi, v, f"{v:.2f}", 1.0)
ax.set_xticks(x)
ax.set_xticklabels(metrics, fontsize=11, color=INK_PRIMARY)
ax.set_xlim(x[0] - 0.85, x[-1] + 0.85)
ax.set_ylabel("Score (0-1)", fontsize=10.5)
style_axis(ax, 1.0)
handles = [plt.Rectangle((0, 0), 1, 1, fc=CAT["grey"]), plt.Rectangle((0, 0), 1, 1, fc=CAT["blue"])]
fig.legend(handles, ["Pilot (old rubric)", "Final round (new rubric)"], frameon=False,
           loc="upper center", bbox_to_anchor=(0.5, 0.85), ncol=2, fontsize=10, labelcolor=INK_SECONDARY)

fig.tight_layout(rect=(0, 0, 1, 0.80))
fig.savefig(FIG_DIR / "06_rubric_fix_before_after.png", dpi=200)
plt.close(fig)

# --- Figure 7: systematic rater offset (final round) ----------------------
with open(DATA_DIR / "judge_calibration_sample.csv", newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

fig, axes = plt.subplots(1, 2, figsize=(12, 5.8))
fig.suptitle("Track D — A Systematic Rater Offset, Not Random Disagreement", fontsize=13.5, color=INK_PRIMARY, x=0.5, y=0.98)
fig.text(0.5, 0.90, "Ranuga's score minus Sineth's score, 82 pairs, final round",
         fontsize=9.5, color=INK_MUTED, ha="center")

for ax, dim, title, color in [
    (axes[0], "priority_tone_match_score", "Tone match\n(Sineth more lenient)", CAT["orange"]),
    (axes[1], "accuracy_score", "Accuracy\n(Ranuga more lenient)", CAT["green"]),
]:
    h1 = [int(r[f"human1_{dim}"]) for r in rows]
    h2 = [int(r[f"human2_{dim}"]) for r in rows]
    diffs = [a - b for a, b in zip(h1, h2)]
    counts = Counter(diffs)
    xs = list(range(-3, 4))
    heights = [counts.get(x, 0) for x in xs]
    for xi, h in zip(xs, heights):
        c = CAT["grey"] if xi == 0 else color
        rounded_bar(ax, xi, h, 0.7, c)
        if h > 0:
            value_label(ax, xi, h, str(h), max(heights) * 1.15, fontsize=10)
    ax.set_xticks(xs)
    ax.set_xticklabels([str(x) for x in xs], fontsize=10, color=INK_PRIMARY)
    ax.set_xlabel("Ranuga − Sineth", fontsize=10, color=INK_SECONDARY)
    ax.set_title(title, fontsize=11, color=INK_PRIMARY, pad=10)
    style_axis(ax, max(heights) * 1.3)
    if ax is axes[0]:
        ax.set_ylabel("Number of pairs", fontsize=10.5)

fig.tight_layout(rect=(0, 0, 1, 0.82))
fig.savefig(FIG_DIR / "07_systematic_rater_offset.png", dpi=200)
plt.close(fig)

# --- Figure 8: the judge won't use the low end on accuracy/groundedness --
with open(DATA_DIR / "judge_calibration_answer_key.csv", newline="", encoding="utf-8-sig") as f:
    key = {r["pair_id"]: r for r in csv.DictReader(f)}

fig, axes = plt.subplots(1, 2, figsize=(12, 5.8))
fig.suptitle("Track D — The Judge Rarely Uses the Low End of the Scale", fontsize=13.5, color=INK_PRIMARY, x=0.5, y=0.98)
fig.text(0.5, 0.90, "Now that human scores are properly calibrated, this gap is visible for the first time",
         fontsize=9.5, color=INK_MUTED, ha="center")

for ax, dim, title in [
    (axes[0], "accuracy_score", "Accuracy"),
    (axes[1], "groundedness_score", "Groundedness"),
]:
    h_means_rounded = []
    j_scores = []
    for r in rows:
        h1 = int(r[f"human1_{dim}"])
        h2 = int(r[f"human2_{dim}"])
        h_means_rounded.append(round((h1 + h2) / 2))
        j_scores.append(int(key[r["pair_id"]][f"judge_{dim}"]))
    h_counts = Counter(h_means_rounded)
    j_counts = Counter(j_scores)
    scores = [1, 2, 3, 4, 5]
    n = len(rows)
    x = np.arange(len(scores)) * 1.4
    w = 0.5
    all_heights = []
    for i, (name, counts, color) in enumerate([("Humans (avg)", h_counts, CAT["blue"]), ("Judge", j_counts, CAT["green"])]):
        offsets = x + (i - 0.5) * (w + 0.05)
        heights = [100 * counts.get(s, 0) / n for s in scores]
        all_heights.extend(heights)
        for xi, h in zip(offsets, heights):
            if h <= 0:
                continue
            ax.bar(xi, h, width=w, color=color, zorder=3)
            ax.text(xi, h + 1.5, f"{h:.0f}%", ha="center", va="bottom", fontsize=8.5, color=INK_PRIMARY)
    ax.set_xticks(x)
    ax.set_xticklabels([str(s) for s in scores], fontsize=10, color=INK_PRIMARY)
    ax.set_title(title, fontsize=11.5, color=INK_PRIMARY, pad=10)
    style_axis(ax, max(all_heights) * 1.2)
    if ax is axes[0]:
        ax.set_ylabel("% of 82 pairs", fontsize=10.5)

handles = [plt.Rectangle((0, 0), 1, 1, fc=CAT["blue"]), plt.Rectangle((0, 0), 1, 1, fc=CAT["green"])]
fig.legend(handles, ["Humans (average)", "Judge"], frameon=False, loc="upper center",
           bbox_to_anchor=(0.5, 0.84), ncol=2, fontsize=10, labelcolor=INK_SECONDARY)

fig.tight_layout(rect=(0, 0, 1, 0.78))
fig.savefig(FIG_DIR / "08_judge_wont_score_low.png", dpi=200)
plt.close(fig)

print(f"Wrote 3 figures to {FIG_DIR}")
