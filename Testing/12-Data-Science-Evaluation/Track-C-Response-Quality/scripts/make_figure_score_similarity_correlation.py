"""Track C figure 04 — judge score vs. semantic similarity, per ticket (see
TRACK_C_FINAL_CONCLUSION_REPORT.md Section 4). The pairwise chart (figure 03)
already shows humans still prefer the real reply 76% of the time even though
judge scores look strong. This figure asks the natural follow-up question at
the individual-ticket level: for THIS specific ticket, does a higher judge
score actually go with wording that's closer to what the human wrote, or are
the two measuring different things? A tight upward trend means they agree;
a flat or scattered cloud means a high judge score doesn't reliably predict
wording similarity to a human reply - i.e. the judge and "closeness to a
human" are genuinely different signals, not two views of the same one.

Reads live from results/clario_full_graph_drafts.csv (judge_overall_score)
joined to results/semantic_similarity.csv (minilm_cosine_as_sent) on query_id -
the same two files the rest of Track C's numbers come from.
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
RESULTS = _HERE.parent / "results"
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

with open(RESULTS / "clario_full_graph_drafts.csv", newline="", encoding="utf-8-sig") as f:
    drafts = {r["query_id"]: r for r in csv.DictReader(f)}
with open(RESULTS / "semantic_similarity.csv", newline="", encoding="utf-8-sig") as f:
    sims = {r["query_id"]: r for r in csv.DictReader(f)}

domain_colors = {"billing": CAT["orange"], "technical": CAT["blue"], "hr": CAT["green"]}
points = []
for qid in sorted(set(drafts) & set(sims)):
    d, s = drafts[qid], sims[qid]
    try:
        score = float(d["judge_overall_score"])
        sim = float(s["minilm_cosine_as_sent"])
    except (ValueError, KeyError):
        continue
    points.append((sim, score, d.get("domain_drafted", "billing")))

xs = np.array([p[0] for p in points])
ys = np.array([p[1] for p in points])
r = np.corrcoef(xs, ys)[0, 1]
slope, intercept = np.polyfit(xs, ys, 1)

fig, ax = plt.subplots(figsize=(8.5, 6.8))
fig.suptitle("Track C — Does a Higher Judge Score Mean Closer Wording to a Human Reply?",
             fontsize=13, color=INK_PRIMARY, x=0.5, y=0.97)
fig.text(0.5, 0.905, f"70 real tickets ({len(points)} with both scores), one dot per ticket — Pearson r = {r:.2f}",
         fontsize=9.5, color=INK_MUTED, ha="center")

for domain, color in domain_colors.items():
    dx = [p[0] for p in points if p[2] == domain]
    dy = [p[1] for p in points if p[2] == domain]
    if dx:
        ax.scatter(dx, dy, s=70, color=color, alpha=0.75, edgecolor="white", linewidth=0.8,
                   label=domain, zorder=3)

xline = np.linspace(xs.min() - 0.02, xs.max() + 0.02, 50)
ax.plot(xline, slope * xline + intercept, color=INK_MUTED, linewidth=1.8, linestyle=(0, (5, 3)), zorder=2)

ax.set_xlabel("Semantic similarity to the real human reply (MiniLM cosine)", fontsize=10.5, color=INK_SECONDARY)
ax.set_ylabel("Judge overall score (1-5)", fontsize=10.5, color=INK_SECONDARY)
ax.set_ylim(0.5, 5.5)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_color(BASELINE)
ax.spines["bottom"].set_color(BASELINE)
ax.grid(True, color=GRID, linewidth=1, zorder=0)
ax.set_axisbelow(True)
ax.tick_params(axis="both", length=0)

fig.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 0.86), ncol=3,
           fontsize=10, labelcolor=INK_SECONDARY)

fig.tight_layout(rect=(0, 0, 1, 0.83))
fig.savefig(FIG_DIR / "04_score_similarity_correlation.png", dpi=200)
plt.close(fig)

print(f"Wrote figures/04_score_similarity_correlation.png (n={len(points)}, r={r:.3f})")
