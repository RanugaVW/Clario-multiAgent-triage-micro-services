"""Regenerates ONLY the figures whose numbers changed because the ground
truth was rebuilt from the corrected annotator CSVs (see
rebuild_real_ground_truth.py and TEST_REPORT_V2.md's "Correction" section).

That is exactly three of the eight LMS-track figures:
  - Figure 5 (two-person agreement) - directly about the annotator files.
  - Figure 11 (Precision@k / Recall@k, final system)
  - Figure 12 (F1@4 / MRR / nDCG@4, final system)
  ...now read from results/v3_summary_metrics.json instead of v2.

Figures 6-10 are NOT regenerated here: they depict the system at earlier,
now-superseded states (old 0.3 threshold, stale content still in the index).
Reproducing them against the corrected ground truth would mean deliberately
reintroducing those old bugs just to re-measure them - out of scope for
this correction, which re-measures the CURRENT system only. They stay as
the historical record they always were; see the report's "Correction"
section for the full explanation.

Same drawing conventions as make_figures_lms.py (validated palette, rounded
bars, hairline gridlines, plain-English interview captions).
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
    scale = ymax if ymax is not None else ax.get_ylim()[1]
    ax.text(x, y + (0.02 + extra_offset) * scale, text, ha="center", va="bottom",
             fontsize=10, color=color, fontweight="medium")


def close_pair_offsets(v1, v2, ymax, threshold_frac=0.04):
    if abs(v1 - v2) < threshold_frac * ymax:
        return (0.05, 0.0) if v1 >= v2 else (0.0, 0.05)
    return (0.0, 0.0)


def add_interview_note(fig, text, extra_lines_above=0):
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


# --- Figure 5: two-person agreement (CORRECTED annotator files) ---------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.6), width_ratios=[1, 1.4])
fig.suptitle("Track A — two-person manual classification of 70 real tickets (corrected)", fontsize=12.5, color=INK_PRIMARY, x=0.02, y=0.97, ha="left")

labels = ["Exact match\n(same domain + doc)", "Partial overlap\n(union resolved)", "No overlap\n(union resolved)"]
vals = [47, 13, 10]
colors = [STATUS_GOOD, "#e0a52c", STATUS_CRITICAL]
x = np.arange(len(labels))
for xi, v, c in zip(x, vals, colors):
    rounded_bar(ax1, xi, v, 0.5, c)
    value_label(ax1, xi, v, f"{v} ({v/70*100:.1f}%)")
ax1.set_xticks(x)
ax1.set_xticklabels(labels, fontsize=9)
ax1.set_ylabel("Tickets (of 70)")
style_axis(ax1, 68)

dom_labels = ["billing", "technical", "hr"]
ranuga = [30, 27, 20]
sineth = [24, 27, 23]
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
ax2.set_ylabel("Tickets labelled (multi-domain rows count once per domain)")
style_axis(ax2, 36)
handles = [plt.Rectangle((0, 0), 1, 1, fc=CAT["blue"]), plt.Rectangle((0, 0), 1, 1, fc=CAT["orange"])]
ax2.legend(handles, ["Annotator 1 (Ranuga)", "Annotator 2 (Sineth)"], frameon=False, loc="upper right",
           fontsize=9, labelcolor=INK_SECONDARY)

bottom = add_interview_note(fig,
    "Two of us labelled all 70 real tickets by hand, separately, without comparing notes first.\n"
    "Domain and document matched exactly on 67.1%; broadening to \"any overlap\" (exact + partial)\n"
    "brings that to 85.7%. All 23 non-exact rows were resolved by taking the union of both answers.")
fig.tight_layout(rect=(0, bottom, 1, 0.90))
fig.savefig(FIG_DIR / "05_lms_annotator_agreement.png", dpi=200)
plt.close(fig)

# --- Figures 11-12: FINAL numbers, read live, now from v3 -----------------
lms = json.load(open(RESULTS_DIR / "v3_summary_metrics.json"))
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
    f"(is the answer in there at all?) — on the 70-ticket set, corrected ground truth. The 99-query\n"
    f"baseline (a separate real dataset) scores {q99_p[0]:.1f}% and {q99_r[3]:.1f}% respectively on the same two.\n"
    f"These numbers reflect the corrected, independently-annotated ground truth — see the report's Correction section.")
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
    "of the two looks better. These are the corrected numbers (see the report's Correction section):\n"
    "MRR and nDCG@4 are still higher on the 70-ticket set than the 99-query baseline, though the\n"
    "gap is narrower than it was under the earlier, incorrect ground truth.")
fig.tight_layout(rect=(0, bottom, 1, 0.82))
fig.savefig(FIG_DIR / "12_final_f1_mrr_ndcg.png", dpi=200)
plt.close(fig)

print("Wrote 3 corrected figures (05, 11, 12) to", FIG_DIR)
