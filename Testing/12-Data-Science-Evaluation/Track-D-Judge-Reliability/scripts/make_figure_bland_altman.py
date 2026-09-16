"""Track D figure 09 — Bland-Altman agreement plots (see ../TRACK_D_CONCLUSION.md,
Final Conclusion Report §4). A Bland-Altman plot is the standard statistical tool
for checking whether two raters/methods agree: each point is one ticket, x = the
mean of the two scores being compared, y = their difference. A cloud centered on
zero with a narrow spread means good agreement; a cloud offset from zero means a
systematic bias; a cloud that fans out at one end means the raters disagree more
on some score ranges than others. This is a genuinely different diagnostic from
the plain diff-histogram in figure 07 - it also shows whether the *size* of the
score matters to the disagreement, which a histogram of differences alone cannot.

Panel 1: Ranuga vs Sineth, overall_score (headline "is this a good reply" score).
Panel 2: Judge vs (Ranuga + Sineth) mean, overall_score.
"""

from __future__ import annotations

import csv
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

with open(DATA_DIR / "judge_calibration_sample.csv", newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
with open(DATA_DIR / "judge_calibration_answer_key.csv", newline="", encoding="utf-8-sig") as f:
    key = {r["pair_id"]: r for r in csv.DictReader(f)}

rng = np.random.default_rng(7)  # fixed seed - jitter is visual only, reproducible


def style_axis(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["bottom"].set_color(BASELINE)
    ax.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)


def bland_altman(ax, means, diffs, color, title):
    means = np.array(means, dtype=float)
    diffs = np.array(diffs, dtype=float)
    # small fixed jitter so overlapping integer/half-integer points are visible -
    # the underlying scores are discrete (1-5 or 0.5 steps), the jitter is not real data
    jx = means + rng.uniform(-0.08, 0.08, size=len(means))
    jy = diffs + rng.uniform(-0.08, 0.08, size=len(diffs))
    ax.scatter(jx, jy, s=36, color=color, alpha=0.55, edgecolor="none", zorder=3)

    bias = diffs.mean()
    sd = diffs.std(ddof=1)
    loa_hi, loa_lo = bias + 1.96 * sd, bias - 1.96 * sd

    ax.axhline(0, color=BASELINE, linewidth=1, zorder=1)
    ax.axhline(bias, color=INK_PRIMARY, linewidth=1.6, zorder=2)
    ax.axhline(loa_hi, color=INK_MUTED, linewidth=1.2, linestyle=(0, (4, 3)), zorder=2)
    ax.axhline(loa_lo, color=INK_MUTED, linewidth=1.2, linestyle=(0, (4, 3)), zorder=2)

    xmax = ax.get_xlim()[1] if ax.get_xlim()[1] else means.max()
    ax.text(means.max() + 0.05, bias, f"bias {bias:+.2f}", fontsize=9, color=INK_PRIMARY,
            va="bottom", ha="left", fontweight="bold")
    ax.text(means.max() + 0.05, loa_hi, f"+1.96 SD ({loa_hi:+.2f})", fontsize=8, color=INK_MUTED, va="bottom", ha="left")
    ax.text(means.max() + 0.05, loa_lo, f"-1.96 SD ({loa_lo:+.2f})", fontsize=8, color=INK_MUTED, va="top", ha="left")

    ax.set_title(title, fontsize=11.5, color=INK_PRIMARY, pad=10)
    ax.set_xlabel("Mean of the two scores", fontsize=10, color=INK_SECONDARY)
    style_axis(ax)
    return bias, sd


fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.8))
fig.suptitle("Track D — Bland-Altman Agreement Plots (overall_score, 82 pairs)", fontsize=13.5, color=INK_PRIMARY, x=0.5, y=0.98)
fig.text(0.5, 0.90, "Each dot is one ticket: x = average of the two scores compared, y = their difference. "
                     "A cloud centered on zero with a narrow band means strong agreement.",
         fontsize=9.5, color=INK_MUTED, ha="center")

# Panel 1: human1 vs human2
h1 = [int(r["human1_overall_score"]) for r in rows]
h2 = [int(r["human2_overall_score"]) for r in rows]
means1 = [(a + b) / 2 for a, b in zip(h1, h2)]
diffs1 = [a - b for a, b in zip(h1, h2)]
bland_altman(axes[0], means1, diffs1, CAT["orange"], "Ranuga vs Sineth")
axes[0].set_ylabel("Difference (Ranuga − Sineth)", fontsize=10.5)

# Panel 2: judge vs human mean
j, hmean = [], []
for r in rows:
    k = key.get(r["pair_id"])
    if not k or not k.get("judge_overall_score"):
        continue
    h1v = int(r["human1_overall_score"])
    h2v = int(r["human2_overall_score"])
    hm = (h1v + h2v) / 2
    hmean.append(hm)
    j.append(int(k["judge_overall_score"]))
means2 = [(a + b) / 2 for a, b in zip(j, hmean)]
diffs2 = [a - b for a, b in zip(j, hmean)]
bland_altman(axes[1], means2, diffs2, CAT["green"], "Judge vs Human mean")
axes[1].set_ylabel("Difference (Judge − Human mean)", fontsize=10.5)

fig.tight_layout(rect=(0, 0, 0.93, 0.86))
fig.savefig(FIG_DIR / "09_bland_altman.png", dpi=200)
plt.close(fig)

print("Wrote figures/09_bland_altman.png")
