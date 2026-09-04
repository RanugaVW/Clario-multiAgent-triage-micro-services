"""Semantic-cache boundary; checks incoming tickets against previously resolved tickets."""

import chromadb
from app.graph.state import TicketState
from app.tools.rag_tool import _chroma_path, _embedding_model, _COLLECTION_NAME, canonicalize_ticket_text

def cache_check_node(state: TicketState) -> TicketState:
    """Embed the raw_text and query ChromaDB for a near-identical resolved ticket."""
    raw_text = state.get("raw_text", "")
    if not raw_text:
        return {**state, "cache_hit": False, "cache_source_ticket_id": None}

    normalized_text = canonicalize_ticket_text(raw_text)

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
        print(f"Cache check failed: {e}")
        
    return {**state, "cache_hit": False, "cache_source_ticket_id": None}
