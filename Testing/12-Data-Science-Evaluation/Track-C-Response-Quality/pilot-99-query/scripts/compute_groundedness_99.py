"""Track C PILOT, step 2: an independent, mechanical groundedness check -
does the draft actually say things the retrieved KB content backs up, or
did it make something up?

This is deliberately NOT the same as judge_groundedness_score already in
results/clario_full_graph_drafts_99.csv. That number is the judge LLM's
own opinion, and Track D's whole point was that a judge's opinion needs an
independent check before being trusted. This script provides that
independent check for groundedness specifically: split the draft's
customer-facing section into sentences, embed each with the same MiniLM
model the semantic-similarity check uses (all-MiniLM-L6-v2), and compare
against the retrieved KB chunks. A sentence with low similarity to
everything retrieved is flagged as unsupported.

SIMILARITY_THRESHOLD (0.35) is a starting point, not an empirically-tuned
value - it was picked as "clearly below a real paraphrase, clearly above
unrelated text" from spot-checking a few pairs by hand, the same way
Track B's early keyword weights were picked before being checked against
real data. Sanity-check it against a handful of known-good and
known-fabricated sentences before trusting the flagged list.

Only scores the [CUSTOMER RESPONSE] section (see validation_node.py's
SECTION_MARKER_PATTERN for the same drafts-have-bracketed-sections
convention) - the [INTERNAL TECHNICAL DETAILS] section is allowed to
reason beyond the retrieved text (that's its job), only the part the
customer actually reads needs to be grounded.

Usage:
    python3 compute_groundedness_99.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from sentence_transformers import SentenceTransformer, util

_HERE = Path(__file__).resolve().parent
RESULTS_DIR = _HERE.parent / "results"
DRAFTS_PATH = RESULTS_DIR / "clario_full_graph_drafts_99.csv"
OUT_PATH = RESULTS_DIR / "groundedness_99.csv"

SIMILARITY_THRESHOLD = 0.35
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Greeting/empathy/sign-off sentences carry no factual claim, so they can
# never match KB content and would otherwise inflate the "unsupported"
# count with false positives - spot-checking the first real run of this
# script found ~176/464 flagged sentences, and most were boilerplate like
# "Hi there, thank you for reaching out." (0.03 similarity, correctly so -
# a greeting isn't a claim to ground). This list is a starting point built
# from those observed phrases, not an exhaustive classifier - same
# "starting guess, needs spot-checking" status as SIMILARITY_THRESHOLD.
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
    """Pull just the customer-facing section out of the bracketed-section
    draft format; falls back to the whole draft if no marker is found (an
    older or differently-shaped draft), so this never silently scores
    nothing."""
    marker = "[CUSTOMER RESPONSE]"
    text = draft.split(marker, 1)[1].strip() if marker in draft else draft.strip()
    return text.replace("**", "")  # strip markdown bold - was gluing onto the next sentence


def is_boilerplate(sentence: str) -> bool:
    return any(p.search(sentence) for p in BOILERPLATE_PATTERNS)


def main() -> None:
    if not DRAFTS_PATH.exists():
        print(f"{DRAFTS_PATH} not found - run run_full_graph_generation_99.py first.")
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
            # Nothing was retrieved at all - every sentence is by definition ungrounded.
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
          f"at threshold {SIMILARITY_THRESHOLD} - spot-check a sample before trusting this number.")


if __name__ == "__main__":
    main()
