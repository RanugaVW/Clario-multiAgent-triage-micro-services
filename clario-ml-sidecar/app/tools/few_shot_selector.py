"""Few-Shot Selector - Retrieves ground truth reference resolutions from ChromaDB.

This module queries the 'validation_refs' Chroma collection (built from train/test CSVs)
to find historically similar tickets with high-quality resolutions. These are used as
few-shot examples for the judge LLM to understand expected response patterns.
"""

from __future__ import annotations

import os
import logging
from typing import List, Dict, Optional
from pathlib import Path

import chromadb
from chromadb.errors import NotFoundError
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

_COLLECTION_NAME = "validation_refs"
_EMBEDDER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_EMBEDDER: Optional[SentenceTransformer] = None


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _embedder() -> SentenceTransformer:
    """Lazy-load the sentence transformer embedder."""
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = SentenceTransformer(_EMBEDDER_MODEL)
    return _EMBEDDER


def _chroma_path() -> str:
    """Resolve ChromaDB persistence path."""
    root = Path(__file__).resolve().parents[2]
    configured = Path(os.getenv("CHROMA_PATH", "./vector_store/chroma_data"))
    return str(configured if configured.is_absolute() else root / configured)


def _get_client() -> chromadb.PersistentClient:
    """Get ChromaDB persistent client."""
    return chromadb.PersistentClient(path=_chroma_path())


def _parse_reference_document(doc: str) -> tuple[str, str]:
    """Parse stored document into issue and resolution components.

    Expected format: "Ticket Issue:\n<issue>\n\nResolution:\n<resolution>"
    """
    issue = ""
    resolution = ""

    if "Ticket Issue:" in doc and "Resolution:" in doc:
        parts = doc.split("Resolution:", 1)
        issue_part = parts[0]
        resolution = parts[1].strip() if len(parts) > 1 else ""
        issue = issue_part.replace("Ticket Issue:", "").strip()

    return issue, resolution


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

async def select_few_shots(
    ticket_text: str,
    priority: str,
    domain: str,
    k: int = 3,
    min_similarity: float = 0.3,
) -> List[Dict]:
    """Retrieve top-K similar ground truth resolutions from validation_refs.

    Args:
        ticket_text: The current ticket's issue description (redacted or raw)
        priority: Ticket priority (Urgent, Critical, High, Medium, Low)
        domain: Routing domain ('technical' or 'billing')
        k: Number of references to retrieve
        min_similarity: Minimum similarity threshold (0-1)

    Returns:
        List of reference dicts with issue, resolution, priority, category,
        similarity_score, and ticket_id. Empty list if collection missing or no matches.
    """
    try:
        client = _get_client()

        # Check if collection exists
        try:
            collection = client.get_collection(_COLLECTION_NAME)
        except (ValueError, NotFoundError):
            logger.warning(f"Validation refs collection '{_COLLECTION_NAME}' not found. Run build_validation_index.py first.")
            return []

        # Generate query embedding
        query_embedding = _embedder().encode(ticket_text, normalize_embeddings=True).tolist()

        # Build where filter for domain + priority
        where_filter = {}
        if domain in ("technical", "billing"):
            where_filter["domain"] = domain
        # Optionally filter by priority band (e.g., High+ for Urgent/Critical)
        # where_filter["priority"] = {"$in": [priority, ...]}

        # Query
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"],
        )

        # Parse results
        few_shots = []
        docs = result.get("documents", [[]])[0] or []
        metas = result.get("metadatas", [[]])[0] or []
        dists = result.get("distances", [[]])[0] or []

        for doc, meta, dist in zip(docs, metas, dists):
            # Convert chroma distance to similarity (0-1)
            # Chroma uses cosine distance where 0=identical, 2=opposite
            similarity = max(0.0, 1.0 - float(dist) / 2.0)

            if similarity < min_similarity:
                continue

            issue, resolution = _parse_reference_document(doc)

            few_shots.append({
                "issue": issue,
                "resolution": resolution,
                "priority": meta.get("priority", "Unknown"),
                "category": meta.get("category", "Unknown"),
                "product": meta.get("product", "Unknown"),
                "similarity_score": similarity,
                "ticket_id": meta.get("ticket_id", ""),
                "domain": meta.get("domain", domain),
            })

        logger.info(f"Retrieved {len(few_shots)} few-shot references for priority={priority}, domain={domain}")
        return few_shots

    except Exception as e:
        logger.error(f"Few-shot selection failed: {e}")
        return []


async def select_few_shots_by_category(
    ticket_text: str,
    category: str,
    domain: str,
    k: int = 3,
    min_similarity: float = 0.3,
) -> List[Dict]:
    """Alternative retrieval by category instead of priority."""
    try:
        client = _get_client()
        collection = client.get_collection(_COLLECTION_NAME)

        query_embedding = _embedder().encode(ticket_text, normalize_embeddings=True).tolist()

        where_filter = {"domain": domain} if domain in ("technical", "billing") else {}
        if category:
            where_filter["category"] = category

        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"],
        )

        few_shots = []
        docs = result.get("documents", [[]])[0] or []
        metas = result.get("metadatas", [[]])[0] or []
        dists = result.get("distances", [[]])[0] or []

        for doc, meta, dist in zip(docs, metas, dists):
            similarity = max(0.0, 1.0 - float(dist) / 2.0)
            if similarity < min_similarity:
                continue

            issue, resolution = _parse_reference_document(doc)
            few_shots.append({
                "issue": issue,
                "resolution": resolution,
                "priority": meta.get("priority", "Unknown"),
                "category": meta.get("category", "Unknown"),
                "product": meta.get("product", "Unknown"),
                "similarity_score": similarity,
                "ticket_id": meta.get("ticket_id", ""),
                "domain": meta.get("domain", domain),
            })

        return few_shots

    except (ValueError, NotFoundError):
        return []
    except Exception as e:
        logger.error(f"Few-shot selection by category failed: {e}")
        return []


async def get_validation_collection_stats() -> Dict:
    """Get statistics about the validation_refs collection."""
    try:
        client = _get_client()
        collection = client.get_collection(_COLLECTION_NAME)
        count = collection.count()

        # Sample some metadata to show distribution
        sample = collection.peek(limit=100)
        metas = sample.get("metadatas", []) or []

        priority_dist = {}
        category_dist = {}
        domain_dist = {}

        for meta in metas:
            p = meta.get("priority", "Unknown")
            c = meta.get("category", "Unknown")
            d = meta.get("domain", "Unknown")
            priority_dist[p] = priority_dist.get(p, 0) + 1
            category_dist[c] = category_dist.get(c, 0) + 1
            domain_dist[d] = domain_dist.get(d, 0) + 1

        return {
            "total_documents": count,
            "priority_distribution": priority_dist,
            "category_distribution": category_dist,
            "domain_distribution": domain_dist,
            "collection_name": _COLLECTION_NAME,
        }

    except (ValueError, NotFoundError):
        return {
            "total_documents": 0,
            "error": f"Collection '{_COLLECTION_NAME}' not found",
        }
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        return {"error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# SYNCHRONOUS WRAPPERS
# ──────────────────────────────────────────────────────────────────────────────

def select_few_shots_sync(
    ticket_text: str,
    priority: str,
    domain: str,
    k: int = 3,
    min_similarity: float = 0.3,
) -> List[Dict]:
    """Synchronous wrapper for select_few_shots."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(
        select_few_shots(ticket_text, priority, domain, k, min_similarity)
    )


def select_few_shots_by_category_sync(
    ticket_text: str,
    category: str,
    domain: str,
    k: int = 3,
    min_similarity: float = 0.3,
) -> List[Dict]:
    """Synchronous wrapper for select_few_shots_by_category."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(
        select_few_shots_by_category(ticket_text, category, domain, k, min_similarity)
    )