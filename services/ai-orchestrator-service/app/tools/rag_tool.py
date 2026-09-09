"""Chroma retrieval and relevance evaluation shared by orchestration nodes."""

from __future__ import annotations

import os
<<<<<<< HEAD
import re
=======
>>>>>>> origin/add/voice-to-text-service
from pathlib import Path

import chromadb
from chromadb.errors import NotFoundError
from dotenv import load_dotenv
<<<<<<< HEAD
from sentence_transformers import SentenceTransformer
=======
from google import genai
from google.genai import types
>>>>>>> origin/add/voice-to-text-service

from app.tools.circuit_breaker import CircuitBreakerOpenError, get_breaker

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")
<<<<<<< HEAD
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_COLLECTION_NAME = "kb_support_docs"
_embedder: SentenceTransformer | None = None


_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")
=======
_MODEL_NAME = "gemini-embedding-2"
_COLLECTION_NAME = "kb_support_docs"
_embedder_client: genai.Client | None = None
>>>>>>> origin/add/voice-to-text-service


def _chroma_path() -> str:
    configured = Path(os.getenv("CHROMA_PATH", "./vector_store/chroma_data"))
    return str(configured if configured.is_absolute() else _ROOT / configured)


<<<<<<< HEAD
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
=======
def _embedding_model() -> genai.Client:
    global _embedder_client
    if _embedder_client is None:
        _embedder_client = genai.Client()
    return _embedder_client

def get_embedding(text: str) -> list[float]:
    res = _embedding_model().models.embed_content(
        model=_MODEL_NAME,
        contents=[text],
        config=types.EmbedContentConfig(output_dimensionality=384)
    )
    return res.embeddings[0].values
>>>>>>> origin/add/voice-to-text-service


def retrieve_context(query: str, domain: str, k: int = 4) -> list[dict]:
    """Return up to k domain-filtered KB matches with cosine-similarity scores."""
<<<<<<< HEAD
    if domain not in {"technical", "billing", "hr"}:
        raise ValueError("domain must be 'technical', 'billing', or 'hr'")
=======
    if domain not in {"technical", "billing"}:
        raise ValueError("domain must be 'technical' or 'billing'")
>>>>>>> origin/add/voice-to-text-service
    breaker = get_breaker("chroma_rag")
    if not breaker.allow_request():
        raise CircuitBreakerOpenError("chroma_rag circuit breaker is open")
    try:
        client = chromadb.PersistentClient(path=_chroma_path())
        
        matches = []
<<<<<<< HEAD
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
=======
        embeds = [get_embedding(query)]

        # Query standard support docs
>>>>>>> origin/add/voice-to-text-service
        try:
            collection = client.get_collection(_COLLECTION_NAME)
            result = collection.query(
                query_embeddings=embeds,
                n_results=k,
<<<<<<< HEAD
                where={"$and": [{"domain": domain}, {"source_file": {"$ne": "precedent_memory"}}]},
=======
                where={"domain": domain},
>>>>>>> origin/add/voice-to-text-service
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
<<<<<<< HEAD
    # Defense in depth: the where-clause above should already exclude these,
    # but never let a precedent_memory document (another customer's full
    # ticket narrative) reach a generation prompt even if that filter is
    # ever bypassed.
    matches = [match for match in matches if match["source_file"] != "precedent_memory"]
=======
>>>>>>> origin/add/voice-to-text-service
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
<<<<<<< HEAD
        normalized_text = canonicalize_ticket_text(redacted_text)
=======
>>>>>>> origin/add/voice-to-text-service
        
        # We use a deterministic ID based on the ticket_id
        doc_id = f"precedent_{ticket_id}"
        
        # Insert or update
        collection.upsert(
            ids=[doc_id],
<<<<<<< HEAD
            embeddings=[_embedding_model().encode(normalized_text, normalize_embeddings=True).tolist()],
=======
            embeddings=[get_embedding(redacted_text)],
>>>>>>> origin/add/voice-to-text-service
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
