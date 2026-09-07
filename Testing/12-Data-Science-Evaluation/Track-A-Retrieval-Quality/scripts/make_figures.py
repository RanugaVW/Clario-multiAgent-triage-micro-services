"""Generates the static PNG chart figures embedded in TEST_REPORT_V1.md.

Static images (not an interactive HTML/SVG chart), so the interaction layer
from the dataviz skill doesn't apply - direct value labels on every bar carry
the load a tooltip would elsewhere. Rendered for a light surface only, since
a PNG can't respond to prefers-color-scheme like the report's own theme-aware
artifacts would. Palette and mark specs (thin capped bars, hairline recessive
gridlines, text-token ink for labels) follow the dataviz skill's reference
palette; the 3-slot categorical order used here was validated with
scripts/validate_palette.js (both light and dark) before use.

These four figures are a FROZEN HISTORICAL SNAPSHOT of the original,
pre-fix baseline (see TEST_REPORT_V1.md) - the bar values are hardcoded
from that original run and are not recomputed here, because the vector
store's stale content was later deleted (TEST_REPORT_V2.md §6) and can't
be exactly reconstructed. Each figure now also carries a plain-English
"what to say in an interview" caption, added directly on the image.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

matplotlib.use("Agg")

# --- Palette (validated) ---------------------------------------------------
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

CAT = {
    "blue": "#2a78d6",
    "orange": "#eb6834",
    "aqua": "#1baf7a",
}
STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#d03b3b"
NOTE_BG = "#f0efe9"

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


def rounded_bar(ax, x, height, width, color, rounding=0.04):
    """A column with a 4px-equivalent rounded cap, square at the baseline -
    matplotlib has no native capped-rect primitive, so build it from a
    FancyBboxPatch anchored at the baseline."""
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


def value_label(ax, x, y, text, color=INK_PRIMARY):
    ax.text(x, y + 0.02 * ax.get_ylim()[1], text, ha="center", va="bottom",
             fontsize=10, color=color, fontweight="medium")


def add_interview_note(fig, text, extra_lines_above=0):
    """Draws a light divider + a short 'what to say in an interview' caption
    at the bottom of the figure, in plain English. Anchored from the BOTTOM
    of the figure upward (va='bottom'), sized from the actual line count, so
    it can never clip off the bottom edge regardless of how many lines the
    caption has. `extra_lines_above` reserves room for a footnote the caller
    places above the divider. Returns the y-fraction the caller should use as
    the bottom of its own `tight_layout(rect=(0, <this>, 1, top))`."""
    n_lines = text.count("\n") + 1
    line_h = 0.033
    bottom_margin = 0.02
    label_h = 0.036
    body_bottom = bottom_margin
    body_top = body_bottom + n_lines * line_h
    label_bottom = body_top + 0.006
    divider_y = label_bottom + label_h + 0.008
    fig.text(0.02, body_bottom, text, fontsize=8.8, color=INK_SECONDARY, ha="left", va="bottom")
    fig.text(0.02, label_bottom, "What to say in an interview:", fontsize=9, color=INK_PRIMARY,
              fontweight="medium", ha="left", va="bottom")
    fig.add_artist(plt.Line2D([0.02, 0.98], [divider_y, divider_y], color=BASELINE, linewidth=1, transform=fig.transFigure))
    return divider_y + 0.012 + extra_lines_above * 0.03


# --- Figure 1: headline metrics ---------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.8), width_ratios=[2, 1])
fig.suptitle("Track A — headline retrieval metrics (original baseline)", fontsize=13, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

pct_labels = ["Precision@3\n(n=99)", "Precision@4\n(n=99)",
              "Precision@3\n(n=59)", "Precision@4\n(n=59)",
              "Recall@3\n(n=59)", "Recall@4\n(n=59)"]
pct_values = [14.5, 12.1, 24.3, 20.3, 62.7, 70.3]
x1 = np.arange(len(pct_labels)) * 1.15
for xi, v in zip(x1, pct_values):
    rounded_bar(ax1, xi, v, 0.6, CAT["blue"])
    value_label(ax1, xi, v, f"{v:.1f}%")
ax1.set_xticks(x1)
ax1.set_xticklabels(pct_labels, fontsize=9)
ax1.set_xlim(x1[0] - 0.7, x1[-1] + 0.7)
ax1.set_ylabel("Percent")
style_axis(ax1, 100)
fig.text(0.015, 0.90, "n=99: all queries · n=59: queries with a real answer",
          fontsize=8.5, color=INK_MUTED)

score_labels = ["MRR\n(n=59)", "nDCG@4\n(n=59)"]
score_values = [0.469, 0.518]
x2 = np.arange(len(score_labels))
for xi, v in zip(x2, score_values):
    rounded_bar(ax2, xi, v, 0.5, CAT["blue"])
    value_label(ax2, xi, v, f"{v:.3f}")
ax2.set_xticks(x2)
ax2.set_xticklabels(score_labels, fontsize=9)
ax2.set_ylabel("Score (0–1)")
style_axis(ax2, 1.0)

bottom = add_interview_note(fig,
    "This was our very first test, before any fix. Recall was high (we usually found the right\n"
    "document somewhere) but Precision was low (it usually wasn't in the #1 spot). That gap is\n"
    "exactly what told us something needed fixing — see the before/after chart later in this deck.")
fig.tight_layout(rect=(0, bottom, 1, 0.87))
fig.savefig(FIG_DIR / "01_headline_metrics.png", dpi=200)
plt.close(fig)

# --- Figure 2: domain breakdown ---------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 5.4), width_ratios=[3, 2])
fig.suptitle("Track A — results by domain (original baseline)", fontsize=13, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

domains = ["technical\n(n=27)", "billing\n(n=62)", "HR→billing*\n(n=10)"]
precision4 = [3.7, 17.3, 2.5]
recall4 = [25.0, 86.9, 100.0]
x = np.arange(len(domains))
w = 0.32
for xi, v in zip(x - w / 2 - 0.02, precision4):
    rounded_bar(ax1, xi, v, w, CAT["blue"])
    value_label(ax1, xi, v, f"{v:.1f}%", color=INK_SECONDARY)
for xi, v in zip(x + w / 2 + 0.02, recall4):
    rounded_bar(ax1, xi, v, w, CAT["orange"])
    value_label(ax1, xi, v, f"{v:.1f}%", color=INK_SECONDARY)
ax1.set_xticks(x)
ax1.set_xlim(x[0] - 0.5, x[-1] + 0.5)
ax1.set_xticklabels(domains, fontsize=9)
ax1.set_ylabel("Percent")
style_axis(ax1, 110)
handles = [plt.Rectangle((0, 0), 1, 1, fc=CAT["blue"]), plt.Rectangle((0, 0), 1, 1, fc=CAT["orange"])]
ax1.legend(handles, ["Precision@4", "Recall@4"], frameon=False, loc="upper left",
           fontsize=9, labelcolor=INK_SECONDARY)

mrr = [0.130, 0.597, 0.500]
x2 = np.arange(len(domains))
for xi, v in zip(x2, mrr):
    rounded_bar(ax2, xi, v, 0.5, CAT["aqua"])
    value_label(ax2, xi, v, f"{v:.3f}", color=INK_SECONDARY)
ax2.set_xticks(x2)
ax2.set_xticklabels(domains, fontsize=9)
ax2.set_ylabel("MRR (0–1)")
style_axis(ax2, 1.1)

bottom = add_interview_note(fig,
    "Billing did far better than technical in this first test — the problem wasn't spread evenly\n"
    "across the system. That's why we checked what was actually inside the knowledge base next.",
    extra_lines_above=1)
fig.text(0.02, bottom - 0.028, "* n=1 with a real answer — not a stable estimate.", fontsize=8,
          color=INK_MUTED, va="bottom")
fig.tight_layout(rect=(0, bottom, 1, 0.93))
fig.savefig(FIG_DIR / "02_domain_breakdown.png", dpi=200)
plt.close(fig)

# --- Figure 3: relevance gate outcomes --------------------------------------
fig, ax = plt.subplots(figsize=(6, 5.6))
fig.suptitle("Track A — relevance-gate outcomes (n=99, original baseline)", fontsize=12.5, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

outcomes = ["TP\n(gate passed,\ntop-1 correct)", "FP\n(gate passed,\ntop-1 wrong)",
            "FN\n(gate failed,\ntop-1 correct)", "TN\n(gate failed,\ntop-1 wrong)"]
counts = [16, 83, 0, 0]
colors = [STATUS_GOOD, STATUS_CRITICAL, STATUS_GOOD, STATUS_CRITICAL]
xo = np.arange(len(outcomes))
for xi, v, c in zip(xo, counts, colors):
    rounded_bar(ax, xi, v, 0.55, c)
    value_label(ax, xi, v, str(v))
ax.set_xticks(xo)
ax.set_xticklabels(outcomes, fontsize=8.5)
ax.set_ylabel("Queries")
style_axis(ax, 95)
handles = [plt.Rectangle((0, 0), 1, 1, fc=STATUS_GOOD), plt.Rectangle((0, 0), 1, 1, fc=STATUS_CRITICAL)]
ax.legend(handles, ["Correct gate decision", "Incorrect gate decision"], frameon=False,
          loc="upper right", fontsize=9, labelcolor=INK_SECONDARY)

bottom = add_interview_note(fig,
    "The gate is a yes/no self-check the system runs on its own top answer before trusting it.\n"
    "Here it said 'yes, trust this' 99 times out of 99 — including on wrong answers. It never once\n"
    "said no. That's the single clearest problem this whole evaluation found.")
fig.tight_layout(rect=(0, bottom, 1, 0.90))
fig.savefig(FIG_DIR / "03_relevance_gate.png", dpi=200)
plt.close(fig)

# --- Figure 4: vector store composition -------------------------------------
fig, ax = plt.subplots(figsize=(6, 5.6))
fig.suptitle("kb_support_docs composition at evaluation time (71 chunks)", fontsize=12, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

comp_labels = ["Current KB docs\n(technical + billing)", "precedent_memory\n(excluded by filter)",
               "Other indexed\nchunks*"]
comp_values = [20, 21, 30]
xc = np.arange(len(comp_labels))
for xi, v in zip(xc, comp_values):
    rounded_bar(ax, xi, v, 0.5, CAT["blue"])
    pct = v / 71 * 100
    value_label(ax, xi, v, f"{v} ({pct:.0f}%)")
ax.set_xticks(xc)
ax.set_xticklabels(comp_labels, fontsize=9)
ax.set_ylabel("Chunks")
style_axis(ax, 36)

bottom = add_interview_note(fig,
    "This is an inventory, not a score: it shows what the system could actually search through.\n"
    "40% of it was old, leftover content — that's very likely why Figures 1 and 2 looked so weak.\n"
    "We removed all of this afterward (see the before/after results).",
    extra_lines_above=1)
fig.text(0.02, bottom - 0.028, "* Not present in the current repo's KB source directories or git history.",
          fontsize=8, color=INK_MUTED, va="bottom")
fig.tight_layout(rect=(0, bottom, 1, 0.90))
fig.savefig(FIG_DIR / "04_vector_store_composition.png", dpi=200)
plt.close(fig)

print("Wrote 4 figures to", FIG_DIR)
