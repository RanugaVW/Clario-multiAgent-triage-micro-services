"""Weekly KB-gap detection: what are customers asking that the KB cannot answer?

Behind KB_GAP_DETECTION_ENABLED. Collects recent tickets with a weak signal
(low retrieval score, low judged groundedness, or a low customer rating),
clusters them by meaning, drops clusters the KB already covers (that is a
generation problem, not a missing document), and drafts a proposed document
per remaining cluster into KB_PROPOSALS_DIR for a human to review. Proposals
are never written into vector_store/kb_documents/: a hallucinated policy in
the KB is worse than a gap.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from app.tools.feedback_learning import (
    as_list,
    feature_enabled,
    get_supabase as _get_supabase,
    issue_text,
    masked,
)
from app.tools.few_shot_selector import _embedder
from app.tools.rag_tool import check_relevance, retrieve_context

logger = logging.getLogger(__name__)

FLAG = "KB_GAP_DETECTION_ENABLED"
_ROOT = Path(__file__).resolve().parents[2]
_KB_DOCS_DIR = (_ROOT / "vector_store" / "kb_documents").resolve()
_VALID_DOMAINS = ("technical", "billing", "hr")
_SELECT = (
    "id, raw_text, ticket_drafts(domain, rag_top_score), response_evaluations(groundedness_score), "
    "customer_feedback(score), resolutions(final_response, escalated, resolved_by)"
)
_PROMPT = """You are writing a new knowledge-base document for a customer-support assistant. Several real customers asked about the same topic and the existing knowledge base has no document that covers it.

Customer tickets (personal details removed):
{tickets}

Replies written by human support staff for some of these tickets (the ONLY trusted source of facts):
{resolutions}

Write ONE markdown document with exactly this structure:
# <Short topic title>
## Common customer phrasing
- <3-6 bullets: how customers describe this issue, paraphrased from the tickets>
## Guidance
<Steps and policy the assistant should follow, using ONLY facts stated in the staff replies above. If the staff replies do not establish a fact, do not state it; write [NEEDS CONFIRMATION] instead.>

Do not include names, emails, order numbers, or amounts."""


def _rag_threshold() -> float:
    return float(os.getenv("RAG_SCORE_THRESHOLD", "0.70"))


def _groundedness_max() -> int:
    return int(os.getenv("KB_GAP_GROUNDEDNESS_MAX", "3"))


def _customer_max() -> int:
    return int(os.getenv("KB_GAP_CUSTOMER_MAX", "2"))


def _min_cluster_size() -> int:
    return max(2, int(os.getenv("KB_GAP_MIN_CLUSTER_SIZE", "3")))


def _distance_threshold() -> float:
    # 0.45 from a check against real MiniLM embeddings: at 0.35 same-topic
    # tickets stayed split. Proposals are human-reviewed, so favor recall.
    return float(os.getenv("KB_GAP_DISTANCE_THRESHOLD", "0.45"))


def _max_tickets() -> int:
    return int(os.getenv("KB_GAP_MAX_TICKETS", "1000"))


def _proposals_dir() -> Path:
    configured = Path(os.getenv("KB_PROPOSALS_DIR", "./vector_store/kb_proposals"))
    path = (configured if configured.is_absolute() else _ROOT / configured).resolve()
    if path == _KB_DOCS_DIR or _KB_DOCS_DIR in path.parents:
        raise ValueError("KB proposals must never be written inside kb_documents; a human reviews them first")
    return path


def _llm(prompt: str) -> str:
    from app.tools.local_llm import llm_invoke

    return llm_invoke(prompt, temperature=0.2)


def _embed(texts: list[str]) -> np.ndarray:
    return np.asarray(_embedder().encode(texts, normalize_embeddings=True))


def detect_kb_gaps(lookback_days: int = 7) -> dict:
    summary = {"candidates": 0, "clusters": 0, "covered": 0, "proposed": 0, "skipped": 0}
    if not feature_enabled(FLAG):
        return {**summary, "disabled": True}
    _proposals_dir()  # fail loudly on a misconfigured directory before any work

    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    try:
        rows = (
            _get_supabase().table("tickets").select(_SELECT)
            .gte("created_at", cutoff).limit(_max_tickets()).execute().data or []
        )
    except Exception as e:
        logger.error(f"Failed to fetch tickets for KB-gap detection: {e}")
        return summary

    candidates = [c for c in (_candidate(row) for row in rows) if c]
    summary["candidates"] = len(candidates)
    if len(candidates) < _min_cluster_size():
        return summary

    vectors = _embed([c["text"] for c in candidates])
    labels = AgglomerativeClustering(
        n_clusters=None, distance_threshold=_distance_threshold(), metric="cosine", linkage="average",
    ).fit_predict(vectors)
    groups: dict[int, list[int]] = {}
    for index, label in enumerate(labels):
        groups.setdefault(int(label), []).append(index)

    for members in groups.values():
        if len(members) < _min_cluster_size():
            continue
        summary["clusters"] += 1
        try:
            outcome = _process_cluster([candidates[i] for i in members], vectors[members])
        except Exception as e:
            logger.warning(f"KB-gap cluster failed: {e}")
            outcome = "skipped"
        summary[outcome] += 1

    logger.info(f"KB-gap detection: {summary}")
    return summary


def _candidate(ticket: dict) -> dict | None:
    drafts = as_list(ticket.get("ticket_drafts"))
    rag = [float(d["rag_top_score"]) for d in drafts if d.get("rag_top_score") is not None]
    grounded = [
        e["groundedness_score"] for e in as_list(ticket.get("response_evaluations"))
        if isinstance(e.get("groundedness_score"), int)
    ]
    rated = [f["score"] for f in as_list(ticket.get("customer_feedback")) if isinstance(f.get("score"), int)]

    signals = []
    if rag and min(rag) < _rag_threshold():
        signals.append("low_rag")
    if grounded and min(grounded) <= _groundedness_max():
        signals.append("low_groundedness")
    if rated and min(rated) <= _customer_max():
        signals.append("low_customer_rating")
    text = masked(issue_text(ticket.get("raw_text")))
    if not signals or not text:
        return None

    domains = [d.get("domain") for d in drafts if d.get("domain") in _VALID_DOMAINS]
    human = [
        r["final_response"] for r in as_list(ticket.get("resolutions"))
        if r.get("resolved_by") and not r.get("escalated") and r.get("final_response")
    ]
    return {
        "id": ticket["id"], "text": text, "signals": signals,
        "domain": Counter(domains).most_common(1)[0][0] if domains else "technical",
        "human_reply": masked(human[0]) if human else None,
    }


def _process_cluster(cluster: list[dict], vectors: np.ndarray) -> str:
    centroid = vectors.mean(axis=0)
    representative = cluster[int(np.argmax(vectors @ centroid))]
    domain = Counter(c["domain"] for c in cluster).most_common(1)[0][0]

    matches = retrieve_context(representative["text"], domain)
    if check_relevance(matches):
        return "covered"

    path = _proposals_dir() / f"{domain}-{_slug(cluster)}.md"
    if path.exists():
        return "skipped"  # already proposed

    body = _llm(_PROMPT.format(
        tickets="\n".join(f"- {c['text']}" for c in cluster[:5]),
        resolutions="\n".join(f"- {c['human_reply']}" for c in cluster if c["human_reply"]) or "(none available)",
    )).strip()
    if not body:
        return "skipped"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_frontmatter(cluster, domain, matches) + body + "\n", encoding="utf-8")
    return "proposed"


def _slug(cluster: list[dict]) -> str:
    return hashlib.sha1(",".join(sorted(c["id"] for c in cluster)).encode()).hexdigest()[:10]


def _frontmatter(cluster: list[dict], domain: str, matches: list[dict]) -> str:
    signals = Counter(s for c in cluster for s in c["signals"])
    best = max((float(m.get("score", 0.0)) for m in matches), default=0.0)
    ids = "\n".join(f"  - {c['id']}" for c in sorted(cluster, key=lambda c: c["id"]))
    counts = ", ".join(f"{name}: {count}" for name, count in sorted(signals.items()))
    return (
        "---\nstatus: proposed\n"
        f"generated_at: {datetime.now(timezone.utc).isoformat()}\n"
        f"domain: {domain}\ncluster_size: {len(cluster)}\n"
        f"signals: {{{counts}}}\nkb_best_score: {best:.3f}\nticket_ids:\n{ids}\n---\n\n"
    )
