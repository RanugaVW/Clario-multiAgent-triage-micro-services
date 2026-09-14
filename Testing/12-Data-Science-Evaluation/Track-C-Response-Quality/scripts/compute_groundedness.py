"""Track C FINAL, step 3: same mechanical, independent groundedness check as
../pilot-99-query/scripts/compute_groundedness_99.py (see that file's
docstring for the full reasoning), pointed at the 70-ticket results.

Usage:
    python3 compute_groundedness.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from sentence_transformers import SentenceTransformer, util

_HERE = Path(__file__).resolve().parent
RESULTS_DIR = _HERE.parent / "results"
DRAFTS_PATH = RESULTS_DIR / "clario_full_graph_drafts.csv"
OUT_PATH = RESULTS_DIR / "groundedness.csv"

SIMILARITY_THRESHOLD = 0.35
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# See compute_groundedness_99.py's docstring/comment for why this exists:
# greeting/empathy/sign-off sentences carry no factual claim and would
# otherwise inflate "unsupported" with false positives (found via the
# pilot run - ~176/464 flagged, most boilerplate like "Hi there, thank you
# for reaching out." at 0.03 similarity). Starting-point list, not an
# exhaustive classifier, mirrored exactly from the pilot script.
BOILERPLATE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"^(hi|hello|dear)\b.{0,40}$",
        r"thank(s| you) for (reaching out|contacting|getting in touch|your patience)",
        r"^i understand (how|this|that)",
        r"^i (am|'m) sorry to hear",
        r"sorry for the inconvenience",
        r"please rest assured",
        r"we appreciate your patience",
        r"please (let us know|feel free|don'?t hesitate) if you (have|need)",
        r"let us know if you (need|have) anything else",
    ]
]


def extract_customer_response(draft: str) -> str:
    marker = "[CUSTOMER RESPONSE]"
    text = draft.split(marker, 1)[1].strip() if marker in draft else draft.strip()
    return text.replace("**", "")


def is_boilerplate(sentence: str) -> bool:
    return any(p.search(sentence) for p in BOILERPLATE_PATTERNS)


def main() -> None:
    if not DRAFTS_PATH.exists():
        print(f"{DRAFTS_PATH} not found - run run_full_graph_generation.py first.")
        return

    model = SentenceTransformer("all-MiniLM-L6-v2")

    with open(DRAFTS_PATH, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["draft"].strip()]

    out_rows = []
    for row in rows:
        customer_text = extract_customer_response(row["draft"])
        sentences = [s.strip() for s in SENTENCE_SPLIT.split(customer_text)
                     if len(s.strip()) > 15 and not is_boilerplate(s.strip())]
        sources = json.loads(row["retrieved_sources"] or "[]")

        if not sentences:
            continue
        if not sources:
            for s in sentences:
                out_rows.append({"query_id": row["query_id"], "domain_drafted": row["domain_drafted"],
                                  "sentence": s, "max_similarity": 0.0, "supported": False})
            continue

        sentence_emb = model.encode(sentences, convert_to_tensor=True)
        source_emb = model.encode(sources, convert_to_tensor=True)
        sim_matrix = util.cos_sim(sentence_emb, source_emb)
        max_sims = sim_matrix.max(dim=1).values.tolist()

        for s, sim in zip(sentences, max_sims):
            out_rows.append({"query_id": row["query_id"], "domain_drafted": row["domain_drafted"],
                              "sentence": s, "max_similarity": round(sim, 4),
                              "supported": sim >= SIMILARITY_THRESHOLD})

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query_id", "domain_drafted", "sentence", "max_similarity", "supported"])
        writer.writeheader()
        writer.writerows(out_rows)

    n_total = len(out_rows)
    n_unsupported = sum(1 for r in out_rows if not r["supported"])
    print(f"Wrote {n_total} sentence-level rows to {OUT_PATH}")
    print(f"{n_unsupported}/{n_total} ({100 * n_unsupported / n_total:.1f}%) sentences flagged unsupported "
          f"at threshold {SIMILARITY_THRESHOLD}.")


if __name__ == "__main__":
    main()
