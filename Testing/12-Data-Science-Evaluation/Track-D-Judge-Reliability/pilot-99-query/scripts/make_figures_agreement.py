"""Generates the score-distribution figure for Track D's pilot conclusion -
shows why kappa came out low despite good raw agreement (see
../../TRACK_D_CONCLUSION.md). Same visual style as Track A/B/C's
make_figures_conclusion.py scripts.
"""

from __future__ import annotations

import csv
from collections import Counter
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
CAT = {"blue": "#2a78d6", "orange": "#eb6834", "green": "#2e9e5b"}

_HERE = Path(__file__).resolve().parent
DATA_DIR = _HERE.parent / "data"
FIG_DIR = _HERE.parent.parent / "figures"
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

with open(DATA_DIR / "judge_calibration_sample_99.csv", newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
with open(DATA_DIR / "judge_calibration_answer_key_99.csv", newline="", encoding="utf-8-sig") as f:
    key = {r["pair_id"]: r for r in csv.DictReader(f)}

h1 = Counter(int(r["human1_overall_score"]) for r in rows)
h2 = Counter(int(r["human2_overall_score"]) for r in rows)
judge = Counter(int(key[r["pair_id"]]["judge_overall_score"]) for r in rows)

scores = [1, 2, 3, 4, 5]
n = len(rows)

fig, ax = plt.subplots(figsize=(9, 6))
fig.suptitle("Track D Pilot — Why Kappa Looks Low", fontsize=14, color=INK_PRIMARY, x=0.5, y=0.97)
fig.text(0.5, 0.90, "Overall score distribution, 99 pairs — everyone clusters on 3-4, so kappa's chance-correction shrinks it",
         fontsize=9.5, color=INK_MUTED, ha="center")

x = np.arange(len(scores)) * 1.5
w = 0.4
series = [("Ranuga", h1, CAT["blue"]), ("Sineth", h2, CAT["orange"]), ("Judge", judge, CAT["green"])]
for i, (name, counts, color) in enumerate(series):
    offsets = x + (i - 1) * (w + 0.04)
    heights = [100 * counts.get(s, 0) / n for s in scores]
    for xi, h in zip(offsets, heights):
        if h <= 0:
            continue
        ax.bar(xi, h, width=w, color=color, zorder=3)
        ax.text(xi, h + 1.5, f"{h:.0f}%", ha="center", va="bottom", fontsize=9, color=INK_PRIMARY)

ax.set_xticks(x)
ax.set_xticklabels([f"Score {s}" for s in scores], fontsize=11, color=INK_PRIMARY)
ax.set_ylabel("% of 99 pairs", fontsize=10.5)
ax.set_ylim(0, 100)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.spines["bottom"].set_color(BASELINE)
ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
ax.set_axisbelow(True)
ax.tick_params(length=0)

handles = [plt.Rectangle((0, 0), 1, 1, fc=c) for _, _, c in series]
fig.legend(handles, [n for n, _, _ in series], frameon=False, loc="upper center",
           bbox_to_anchor=(0.5, 0.84), ncol=3, fontsize=10.5, labelcolor=INK_SECONDARY)

fig.tight_layout(rect=(0, 0, 1, 0.78))
fig.savefig(FIG_DIR / "05_score_distribution_pilot.png", dpi=200)
plt.close(fig)

print(f"Wrote 1 figure to {FIG_DIR}")
