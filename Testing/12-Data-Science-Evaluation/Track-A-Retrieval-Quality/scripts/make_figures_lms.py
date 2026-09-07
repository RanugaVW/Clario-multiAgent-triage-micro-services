"""Generates the static PNG chart figures for the Track A / LMS-ticket
report (TEST_REPORT_V2.md). Same conventions as make_figures.py: validated
palette, rounded-cap bar marks, hairline recessive gridlines, direct value
labels (this is a set of static images, not an interactive artifact, so
labels carry the load a tooltip would elsewhere).

Figures 5-8 are frozen historical snapshots (values hardcoded from the
pre-fix run, same reasoning as make_figures.py). Figures 9-10 reflect the
state right after the cleanup+threshold fix. Figures 11-12 are new: the
CURRENT, final numbers (after cleanup + threshold + the KB wording pass),
read live from results/v2_summary_metrics.json and results/v1_summary_metrics.json,
including Precision@2/@3/@4 and F1 - see TEST_REPORT_V2.md §6.5.

Every figure carries a plain-English "what to say in an interview" caption,
added directly on the image.
"""

from __future__ import annotations

import json
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

CAT = {"blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a"}
STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#d03b3b"

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"
FIG_DIR.mkdir(exist_ok=True)
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

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


def value_label(ax, x, y, text, color=INK_PRIMARY, extra_offset=0.0, ymax=None):
    """`ymax` should be the same value passed to style_axis() for this axis.
    Reading ax.get_ylim()[1] here is unreliable: FancyBboxPatch doesn't
    trigger autoscale on add, so at call time (before style_axis runs) the
    axis is often still at its default (0, 1) range, silently shrinking
    this offset to nothing - pass ymax explicitly instead."""
    scale = ymax if ymax is not None else ax.get_ylim()[1]
    ax.text(x, y + (0.02 + extra_offset) * scale, text, ha="center", va="bottom",
             fontsize=10, color=color, fontweight="medium")


def close_pair_offsets(v1, v2, ymax, threshold_frac=0.04):
    """When two adjacent grouped-bar values are close enough that their
    labels would sit at nearly the same height (and collide horizontally,
    since the bars are adjacent), stagger them vertically instead. Returns
    (offset1, offset2) as extra fractions of ymax."""
    if abs(v1 - v2) < threshold_frac * ymax:
        return (0.05, 0.0) if v1 >= v2 else (0.0, 0.05)
    return (0.0, 0.0)


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


# --- Figure 5: two-person agreement ------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.6), width_ratios=[1, 1.4])
fig.suptitle("Track A — two-person manual classification of 70 real tickets", fontsize=13, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

labels = ["Agreed\nbefore discussion", "Disagreed\n(resolved after review)"]
vals = [67, 3]
colors = [STATUS_GOOD, STATUS_CRITICAL]
x = np.arange(len(labels))
for xi, v, c in zip(x, vals, colors):
    rounded_bar(ax1, xi, v, 0.5, c)
    value_label(ax1, xi, v, f"{v} ({v/70*100:.1f}%)")
ax1.set_xticks(x)
ax1.set_xticklabels(labels, fontsize=9)
ax1.set_ylabel("Tickets (of 70)")
style_axis(ax1, 92)

dom_labels = ["billing", "technical", "hr", "escalate\n(no doc)"]
ranuga = [32, 27, 11, 0]
sineth = [30, 26, 12, 2]
xd = np.arange(len(dom_labels))
w = 0.32
for xi, v in zip(xd - w / 2 - 0.02, ranuga):
    rounded_bar(ax2, xi, v, w, CAT["blue"])
    value_label(ax2, xi, v, str(v), color=INK_SECONDARY)
for xi, v in zip(xd + w / 2 + 0.02, sineth):
    rounded_bar(ax2, xi, v, w, CAT["orange"])
    value_label(ax2, xi, v, str(v), color=INK_SECONDARY)
ax2.set_xticks(xd)
ax2.set_xlim(xd[0] - 0.5, xd[-1] + 0.5)
ax2.set_xticklabels(dom_labels, fontsize=9)
ax2.set_ylabel("Tickets labelled")
style_axis(ax2, 44)
handles = [plt.Rectangle((0, 0), 1, 1, fc=CAT["blue"]), plt.Rectangle((0, 0), 1, 1, fc=CAT["orange"])]
ax2.legend(handles, ["Annotator 1 (Ranuga)", "Annotator 2 (Sineth)"], frameon=False, loc="upper right",
           fontsize=9, labelcolor=INK_SECONDARY)

bottom = add_interview_note(fig,
    "Two of us labelled all 70 real tickets by hand, separately, without comparing notes first.\n"
    "We agreed on 95.7% of them before any discussion — that's why we trust this ground truth.")
fig.tight_layout(rect=(0, bottom, 1, 0.90))
fig.savefig(FIG_DIR / "05_lms_annotator_agreement.png", dpi=200)
plt.close(fig)

# --- Figure 6: headline retrieval metrics (pre-fix snapshot) ------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.8), width_ratios=[2, 1])
fig.suptitle("Track A — headline retrieval metrics, before any fix (70 real tickets)", fontsize=12.5, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

pct_labels = ["Precision@3\n(n=70)", "Precision@4\n(n=70)",
              "Precision@3\n(n=68)", "Precision@4\n(n=68)",
              "Recall@3\n(n=68)", "Recall@4\n(n=68)"]
pct_values = [19.0, 16.8, 19.6, 17.3, 58.8, 63.2]
x1 = np.arange(len(pct_labels)) * 1.15
for xi, v in zip(x1, pct_values):
    rounded_bar(ax1, xi, v, 0.6, CAT["blue"])
    value_label(ax1, xi, v, f"{v:.1f}%")
ax1.set_xticks(x1)
ax1.set_xticklabels(pct_labels, fontsize=9)
ax1.set_xlim(x1[0] - 0.7, x1[-1] + 0.7)
ax1.set_ylabel("Percent")
style_axis(ax1, 100)
fig.text(0.015, 0.90, "n=70: all tickets  ·  n=68: tickets with a real answer",
          fontsize=8.5, color=INK_MUTED)

score_labels = ["MRR\n(n=68)", "nDCG@4\n(n=68)"]
score_values = [0.406, 0.463]
x2 = np.arange(len(score_labels))
for xi, v in zip(x2, score_values):
    rounded_bar(ax2, xi, v, 0.5, CAT["blue"])
    value_label(ax2, xi, v, f"{v:.3f}")
ax2.set_xticks(x2)
ax2.set_xticklabels(score_labels, fontsize=9)
ax2.set_ylabel("Score (0–1)")
style_axis(ax2, 1.0)

bottom = add_interview_note(fig,
    "This is the real-ticket test, before any fix — same pattern as our very first test:\n"
    "the right answer is usually in there somewhere, but rarely in the #1 spot. See Figure 11\n"
    "for where these numbers ended up after we fixed the two root causes we found.")
fig.tight_layout(rect=(0, bottom, 1, 0.87))
fig.savefig(FIG_DIR / "06_lms_headline_metrics.png", dpi=200)
plt.close(fig)

# --- Figure 7: results by domain (pre-fix snapshot) ---------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 5.4), width_ratios=[3, 2])
fig.suptitle("Track A — results by domain, before any fix (70 real tickets)", fontsize=12.5, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

domains = ["technical\n(n=27)", "billing\n(n=31)", "hr\n(n=12)"]
precision4 = [7.4, 18.5, 33.3]
recall4 = [30.8, 76.7, 100.0]
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
style_axis(ax1, 112)
handles = [plt.Rectangle((0, 0), 1, 1, fc=CAT["blue"]), plt.Rectangle((0, 0), 1, 1, fc=CAT["orange"])]
ax1.legend(handles, ["Precision@4", "Recall@4"], frameon=False, loc="upper left",
           fontsize=9, labelcolor=INK_SECONDARY)

mrr = [0.167, 0.425, 0.875]
x2 = np.arange(len(domains))
for xi, v in zip(x2, mrr):
    rounded_bar(ax2, xi, v, 0.5, CAT["aqua"])
    value_label(ax2, xi, v, f"{v:.3f}", color=INK_SECONDARY)
ax2.set_xticks(x2)
ax2.set_xticklabels(domains, fontsize=9)
ax2.set_ylabel("MRR (0–1)")
style_axis(ax2, 1.05)

bottom = add_interview_note(fig,
    "Our brand-new HR knowledge base — small and still clean — performed perfectly here.\n"
    "Technical was the weakest, matching what our very first test already found.")
fig.tight_layout(rect=(0, bottom, 1, 0.90))
fig.savefig(FIG_DIR / "07_lms_domain_breakdown.png", dpi=200)
plt.close(fig)

# --- Figure 8: relevance gate outcomes (pre-fix snapshot) ----------------
fig, ax = plt.subplots(figsize=(6, 5.6))
fig.suptitle("Track A — relevance-gate outcomes, before any fix (70 real tickets)", fontsize=12, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

outcomes = ["TP\n(gate passed,\ntop-1 correct)", "FP\n(gate passed,\ntop-1 wrong)",
            "FN\n(gate failed,\ntop-1 correct)", "TN\n(gate failed,\ntop-1 wrong)"]
counts = [16, 54, 0, 0]
colors = [STATUS_GOOD, STATUS_CRITICAL, STATUS_GOOD, STATUS_CRITICAL]
xo = np.arange(len(outcomes))
for xi, v, c in zip(xo, counts, colors):
    rounded_bar(ax, xi, v, 0.55, c)
    value_label(ax, xi, v, str(v))
ax.set_xticks(xo)
ax.set_xticklabels(outcomes, fontsize=8.5)
ax.set_ylabel("Tickets")
style_axis(ax, 62)
handles = [plt.Rectangle((0, 0), 1, 1, fc=STATUS_GOOD), plt.Rectangle((0, 0), 1, 1, fc=STATUS_CRITICAL)]
ax.legend(handles, ["Correct gate decision", "Incorrect gate decision"], frameon=False,
          loc="upper right", fontsize=9, labelcolor=INK_SECONDARY)

bottom = add_interview_note(fig,
    "Same self-check as before, now on real tickets: it still never once said 'no,' even on\n"
    "tickets where the honest answer was 'there's no document for this.' Confirmed the problem\n"
    "was real, not a fluke of our first test.")
fig.tight_layout(rect=(0, bottom, 1, 0.90))
fig.savefig(FIG_DIR / "08_lms_relevance_gate.png", dpi=200)
plt.close(fig)

# --- Figure 9: vector store composition (after stale-content cleanup) ---
fig, ax = plt.subplots(figsize=(6, 5.6))
fig.suptitle("kb_support_docs composition, after removing stale content (45 chunks)", fontsize=12, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

comp_labels = ["Current KB docs\n(technical + billing + hr)", "precedent_memory\n(excluded by filter)",
               "Other indexed\nchunks*"]
comp_values = [23, 22, 0]
xc = np.arange(len(comp_labels))
for xi, v in zip(xc, comp_values):
    rounded_bar(ax, xi, v, 0.5, CAT["blue"] if v else BASELINE)
    pct = v / 45 * 100
    value_label(ax, xi, v, f"{v} ({pct:.0f}%)")
ax.set_xticks(xc)
ax.set_xlim(xc[0] - 0.5, xc[-1] + 0.5)
ax.set_xticklabels(comp_labels, fontsize=9)
ax.set_ylabel("Chunks")
style_axis(ax, 27)

bottom = add_interview_note(fig,
    "This is the same inventory as before, after we deleted the old content — it's now 0%.\n"
    "The knowledge base is fully current.",
    extra_lines_above=1)
fig.text(0.02, bottom - 0.028, "* Was 30 chunks (40%) before cleanup - see TEST_REPORT_V1.md, Figure 4.",
          fontsize=8, color=INK_MUTED, va="bottom")
fig.tight_layout(rect=(0, bottom, 1, 0.90))
fig.savefig(FIG_DIR / "09_lms_vector_store_composition.png", dpi=200)
plt.close(fig)

# --- Figure 10: before/after fix, on both independent datasets ----------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 6.0))
fig.suptitle("Effect of removing stale content + raising the relevance-gate threshold", fontsize=12.5, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

groups = ["70 real\ntickets", "99-query\nKB baseline"]
before_acc = [22.9, 22.9]
after_acc = [72.9, 68.7]
xg = np.arange(len(groups))
w = 0.32
for xi, v in zip(xg - w / 2 - 0.02, before_acc):
    rounded_bar(ax1, xi, v, w, STATUS_CRITICAL)
    value_label(ax1, xi, v, f"{v:.1f}%", color=INK_SECONDARY)
for xi, v in zip(xg + w / 2 + 0.02, after_acc):
    rounded_bar(ax1, xi, v, w, STATUS_GOOD)
    value_label(ax1, xi, v, f"{v:.1f}%", color=INK_SECONDARY)
ax1.set_xticks(xg)
ax1.set_xlim(xg[0] - 0.5, xg[-1] + 0.5)
ax1.set_xticklabels(groups, fontsize=9)
ax1.set_ylabel("Relevance-gate accuracy")
style_axis(ax1, 88)
handles = [plt.Rectangle((0, 0), 1, 1, fc=STATUS_CRITICAL), plt.Rectangle((0, 0), 1, 1, fc=STATUS_GOOD)]
fig.legend(handles, ["Before (old index, threshold 0.3)", "After (cleaned index, threshold 0.70)"],
           frameon=False, loc="upper center", bbox_to_anchor=(0.5, 0.90), ncol=2,
           fontsize=9, labelcolor=INK_SECONDARY)

mrr_before = [0.406, 0.469]
mrr_after = [0.651, 0.780]
for xi, v in zip(xg - w / 2 - 0.02, mrr_before):
    rounded_bar(ax2, xi, v, w, STATUS_CRITICAL)
    value_label(ax2, xi, v, f"{v:.3f}", color=INK_SECONDARY)
for xi, v in zip(xg + w / 2 + 0.02, mrr_after):
    rounded_bar(ax2, xi, v, w, STATUS_GOOD)
    value_label(ax2, xi, v, f"{v:.3f}", color=INK_SECONDARY)
ax2.set_xticks(xg)
ax2.set_xlim(xg[0] - 0.5, xg[-1] + 0.5)
ax2.set_xticklabels(groups, fontsize=9)
ax2.set_ylabel("MRR (0-1)")
style_axis(ax2, 1.0)

bottom = add_interview_note(fig,
    "We fixed two real causes — old content in the index, and a self-check that never said 'no' —\n"
    "and checked the improvement on two separate, independent tests, not just one. Gate accuracy\n"
    "roughly tripled on both. That's why we trust this is a real fix, not a lucky number.")
fig.tight_layout(rect=(0, bottom, 1, 0.83))
fig.savefig(FIG_DIR / "10_lms_before_after_fix.png", dpi=200)
plt.close(fig)

# --- Figures 11-12: FINAL numbers, read live, including F1 and Precision@2 --
lms = json.load(open(RESULTS_DIR / "v2_summary_metrics.json"))
q99 = json.load(open(RESULTS_DIR / "v1_summary_metrics.json"))

# --- Figure 11: Precision@k and Recall@k, final system, both datasets ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.8))
fig.suptitle("Final system — Precision and Recall at each cutoff (k=1 to k=4)", fontsize=13, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

k_labels = ["k=1", "k=2", "k=3", "k=4"]
xk = np.arange(4)
w = 0.32
lms_p = [lms["precision_at_1_with_relevant_only"] * 100, lms["precision_at_2_with_relevant_only"] * 100, lms["precision_at_3_with_relevant_only"] * 100, lms["precision_at_4_with_relevant_only"] * 100]
q99_p = [q99["precision_at_1_with_relevant_only"] * 100, q99["precision_at_2_with_relevant_only"] * 100, q99["precision_at_3_with_relevant_only"] * 100, q99["precision_at_4_with_relevant_only"] * 100]
p_offsets = [close_pair_offsets(a, b, 78) for a, b in zip(lms_p, q99_p)]
for xi, v, (off, _) in zip(xk - w / 2 - 0.02, lms_p, p_offsets):
    rounded_bar(ax1, xi, v, w, CAT["blue"])
    value_label(ax1, xi, v, f"{v:.1f}%", color=INK_SECONDARY, extra_offset=off, ymax=78)
for xi, v, (_, off) in zip(xk + w / 2 + 0.02, q99_p, p_offsets):
    rounded_bar(ax1, xi, v, w, CAT["orange"])
    value_label(ax1, xi, v, f"{v:.1f}%", color=INK_SECONDARY, extra_offset=off, ymax=78)
ax1.set_xticks(xk)
ax1.set_xlim(xk[0] - 0.5, xk[-1] + 0.5)
ax1.set_xticklabels(k_labels, fontsize=10)
ax1.set_ylabel("Precision@k (queries with a real answer)")
style_axis(ax1, 78)
handles = [plt.Rectangle((0, 0), 1, 1, fc=CAT["blue"]), plt.Rectangle((0, 0), 1, 1, fc=CAT["orange"])]
ax1.legend(handles, ["70 real tickets", "99-query baseline"], frameon=False, loc="upper right",
           fontsize=9, labelcolor=INK_SECONDARY)

lms_r = [lms["recall_at_1"] * 100, lms["recall_at_2"] * 100, lms["recall_at_3"] * 100, lms["recall_at_4"] * 100]
q99_r = [q99["recall_at_1"] * 100, q99["recall_at_2"] * 100, q99["recall_at_3"] * 100, q99["recall_at_4"] * 100]
r_offsets = [close_pair_offsets(a, b, 100) for a, b in zip(lms_r, q99_r)]
for xi, v, (off, _) in zip(xk - w / 2 - 0.02, lms_r, r_offsets):
    rounded_bar(ax2, xi, v, w, CAT["blue"])
    value_label(ax2, xi, v, f"{v:.1f}%", color=INK_SECONDARY, extra_offset=off, ymax=100)
for xi, v, (_, off) in zip(xk + w / 2 + 0.02, q99_r, r_offsets):
    rounded_bar(ax2, xi, v, w, CAT["orange"])
    value_label(ax2, xi, v, f"{v:.1f}%", color=INK_SECONDARY, extra_offset=off, ymax=100)
ax2.set_xticks(xk)
ax2.set_xlim(xk[0] - 0.5, xk[-1] + 0.5)
ax2.set_xticklabels(k_labels, fontsize=10)
ax2.set_ylabel("Recall@k (queries with a real answer)")
style_axis(ax2, 100)

bottom = add_interview_note(fig,
    f"Precision goes DOWN as k grows and Recall goes UP — that's arithmetic, not a flaw. If a slide only\n"
    f"has room for two numbers: Precision@1 = {lms_p[0]:.1f}% (is our top pick right?) and Recall@4 = {lms_r[3]:.1f}%\n"
    f"(is the answer in there at all?) — on the 70-ticket set. Say the caveat with them: this KB reflects\n"
    f"direct personal knowledge of these exact real tickets, and the 99-query baseline (a separate real\n"
    f"dataset) scores lower on every one of these same metrics — {q99_p[0]:.1f}% and {q99_r[3]:.1f}% respectively.\n"
    f"That gap is the honest measure of how much this result depends on knowing these specific tickets.")
fig.tight_layout(rect=(0, bottom, 1, 0.82))
fig.savefig(FIG_DIR / "11_final_precision_recall_by_k.png", dpi=200)
plt.close(fig)

# --- Figure 12: F1, MRR, nDCG@4 - final system, both datasets -----------
fig, ax = plt.subplots(figsize=(8, 5.8))
fig.suptitle("Final system — F1@4, MRR, and nDCG@4", fontsize=13, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

m_labels = ["F1@4", "MRR", "nDCG@4"]
xm = np.arange(3)
lms_m = [lms["f1_at_4"], lms["mrr"], lms["ndcg_at_4"]]
q99_m = [q99["f1_at_4"], q99["mrr"], q99["ndcg_at_4"]]
for xi, v in zip(xm - w / 2 - 0.02, lms_m):
    rounded_bar(ax, xi, v, w, CAT["blue"])
    value_label(ax, xi, v, f"{v:.3f}", color=INK_SECONDARY)
for xi, v in zip(xm + w / 2 + 0.02, q99_m):
    rounded_bar(ax, xi, v, w, CAT["orange"])
    value_label(ax, xi, v, f"{v:.3f}", color=INK_SECONDARY)
ax.set_xticks(xm)
ax.set_xlim(xm[0] - 0.5, xm[-1] + 0.5)
ax.set_xticklabels(m_labels, fontsize=10)
ax.set_ylabel("Score (0–1)")
style_axis(ax, 1.0)
handles = [plt.Rectangle((0, 0), 1, 1, fc=CAT["blue"]), plt.Rectangle((0, 0), 1, 1, fc=CAT["orange"])]
fig.legend(handles, ["70 real tickets", "99-query baseline"], frameon=False, loc="upper center",
           bbox_to_anchor=(0.5, 0.90), ncol=2, fontsize=9, labelcolor=INK_SECONDARY)

bottom = add_interview_note(fig,
    "F1@4 blends Precision@4 and Recall@4 into one number, so it doesn't hide behind whichever\n"
    "of the two looks better. All three scores here are higher on the 70-ticket set than on the\n"
    "99-query baseline, by a clear margin, on every one of the three formulas — that consistency\n"
    "is what makes it a real pattern: this KB fits its known tickets very well, and that strength\n"
    "has not yet been shown to carry over to real tickets the author hasn't personally seen (§6.4).")
fig.tight_layout(rect=(0, bottom, 1, 0.82))
fig.savefig(FIG_DIR / "12_final_f1_mrr_ndcg.png", dpi=200)
plt.close(fig)

print("Wrote 8 figures to", FIG_DIR)
