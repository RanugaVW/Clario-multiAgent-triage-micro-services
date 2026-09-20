"""Track A figure 15 — rank-cutoff curves (see TRACK_A_FINAL_CONCLUSION_REPORT.md
Section 4). Every other Track A figure is a bar chart at one fixed k. This is a
genuinely different diagnostic: it plots Precision@k and Recall@k as k itself
grows from 1 to 4, so it shows *how fast* the system's confidence decays as it's
asked for more results, not just a single snapshot. A steep drop after k=1 means
the top pick carries almost all the signal; a flat line means the right document
is spread across several ranks about equally.

Values are read directly from results/v1_summary_metrics.json (99-query set,
final KB/index state) and results/v3_summary_metrics.json (70-ticket set, final
corrected state) - the exact same two files the existing conclusion doc's
headline numbers (71.4/64.4, 89.0/86.4) come from. Precision uses the
"with_relevant_only" fields so both curves are computed over queries that
actually have a correct answer to find, matching how the headline numbers
are reported.
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
DATA_DIR = _HERE.parent / "results"
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

v1 = json.loads((DATA_DIR / "v1_summary_metrics.json").read_text())  # 99-query, final state
v3 = json.loads((DATA_DIR / "v3_summary_metrics.json").read_text())  # 70-ticket, final state

ks = [1, 2, 3, 4]
series = {
    "70 real tickets": {
        "precision": [v3[f"precision_at_{k}_with_relevant_only"] * 100 for k in ks],
        "recall": [v3[f"recall_at_{k}"] * 100 for k in ks],
        "color": CAT["blue"],
    },
    "99-query baseline": {
        "precision": [v1[f"precision_at_{k}_with_relevant_only"] * 100 for k in ks],
        "recall": [v1[f"recall_at_{k}"] * 100 for k in ks],
        "color": CAT["grey"],
    },
}


def style_axis(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["bottom"].set_color(BASELINE)
    ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)
    ax.set_ylim(0, 100)
    ax.set_xticks(ks)
    ax.set_xlabel("k (how many results considered)", fontsize=10, color=INK_SECONDARY)


fig, axes = plt.subplots(1, 2, figsize=(12, 5.8))
fig.suptitle("Track A — Precision@k and Recall@k as k Grows", fontsize=13.5, color=INK_PRIMARY, x=0.5, y=0.98)
fig.text(0.5, 0.90, "Same final system and knowledge base, both real datasets, k = 1 to 4",
         fontsize=9.5, color=INK_MUTED, ha="center")

for ax, metric, title in [(axes[0], "precision", "Precision@k"), (axes[1], "recall", "Recall@k")]:
    names = list(series.keys())
    for name in names:
        s = series[name]
        ax.plot(ks, s[metric], marker="o", markersize=6, linewidth=2.4, color=s["color"], label=name)
    # offset labels above/below whenever the two series land within 4pp of each other at this k,
    # so close values (e.g. 86.9% vs 86.4%) don't render as overlapping, unreadable text
    for k_idx, k in enumerate(ks):
        vals = [(name, series[name][metric][k_idx]) for name in names]
        close = abs(vals[0][1] - vals[1][1]) < 4
        for i, (name, v) in enumerate(vals):
            if close:
                dy = 10 if i == 0 else -14
                va = "bottom" if i == 0 else "top"
            else:
                dy, va = 8, "bottom"
            ax.annotate(f"{v:.0f}%", (k, v), textcoords="offset points", xytext=(0, dy),
                        ha="center", va=va, fontsize=8.5, color=INK_PRIMARY)
    ax.set_title(title, fontsize=11.5, color=INK_PRIMARY, pad=10)
    style_axis(ax)
    if ax is axes[0]:
        ax.set_ylabel("Score (%)", fontsize=10.5)

handles = [plt.Line2D([0], [0], color=CAT["blue"], linewidth=2.4, marker="o"),
           plt.Line2D([0], [0], color=CAT["grey"], linewidth=2.4, marker="o")]
fig.legend(handles, ["70 real tickets", "99-query baseline"], frameon=False, loc="upper center",
           bbox_to_anchor=(0.5, 0.85), ncol=2, fontsize=10, labelcolor=INK_SECONDARY)

fig.tight_layout(rect=(0, 0, 1, 0.82))
fig.savefig(FIG_DIR / "15_rank_cutoff_curves.png", dpi=200)
plt.close(fig)

print("Wrote figures/15_rank_cutoff_curves.png")
