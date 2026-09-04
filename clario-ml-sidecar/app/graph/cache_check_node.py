"""Semantic-cache boundary; checks incoming tickets against previously resolved tickets."""

import chromadb
from app.graph.state import TicketState
from app.tools.circuit_breaker import get_breaker
from app.tools.rag_tool import _chroma_path, _embedding_model, _COLLECTION_NAME, canonicalize_ticket_text

def cache_check_node(state: TicketState) -> TicketState:
    """Embed the raw_text and query ChromaDB for a near-identical resolved ticket."""
    raw_text = state.get("raw_text", "")
    if not raw_text:
        return {**state, "cache_hit": False, "cache_source_ticket_id": None}

    normalized_text = canonicalize_ticket_text(raw_text)

    # Shares the same breaker retrieve_context() (rag_tool.py) reports to -
    # both talk to the same ChromaDB instance. Before this, a sustained
    # Chroma outage never tripped anything on this path (only the bare
    # try/except below caught it), so every single ticket kept paying the
    # real, failing connection-attempt cost forever instead of eventually
    # short-circuiting. Found in Testing/06-Failover-Recovery-Testing
    # (finding B1b).
    breaker = get_breaker("chroma_rag")
    if not breaker.allow_request():
        return {**state, "cache_hit": False, "cache_source_ticket_id": None}

    try:
        client = chromadb.PersistentClient(path=_chroma_path())
        collection = client.get_collection(_COLLECTION_NAME)
        
        embeds = [_embedding_model().encode(normalized_text, normalize_embeddings=True).tolist()]
        
        result = collection.query(
            query_embeddings=embeds,
            n_results=1,
            where={"source_file": "precedent_memory"},
            include=["documents", "metadatas", "distances"],
        )
        
        breaker.record_success()  # the query itself succeeded, whether or not it found a match

        docs = result.get("documents", [[]])[0] or []
        metas = result.get("metadatas", [[]])[0] or []
        dists = result.get("distances", [[]])[0] or []

        if docs and metas and dists:
            # Cosine distance to similarity score
            score = max(0.0, 1.0 - (float(dists[0]) / 2.0))
            score_threshold = 0.92
            if score >= score_threshold:
                # We have a cache hit!
                document = docs[0]
                ticket_id = metas[0].get("ticket_id")
                
                # Extract resolution text from the document (format is "Ticket Issue:\n...\n\nResolution:\n...")
                resolution = ""
                if "Resolution:\n" in document:
                    resolution = document.split("Resolution:\n", 1)[1].strip()
                else:
                    resolution = document
                
                # We mock the routing decision as "technical" to satisfy TypedDict and validation
                return {
                    **state,
                    "cache_hit": True,
                    "cache_source_ticket_id": ticket_id,
                    "routing_decision": "technical",
                    "agent_drafts": {"technical": resolution},
                    "rag_top_score": {"technical": 1.0}
                }
                
    except Exception as e:
        breaker.record_failure()
        print(f"Cache check failed: {e}")

    return {**state, "cache_hit": False, "cache_source_ticket_id": None}
