"""Track E figures for TRACK_E_FINAL_CONCLUSION_REPORT.md. Same house style
as Tracks A-D's make_figures_conclusion.py scripts (validated palette,
rounded bars, hairline gridlines, direct value labels). Reads live from
results/funnel_rates_summary.json, results/reflection_value_summary.json,
and data/failure_taxonomy.csv - nothing here is hand-typed twice.
"""

from __future__ import annotations

import csv
import json
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
CAT = {"blue": "#2a78d6", "orange": "#eb6834", "green": "#2e9e5b", "grey": "#b6b4ac", "red": "#c94f3d"}

_HERE = Path(__file__).resolve().parent
DATA_DIR = _HERE.parent / "data"
RESULTS_DIR = _HERE.parent / "results"
FIG_DIR = _HERE.parent / "figures"
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


def style_axis(ax, ymax):
    ax.set_ylim(0, ymax)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)


def rounded_bar(ax, x, height, width, color, rounding=0.05, zorder=3):
    if height <= 0:
        return
    box = FancyBboxPatch((x - width / 2, 0), width, height,
                          boxstyle=f"round,pad=0,rounding_size={rounding}",
                          linewidth=0, facecolor=color, mutation_aspect=1, zorder=zorder)
    ax.add_patch(box)


# --- Figure 1: funnel rates with Wilson 95% CI --------------------------
funnel = json.loads((RESULTS_DIR / "funnel_rates_summary_v2.json").read_text())["funnel_rates"]
labels = ["Cache-hit\nrate", "Reflection-loop\nrate", "Misroute-retry\nrate", "Escalation\nrate"]
keys = ["cache_hit_rate", "reflection_loop_rate", "misroute_retry_rate", "escalation_rate"]

fig, ax = plt.subplots(figsize=(9, 6.2))
fig.suptitle("Track E — Pipeline Funnel Rates, with 95% Wilson Intervals", fontsize=13.5, color=INK_PRIMARY, x=0.5, y=0.97)
fig.text(0.5, 0.905, "70 real tickets, one live run through the full pipeline each",
         fontsize=9.5, color=INK_MUTED, ha="center")

x = np.arange(len(labels)) * 1.3
w = 0.55
for xi, key in zip(x, keys):
    stats = funnel[key]
    pct = stats["point"] * 100
    lo, hi = stats["ci_low"] * 100, stats["ci_high"] * 100
    rounded_bar(ax, xi, pct, w, CAT["blue"])
    ax.errorbar(xi, pct, yerr=[[pct - lo], [hi - pct]], fmt="none",
                ecolor=INK_PRIMARY, elinewidth=1.6, capsize=6, capthick=1.6, zorder=4)
    ax.text(xi, hi + 2.5, f"{pct:.1f}%\n[{lo:.1f}, {hi:.1f}]", ha="center", va="bottom",
            fontsize=9, color=INK_PRIMARY, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=10.5, color=INK_PRIMARY)
ax.set_ylabel("Rate (%)", fontsize=10.5)
style_axis(ax, 100)

fig.tight_layout(rect=(0, 0, 1, 0.85))
fig.savefig(FIG_DIR / "01_funnel_rates.png", dpi=200)
plt.close(fig)

# --- Figure 2: failure taxonomy ------------------------------------------
with open(DATA_DIR / "failure_taxonomy.csv", newline="", encoding="utf-8-sig") as f:
    tax_rows = list(csv.DictReader(f))
bucket_counts = Counter(r["bucket"] for r in tax_rows)
buckets = ["wrong_retrieval", "fabricated_content", "prompt_gap", "genuinely_hard_case"]
bucket_labels = ["Wrong\nretrieval", "Fabricated\ncontent", "Prompt\ngap", "Genuinely\nhard case"]
bucket_colors = [CAT["blue"], CAT["red"], CAT["orange"], CAT["grey"]]

fig, ax = plt.subplots(figsize=(9, 6))
fig.suptitle("Track E — Failure Taxonomy, Tracks A–D Combined", fontsize=13.5, color=INK_PRIMARY, x=0.5, y=0.97)
fig.text(0.5, 0.905, f"{len(tax_rows)} real, documented failure patterns sorted into 4 buckets",
         fontsize=9.5, color=INK_MUTED, ha="center")

xs = np.arange(len(buckets)) * 1.3
heights = [bucket_counts.get(b, 0) for b in buckets]
for xi, h, c in zip(xs, heights, bucket_colors):
    rounded_bar(ax, xi, h, 0.6, c)
    if h > 0:
        ax.text(xi, h + 0.12, str(h), ha="center", va="bottom", fontsize=13, color=INK_PRIMARY, fontweight="bold")
ax.set_xticks(xs)
ax.set_xticklabels(bucket_labels, fontsize=10.5, color=INK_PRIMARY)
ax.set_ylabel("Number of documented failure patterns", fontsize=10.5)
style_axis(ax, max(heights) * 1.35)

fig.tight_layout(rect=(0, 0, 1, 0.85))
fig.savefig(FIG_DIR / "02_failure_taxonomy.png", dpi=200)
plt.close(fig)

# --- Figure 3: reflection value - two fixes, applied one at a time -------
refl_v2 = json.loads((RESULTS_DIR / "reflection_value_summary_v2.json").read_text())
refl_v3 = json.loads((RESULTS_DIR / "reflection_value_summary_v3.json").read_text())
refl_v5 = json.loads((RESULTS_DIR / "reflection_value_summary_v5.json").read_text())

fig, axes = plt.subplots(1, 3, figsize=(18.5, 6.6))
fig.suptitle("Track E — Two Fixes, Applied and Verified One at a Time", fontsize=13.5, color=INK_PRIMARY, x=0.5, y=0.98)
fig.text(0.5, 0.915, "Same judge, same paired before/after comparison, run again after each fix - not once at the end",
         fontsize=9.5, color=INK_MUTED, ha="center")


def _slope_panel(ax, refl, title, n_note):
    pairs = refl["per_ticket"]
    for p in pairs:
        delta = p["final"] - p["pre"]
        color = CAT["green"] if delta > 0 else (CAT["red"] if delta < 0 else CAT["grey"])
        alpha = 0.85 if delta != 0 else 0.45
        jitter = (hash(p["query_id"]) % 21 - 10) / 400
        ax.plot([0, 1], [p["pre"] + jitter, p["final"] + jitter], color=color, alpha=alpha, linewidth=1.6,
                zorder=3, marker="o", markersize=4)
    improved, unchanged, worsened = refl["tickets_improved"], refl["tickets_unchanged"], refl["tickets_worsened"]
    handles = [plt.Line2D([0], [0], color=CAT["green"], linewidth=2), plt.Line2D([0], [0], color=CAT["red"], linewidth=2),
               plt.Line2D([0], [0], color=CAT["grey"], linewidth=2)]
    ax.legend(handles, [f"Improved ({improved})", f"Got worse ({worsened})", f"Unchanged ({unchanged})"],
              frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, fontsize=9, labelcolor=INK_SECONDARY)
    ax.set_xlim(-0.15, 1.15)
    ax.set_ylim(0.5, 5.5)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Before reflection", "After reflection"], fontsize=10, color=INK_PRIMARY)
    ax.set_title(f"{title}\n({n_note})", fontsize=11, color=INK_PRIMARY, pad=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["bottom"].set_color(BASELINE)
    ax.grid(True, axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


_slope_panel(axes[0], refl_v2, "1. Before any fix",
             f"n={refl_v2['n_reflected_with_paired_scores']}, always kept the rewrite")
_slope_panel(axes[1], refl_v3, "2. Fallback fix",
             f"n={refl_v3['n_reflected_with_paired_scores']}, keeps whichever draft scores higher")
_slope_panel(axes[2], refl_v5, "3. + critique fix (full 70)",
             f"n={refl_v5['n_reflected_with_paired_scores']}, redraft now told which check failed")
axes[0].set_ylabel("Judge overall score (1-5)", fontsize=10.5, color=INK_SECONDARY)

fig.text(0.5, 0.03, "Panel 2: zero tickets end up worse than their original draft - guaranteed by the fallback's "
                     "construction. Panel 3: the same fallback at full sample size; one red line is judge-rescoring "
                     "noise on an identical draft, not the guarantee failing (see report).",
         fontsize=8.5, color=INK_MUTED, ha="center", style="italic")

fig.tight_layout(rect=(0, 0.06, 1, 0.86))
fig.savefig(FIG_DIR / "03_reflection_value.png", dpi=200)
plt.close(fig)

print("Wrote 3 figures to", FIG_DIR)
