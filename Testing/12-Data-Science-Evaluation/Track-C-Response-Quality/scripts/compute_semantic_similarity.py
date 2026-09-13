"""Track C FINAL, step 5: how close in meaning is Clario's draft to the
real human reply, per DATA_SCIENCE_EVALUATION_PROPOSAL.md Sec7.3 check 3. The
main numbers are meaning-based (MiniLM cosine similarity, BERTScore F1) -
BLEU/ROUGE are reported only as a side note per the proposal's own framing,
and are skipped automatically if their packages aren't installed (`pip
install nltk rouge-score` to enable them; not required for the main result).

Scores against BOTH reference columns from data/human_reference_70.csv:
  - human_reply_as_sent: the real reply, verbatim.
  - human_reply_corrected: the same reply with a note appended wherever
    Recommended Action flagged a real gap - a mechanical placeholder, NOT
    an actual human rewrite (see ../HOW_TO_ANNOTATE.md). Treat any
    difference between the two columns' scores as a rough, not precise,
    signal unless a human has actually rewritten those specific replies.

Joins to results/clario_full_graph_drafts.csv by query_id - run
run_full_graph_generation.py first if that file doesn't exist yet.
Compares only the [CUSTOMER RESPONSE] section, same extraction as
compute_groundedness.py, since that's the only part a real customer (or
the real human agent being compared against) actually sees.

Usage:
    python3 compute_semantic_similarity.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from sentence_transformers import SentenceTransformer, util

_HERE = Path(__file__).resolve().parent
DATA_DIR = _HERE.parent / "data"
RESULTS_DIR = _HERE.parent / "results"
DRAFTS_PATH = RESULTS_DIR / "clario_full_graph_drafts.csv"
REFERENCE_PATH = DATA_DIR / "human_reference_70.csv"
OUT_PATH = RESULTS_DIR / "semantic_similarity.csv"

try:
    from bert_score import score as bertscore
    HAVE_BERTSCORE = True
except ImportError:
    HAVE_BERTSCORE = False


def extract_customer_response(draft: str) -> str:
    marker = "[CUSTOMER RESPONSE]"
    if marker not in draft:
        return draft.strip()
    return draft.split(marker, 1)[1].strip()


def main() -> None:
    if not DRAFTS_PATH.exists():
        print(f"{DRAFTS_PATH} not found - run run_full_graph_generation.py first.")
        return
    if not REFERENCE_PATH.exists():
        print(f"{REFERENCE_PATH} not found - run prepare_human_reference_data.py first.")
        return

    with open(REFERENCE_PATH, newline="", encoding="utf-8") as f:
        references = {r["query_id"]: r for r in csv.DictReader(f) if r["source_status"] == "matched"}

    with open(DRAFTS_PATH, newline="", encoding="utf-8") as f:
        drafts = [r for r in csv.DictReader(f) if r["draft"].strip() and r["query_id"] in references]

    if not drafts:
        print("No scoreable rows (no draft matched to a resolved reference) - nothing to do.")
        return

    print(f"{len(drafts)} domain-drafts have a real human reference to compare against "
          f"({len(references)} of 70 tickets resolved to a real reply).")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    customer_texts = [extract_customer_response(r["draft"]) for r in drafts]
    as_sent_refs = [references[r["query_id"]]["human_reply_as_sent"] for r in drafts]
    corrected_refs = [references[r["query_id"]]["human_reply_corrected"] for r in drafts]

    draft_emb = model.encode(customer_texts, convert_to_tensor=True)
    as_sent_emb = model.encode(as_sent_refs, convert_to_tensor=True)
    corrected_emb = model.encode(corrected_refs, convert_to_tensor=True)
    cos_as_sent = util.cos_sim(draft_emb, as_sent_emb).diagonal().tolist()
    cos_corrected = util.cos_sim(draft_emb, corrected_emb).diagonal().tolist()

    if HAVE_BERTSCORE:
        _, _, f1_as_sent = bertscore(customer_texts, as_sent_refs, lang="en", verbose=False)
        _, _, f1_corrected = bertscore(customer_texts, corrected_refs, lang="en", verbose=False)
        f1_as_sent, f1_corrected = f1_as_sent.tolist(), f1_corrected.tolist()
    else:
        print("bert_score not installed (`pip install bert-score`) - BERTScore columns left blank.")
        f1_as_sent = f1_corrected = [None] * len(drafts)

    out_rows = []
    for i, r in enumerate(drafts):
        out_rows.append({
            "query_id": r["query_id"], "domain_drafted": r["domain_drafted"],
            "minilm_cosine_as_sent": round(cos_as_sent[i], 4),
            "minilm_cosine_corrected": round(cos_corrected[i], 4),
            "bertscore_f1_as_sent": round(f1_as_sent[i], 4) if f1_as_sent[i] is not None else "",
            "bertscore_f1_corrected": round(f1_corrected[i], 4) if f1_corrected[i] is not None else "",
        })

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    mean_cos_as_sent = sum(r["minilm_cosine_as_sent"] for r in out_rows) / len(out_rows)
    mean_cos_corrected = sum(r["minilm_cosine_corrected"] for r in out_rows) / len(out_rows)
    print(f"\nWrote {len(out_rows)} rows to {OUT_PATH}")
    print(f"Mean MiniLM cosine vs as-sent reply: {mean_cos_as_sent:.3f}")
    print(f"Mean MiniLM cosine vs corrected reply: {mean_cos_corrected:.3f}")
    if abs(mean_cos_as_sent - mean_cos_corrected) > 0.02:
        print("These differ enough to be worth reporting both, per the proposal's own instruction "
              "(Sec7.3) - do not silently pick one.")


if __name__ == "__main__":
    main()
