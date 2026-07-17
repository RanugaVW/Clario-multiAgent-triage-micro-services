"""Chroma retrieval and relevance evaluation shared by orchestration nodes."""

from __future__ import annotations

import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from app.tools.circuit_breaker import CircuitBreakerOpenError, get_breaker

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_COLLECTION_NAME = "kb_support_docs"
_embedder: SentenceTransformer | None = None


def _chroma_path() -> str:
    configured = Path(os.getenv("CHROMA_PATH", "./vector_store/chroma_data"))
    return str(configured if configured.is_absolute() else _ROOT / configured)


def _embedding_model() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(_MODEL_NAME, local_files_only=True)
    return _embedder


def retrieve_context(query: str, domain: str, k: int = 4) -> list[dict]:
    """Return up to k domain-filtered KB matches with cosine-similarity scores."""
    if domain not in {"technical", "billing"}:
        raise ValueError("domain must be 'technical' or 'billing'")
    breaker = get_breaker("chroma_rag")
    if not breaker.allow_request():
        raise CircuitBreakerOpenError("chroma_rag circuit breaker is open")
    try:
        client = chromadb.PersistentClient(path=_chroma_path())
        try:
            collection = client.get_collection(_COLLECTION_NAME)
        except ValueError:
            breaker.record_success()
            return []
        result = collection.query(
            query_embeddings=[_embedding_model().encode(query).tolist()],
            n_results=k,
            where={"domain": domain},
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        breaker.record_failure()
        raise
    documents = result.get("documents", [[]])[0] or []
    metadata = result.get("metadatas", [[]])[0] or []
    distances = result.get("distances", [[]])[0] or []
    matches = [
        {
            "text": text,
            "source_file": item.get("source_file", "unknown"),
            "score": max(0.0, 1.0 - float(distance)),
        }
        for text, item, distance in zip(documents, metadata, distances)
    ]
    breaker.record_success()
    return matches


def check_relevance(retrieved_context: list[dict], threshold: float | None = None) -> bool:
    """Return whether the top match meets the configured similarity threshold."""
    if not retrieved_context:
        return False
    score_threshold = threshold if threshold is not None else float(os.getenv("RAG_SCORE_THRESHOLD", "0.3"))
    return float(retrieved_context[0].get("score", 0.0)) >= score_threshold
