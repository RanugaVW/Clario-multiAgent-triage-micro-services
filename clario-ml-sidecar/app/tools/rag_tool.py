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
        
        matches = []
        embeds = [_embedding_model().encode(query, normalize_embeddings=True).tolist()]

        # Query standard support docs
        try:
            collection = client.get_collection(_COLLECTION_NAME)
            result = collection.query(
                query_embeddings=embeds,
                n_results=k,
                where={"domain": domain},
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
        except ValueError:
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
            except ValueError:
                pass
                
    except Exception:
        breaker.record_failure()
        raise
        
    breaker.record_success()
    # Sort combined matches by score descending and keep top k
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:k]


def check_relevance(retrieved_context: list[dict], threshold: float | None = None) -> bool:
    """Return whether the top match meets the configured similarity threshold."""
    if not retrieved_context:
        return False
    score_threshold = threshold if threshold is not None else float(os.getenv("RAG_SCORE_THRESHOLD", "0.3"))
    return float(retrieved_context[0].get("score", 0.0)) >= score_threshold


def add_precedent(ticket_id: str, redacted_text: str, final_response: str, domain: str) -> None:
    """Embeds a resolved ticket into the vector store for future RAG retrieval."""
    if not redacted_text or not final_response:
        return
        
    try:
        client = chromadb.PersistentClient(path=_chroma_path())
        collection = client.get_or_create_collection(_COLLECTION_NAME)
        
        # Only embed the ticket issue, but keep resolution in the stored document
        content = f"Ticket Issue:\n{redacted_text}\n\nResolution:\n{final_response}"
        
        # We use a deterministic ID based on the ticket_id
        doc_id = f"precedent_{ticket_id}"
        
        # Insert or update
        collection.upsert(
            ids=[doc_id],
            embeddings=[_embedding_model().encode(redacted_text, normalize_embeddings=True).tolist()],
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
