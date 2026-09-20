"""Track B figure 05 — per-class precision/recall scatter (see
TRACK_B_FINAL_CONCLUSION_REPORT.md Section 4). The two confusion matrices show
raw counts; this shows the same underlying per-class numbers a different way -
precision and recall plotted against each other, one point per routing class,
sized by how many real tickets actually belong to that class (support). A point
in the top-right corner is a class the router gets right with no real
trade-off; a point pulled away from that corner shows exactly which trade-off
is happening (missing real cases vs. false alarms), and a tiny point (like
"both", support=1) is a reminder not to over-read a class with almost no data
behind it.

Reads live from results/routing_eval_summary.json - the same file the
existing conclusion doc's headline numbers come from - so this never drifts
out of sync with a re-run.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
CAT = {"blue": "#2a78d6", "orange": "#eb6834", "green": "#2e9e5b", "grey": "#b6b4ac"}

_HERE = Path(__file__).resolve().parent
RESULTS = _HERE.parent / "results" / "routing_eval_summary.json"
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

data = json.loads(RESULTS.read_text())
per_class = data["live_routing"]["per_class"]

colors = {"technical": CAT["blue"], "billing": CAT["orange"], "hr": CAT["green"], "both": CAT["grey"]}
# hand-placed, not auto-avoided: only 4 points, and technical/hr/billing cluster
# tightly near (75-93% recall, 94-100% precision), so each label is aimed at the
# nearest open space rather than a generic fixed offset that would collide
label_layout = {
    "technical": {"dx": -90, "dy": 18, "ha": "right"},
    "hr": {"dx": 0, "dy": 20, "ha": "center"},
    "billing": {"dx": 16, "dy": -38, "ha": "left"},
    "both": {"dx": -14, "dy": 0, "ha": "right"},
}

fig, ax = plt.subplots(figsize=(7.5, 6.8))
fig.suptitle("Track B — Precision vs. Recall by Routing Class", fontsize=13.5, color=INK_PRIMARY, x=0.5, y=0.97)
fig.text(0.5, 0.905, "70 real tickets, live routing (classifier + rules), point size = support (tickets in that class)",
         fontsize=9.5, color=INK_MUTED, ha="center")

for cls, color in colors.items():
    m = per_class[cls]
    if m["support"] == 0:
        continue
    size = 160 + m["support"] * 32
    ax.scatter(m["recall"] * 100, m["precision"] * 100, s=size, color=color, alpha=0.75,
               edgecolor="white", linewidth=1.5, zorder=3)
    layout = label_layout[cls]
    ax.annotate(f"{cls}\n(n={m['support']}, F1={m['f1']:.2f})", (m["recall"] * 100, m["precision"] * 100),
                textcoords="offset points", xytext=(layout["dx"], layout["dy"]),
                ha=layout["ha"], fontsize=9.5, color=INK_PRIMARY, fontweight="bold")

ax.set_xlim(30, 105)
ax.set_ylim(30, 105)
ax.set_xlabel("Recall (%) — of the real cases, how many did it catch?", fontsize=10.5, color=INK_SECONDARY)
ax.set_ylabel("Precision (%) — when it picked this class, how often was it right?", fontsize=10.5, color=INK_SECONDARY)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_color(BASELINE)
ax.spines["bottom"].set_color(BASELINE)
ax.grid(True, color=GRID, linewidth=1, zorder=0)
ax.set_axisbelow(True)
ax.tick_params(axis="both", length=0)
ax.axhline(100, color=BASELINE, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
ax.axvline(100, color=BASELINE, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
ax.text(100, 32, "perfect recall", fontsize=8, color=INK_MUTED, ha="right", va="bottom", rotation=90)
ax.text(32, 100, "perfect precision", fontsize=8, color=INK_MUTED, ha="left", va="top")

fig.tight_layout(rect=(0, 0, 1, 0.87))
fig.savefig(FIG_DIR / "05_per_class_precision_recall.png", dpi=200)
plt.close(fig)

print("Wrote figures/05_per_class_precision_recall.png")
