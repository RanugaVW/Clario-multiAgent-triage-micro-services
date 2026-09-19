"""Chroma retrieval and relevance evaluation shared by orchestration nodes."""

from __future__ import annotations

import os
import re
from pathlib import Path

import chromadb
from chromadb.errors import NotFoundError
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from app.tools.circuit_breaker import CircuitBreakerOpenError, get_breaker
from app.tools.kb_taxonomy import categories_for_doc
from app.tools.taxonomy import normalize_categories

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_COLLECTION_NAME = "kb_support_docs"
_embedder: SentenceTransformer | None = None

# Label-aware retrieval: predicted categories re-rank the domain-filtered
# candidates. They are a soft signal, never a filter - category exact-set
# accuracy is ~0.81, so a hard filter would hide the right document whenever
# the classifier is wrong. Below LABEL_MIN_CONFIDENCE (the calibrated
# category-token confidence) the labels are ignored entirely.
LABEL_MIN_CONFIDENCE = float(os.getenv("RAG_LABEL_MIN_CONFIDENCE", "0.5"))
LABEL_BOOST = float(os.getenv("RAG_LABEL_BOOST", "0.05"))
LABEL_CANDIDATES = 12


_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


def _chroma_path() -> str:
    configured = Path(os.getenv("CHROMA_PATH", "./vector_store/chroma_data"))
    return str(configured if configured.is_absolute() else _ROOT / configured)


def _embedding_model() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(_MODEL_NAME)
    return _embedder


def canonicalize_ticket_text(text: str) -> str:
    """Normalize ticket text so semantically equivalent issues compare more reliably."""
    cleaned = text.lower().strip()
    cleaned = _PUNCT_RE.sub(" ", cleaned)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def labels_trusted(categories: list[str] | str | None, confidence: float | None) -> list[str]:
    """The predicted labels retrieval may act on, or [] when it should ignore them.

    No confidence means the caller could not measure it (e.g. the Gemini
    fallback), which is treated as untrusted rather than as certain.
    """
    labels = normalize_categories(categories)
    if not labels or confidence is None or confidence < LABEL_MIN_CONFIDENCE:
        return []
    return labels


def rerank_by_categories(
    matches: list[dict],
    categories: list[str],
    k: int,
    boost: float = LABEL_BOOST,
    cover: bool = True,
    cover_floor: float = 0.0,
) -> list[dict]:
    """Order matches by cosine score plus a bonus for sharing a predicted label.

    Every match keeps its true cosine ``score`` - the relevance gate reads it,
    and a bonus must never lift a weak document over that threshold. Only the
    order and the top-k membership change.

    With ``cover`` and several predicted labels, each label first claims its own
    best-scoring document (if it scores at least ``cover_floor``), so a ticket
    about a refund *and* a login problem gets a document for each instead of k
    for whichever issue dominates the embedding. Remaining slots go to the
    highest boosted scores, and the final list is ordered by boosted score.
    """
    if not matches or not categories:
        return matches[:k]

    tagged: list[dict] = []
    for match in matches:
        tags = set(categories_for_doc(match["source_file"]))
        shared = [c for c in categories if c in tags]
        tagged.append({**match, "categories": sorted(tags), "label_match": bool(shared), "_shared": shared})

    def rank_key(match: dict) -> float:
        return match["score"] + (boost if match["label_match"] else 0.0)

    def taken(match: dict, group: list[dict]) -> bool:
        return any(match is member for member in group)

    reserved: list[dict] = []
    if cover and len(categories) > 1:
        for category in categories:
            claimants = [
                m for m in tagged
                if category in m["_shared"] and m["score"] >= cover_floor and not taken(m, reserved)
            ]
            if claimants:
                reserved.append(max(claimants, key=lambda m: m["score"]))
        reserved = sorted(reserved, key=rank_key, reverse=True)[:k]

    fill = sorted((m for m in tagged if not taken(m, reserved)), key=rank_key, reverse=True)
    selected = reserved + fill[: k - len(reserved)]
    ordered = sorted(selected, key=rank_key, reverse=True)
    for match in ordered:
        match.pop("_shared", None)
    return ordered


def retrieve_context(
    query: str,
    domain: str,
    k: int = 4,
    categories: list[str] | str | None = None,
    category_confidence: float | None = None,
) -> list[dict]:
    """Return up to k domain-filtered KB matches with cosine-similarity scores.

    When the classifier's category labels are supplied and trusted (see
    labels_trusted), documents tagged with those labels are ranked ahead of
    equally-similar ones. Without them the result is exactly the plain
    domain-filtered top-k.
    """
    if domain not in {"technical", "billing", "hr"}:
        raise ValueError("domain must be 'technical', 'billing', or 'hr'")
    labels = labels_trusted(categories, category_confidence)
    pool = max(k, LABEL_CANDIDATES) if labels else k
    breaker = get_breaker("chroma_rag")
    if not breaker.allow_request():
        raise CircuitBreakerOpenError("chroma_rag circuit breaker is open")
    try:
        client = chromadb.PersistentClient(path=_chroma_path())

        matches = []
        embeds = [_embedding_model().encode(query, normalize_embeddings=True).tolist()]

        # Query standard support docs. Excludes precedent_memory: those
        # documents are OTHER customers' full ticket narratives (product
        # names, specific circumstances), and feeding them here means the
        # specialist prompt's "answer ONLY from retrieved context" instruction
        # makes the LLM copy those specifics into a new customer's response
        # even when that customer never mentioned them - confirmed live: a
        # customer who only said "this course" got told "the AI course did
        # not meet your expectations", copied verbatim from three unrelated
        # customers' precedent tickets that all happened to name that course.
        # precedent_memory still fully serves its real purpose - exact-match
        # cache-hit reuse in cache_check_node.py, which queries it directly
        # and never calls this function.
        try:
            collection = client.get_collection(_COLLECTION_NAME)
            result = collection.query(
                query_embeddings=embeds,
                n_results=pool,
                where={"$and": [{"domain": domain}, {"source_file": {"$ne": "precedent_memory"}}]},
                include=["documents", "metadatas", "distances"],
            )
            docs = result.get("documents", [[]])[0] or []
            metas = result.get("metadatas", [[]])[0] or []
            dists = result.get("distances", [[]])[0] or []
            for text, item, distance in zip(docs, metas, dists):
                matches.append({
                    "text": text,
                    "source_file": item.get("source_file", "unknown"),
                    "score": max(0.0, 1.0 - (float(distance) / 2.0)),
                })
        except (ValueError, NotFoundError):
            pass
            
        # Query codebase if technical
        if domain == "technical":
            try:
                code_coll = client.get_collection("kb_codebase")
                code_res = code_coll.query(
                    query_embeddings=embeds,
                    n_results=k,
                    include=["documents", "metadatas", "distances"],
                )
                c_docs = code_res.get("documents", [[]])[0] or []
                c_metas = code_res.get("metadatas", [[]])[0] or []
                c_dists = code_res.get("distances", [[]])[0] or []
                for text, item, distance in zip(c_docs, c_metas, c_dists):
                    matches.append({
                        "text": text,
                        "source_file": item.get("source_file", "unknown"),
                        "score": max(0.0, 1.0 - (float(distance) / 2.0)),
                    })
            except (ValueError, NotFoundError):
                pass
                
    except Exception:
        breaker.record_failure()
        raise
        
    breaker.record_success()
    # Defense in depth: the where-clause above should already exclude these,
    # but never let a precedent_memory document (another customer's full
    # ticket narrative) reach a generation prompt even if that filter is
    # ever bypassed.
    matches = [match for match in matches if match["source_file"] != "precedent_memory"]
    # Sort combined matches by score descending and keep top k
    matches.sort(key=lambda x: x["score"], reverse=True)
    if labels:
        return rerank_by_categories(matches, labels, k)
    return matches[:k]


def check_relevance(retrieved_context: list[dict], threshold: float | None = None) -> bool:
    """Return whether the best match meets the configured similarity threshold.

    Reads the highest cosine score rather than the first item: label-aware
    re-ranking can place a slightly lower-scoring, correctly-labelled document
    first, and that must not flip the gate.
    """
    if not retrieved_context:
        return False
    score_threshold = threshold if threshold is not None else float(os.getenv("RAG_SCORE_THRESHOLD", "0.70"))
    best = max(float(match.get("score", 0.0)) for match in retrieved_context)
    return best >= score_threshold


def add_precedent(ticket_id: str, redacted_text: str, final_response: str, domain: str) -> None:
    """Embeds a resolved ticket into the vector store for future RAG retrieval."""
    if not redacted_text or not final_response:
        return
        
    try:
        client = chromadb.PersistentClient(path=_chroma_path())
        collection = client.get_or_create_collection(_COLLECTION_NAME)
        
        # Only embed the ticket issue, but keep resolution in the stored document
        content = f"Ticket Issue:\n{redacted_text}\n\nResolution:\n{final_response}"
        normalized_text = canonicalize_ticket_text(redacted_text)
        
        # We use a deterministic ID based on the ticket_id
        doc_id = f"precedent_{ticket_id}"
        
        # Insert or update
        collection.upsert(
            ids=[doc_id],
            embeddings=[_embedding_model().encode(normalized_text, normalize_embeddings=True).tolist()],
            documents=[content],
            metadatas=[{
                "domain": domain,
                "source_file": "precedent_memory",
                "ticket_id": ticket_id
            }]
        )
    except Exception as e:
        # We don't want precedent memory failures to crash the resolution flow
        print(f"Failed to add precedent to ChromaDB: {e}")

def rewrite_query(query: str, domain: str) -> str:
    """Corrective RAG: Rewrite a query to improve retrieval when initial context is irrelevant."""
    try:
        from app.tools.local_llm import llm_invoke
        prompt = (
            f"You are a retrieval optimization assistant for the {domain} domain.\n"
            f"The following user query failed to retrieve relevant documents from the knowledge base.\n"
            f"Rewrite the query to be more descriptive, extracting key technical terms, and removing conversational noise.\n"
            f"Output ONLY the rewritten query text.\n\n"
            f"Original Query: {query}"
        )
        return llm_invoke(prompt, temperature=0.3).strip()
    except Exception as e:
        print(f"Failed to rewrite query: {e}")
        return query
