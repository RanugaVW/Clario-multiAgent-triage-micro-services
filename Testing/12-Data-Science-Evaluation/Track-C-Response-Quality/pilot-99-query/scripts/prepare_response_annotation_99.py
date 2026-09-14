"""Track C PILOT, step 1b (after run_full_graph_generation_99.py): build the
sheet two humans use to write qualitative improvement notes on Clario's
actual generated replies for the 99-query set.

This exists because the 99-query set has no real human reply to compare
against (see ../README.md), so checks 1 (pairwise) and 3 (semantic
similarity) can't run here - there is nothing to compare Clario's draft
to. Open-ended human notes on the draft itself are the substitute: they
catch problems no automated check here is built to catch (wrong tone,
missed part of the question, technically fine but not actually helpful),
the same way Track B's human annotation surfaced real routing/escalation
gaps before real API cost was spent on the 70-ticket round.

One row per domain-drafted ticket (skips escalated-before-drafting rows,
which have no draft text to annotate). human1_flag/human2_flag use a
short fixed set of tags so agreement between the two humans is countable
later (Cohen's kappa, same tool used throughout this evaluation); the
notes columns are free text for what specifically should be enhanced.

Usage:
    python3 prepare_response_annotation_99.py
"""

from __future__ import annotations

import csv
from pathlib import Path

_HERE = Path(__file__).resolve().parent
RESULTS_DIR = _HERE.parent / "results"
DATA_DIR = _HERE.parent / "data"
DRAFTS_PATH = RESULTS_DIR / "clario_full_graph_drafts_99.csv"
GT_PATH = _HERE.parent.parent.parent / "Track-A-Retrieval-Quality" / "data" / "retrieval_ground_truth.csv"
OUT_PATH = DATA_DIR / "response_annotation_99.csv"

# Kept identical to compute_groundedness_99.py's helper of the same name -
# both need the customer-facing section only, not the internal reasoning.
def extract_customer_response(draft: str) -> str:
    marker = "[CUSTOMER RESPONSE]"
    if marker not in draft:
        return draft.strip()
    return draft.split(marker, 1)[1].strip()


FLAG_OPTIONS = "good / needs_improvement / wrong_or_inaccurate / too_generic / tone_issue / missing_info"


def main() -> None:
    if not DRAFTS_PATH.exists():
        print(f"{DRAFTS_PATH} not found - run run_full_graph_generation_99.py first.")
        return

    with open(DRAFTS_PATH, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["draft"].strip()]

    with open(GT_PATH, newline="", encoding="utf-8-sig") as f:
        ticket_text_by_id = {r["query_id"]: r["query_text"] for r in csv.DictReader(f)}

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "query_id", "domain", "ticket_text", "category", "priority", "sentiment", "clario_draft",
        "human1_flag", "human1_notes", "human2_flag", "human2_notes",
    ]
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "query_id": row["query_id"],
                "domain": row["domain_drafted"] or row["gt_domain"],
                "ticket_text": ticket_text_by_id.get(row["query_id"], ""),
                # Same local-LLM classification the real graph routed and drafted from -
                # gives the two humans the context Clario itself was working with,
                # so a flag like "tone_issue" can be judged against the right priority/sentiment
                # instead of the reviewer having to guess it from the ticket text alone.
                "category": row["category"],
                "priority": row["priority"],
                "sentiment": row["sentiment"],
                "clario_draft": extract_customer_response(row["draft"]),
                "human1_flag": "", "human1_notes": "",
                "human2_flag": "", "human2_notes": "",
            })

    print(f"Wrote {len(rows)} rows to {OUT_PATH}")
    print(f"human1_flag/human2_flag options: {FLAG_OPTIONS}")


if __name__ == "__main__":
    main()
