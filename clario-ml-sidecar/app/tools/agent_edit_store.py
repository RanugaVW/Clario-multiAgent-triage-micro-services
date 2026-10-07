"""Generalized takeaways learned from human-agent edits (Chroma: agent_edit_refs).

Written by app/jobs/sync_agent_edits.py, read by the specialist agents. Reading
is gated by AGENT_EDIT_LEARNING_ENABLED and can never raise: a broken learning
store must not stop a ticket from being drafted.
"""

from __future__ import annotations

import logging
import os

from app.tools.feedback_learning import deterministic_id, feature_enabled
from app.tools.few_shot_selector import _embedder, _get_client

logger = logging.getLogger(__name__)

COLLECTION_NAME = "agent_edit_refs"
FLAG = "AGENT_EDIT_LEARNING_ENABLED"


def upsert_agent_edit(
    *, review_id: str, issue_text: str, takeaway: str, edit_type: str,
    domain: str, category: str, priority: str, sentiment: str,
) -> None:
    if not issue_text or not takeaway:
        return
    collection = _get_client().get_or_create_collection(COLLECTION_NAME)
    collection.upsert(
        ids=[deterministic_id("edit", review_id)],
        embeddings=[_embedder().encode(issue_text, normalize_embeddings=True).tolist()],
        documents=[takeaway],
        metadatas=[{
            "edit_type": edit_type, "domain": domain, "category": category,
            "priority": priority, "sentiment": sentiment, "review_id": review_id,
        }],
    )


def select_agent_edits(
    ticket_text: str, domain: str, k: int = 3, min_similarity: float | None = None,
) -> list[dict]:
    if not feature_enabled(FLAG) or not ticket_text:
        return []
    threshold = min_similarity if min_similarity is not None else float(os.getenv("AGENT_EDIT_MIN_SIMILARITY", "0.5"))
    try:
        try:
            collection = _get_client().get_collection(COLLECTION_NAME)
        except Exception:
            return []  # nothing learned yet
        result = collection.query(
            query_embeddings=[_embedder().encode(ticket_text, normalize_embeddings=True).tolist()],
            n_results=k,
            where={"domain": domain},
            include=["documents", "metadatas", "distances"],
        )
        edits = []
        for doc, meta, dist in zip(
            (result.get("documents") or [[]])[0],
            (result.get("metadatas") or [[]])[0],
            (result.get("distances") or [[]])[0],
        ):
            similarity = max(0.0, 1.0 - float(dist) / 2.0)  # same conversion as few_shot_selector
            if similarity >= threshold:
                edits.append({
                    "takeaway": doc, "edit_type": meta.get("edit_type", "style"),
                    "similarity": round(similarity, 4), "review_id": meta.get("review_id", ""),
                })
        return edits
    except Exception as e:
        logger.warning(f"Agent-edit retrieval failed, continuing without it: {e}")
        return []


def format_edit_guidance(edits: list[dict]) -> str | None:
    """Style takeaways as prompt guidance; facts travel as context items instead."""
    style = [e["takeaway"] for e in edits if e["edit_type"] == "style"]
    if not style:
        return None
    bullets = "\n".join(f"- {t}" for t in style)
    return (
        "Style guidance learned from how human agents corrected similar replies "
        f"(tone and phrasing only, not facts):\n{bullets}"
    )


def factual_context_items(edits: list[dict]) -> list[dict]:
    """Factual takeaways as retrieved-context items so they are citable and judgeable.

    score 0.0: check_relevance() reads the *max* score, so these can never make a
    weak retrieval look relevant.
    """
    return [
        {"source_file": "agent_edit_correction", "text": e["takeaway"], "score": 0.0}
        for e in edits if e["edit_type"] == "factual"
    ]
