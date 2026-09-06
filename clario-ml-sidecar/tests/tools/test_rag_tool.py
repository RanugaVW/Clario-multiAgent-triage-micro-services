"""retrieve_context() coverage - notably, that it never grounds fresh
generation on precedent_memory (other customers' full ticket text)."""

from unittest.mock import MagicMock, patch

from app.tools.rag_tool import retrieve_context


# Real bug, found live: a customer who only said "this course" got told
# "the AI course did not meet your expectations" - the specialist prompt's
# "answer ONLY from retrieved context" instruction made the LLM copy that
# phrase verbatim from three unrelated customers' precedent tickets that
# all happened to name that course. precedent_memory documents are full
# past-customer narratives, not generic policy - they must never be part
# of the context a fresh draft is grounded on. (cache_check_node.py still
# queries precedent_memory directly and independently for exact-match
# cache-hit reuse, which is precedent_memory's actual intended use.)
def test_retrieve_context_excludes_precedent_memory_from_kb_query() -> None:
    fake_collection = MagicMock()
    fake_collection.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    fake_client = MagicMock()
    fake_client.get_collection.return_value = fake_collection

    with patch("app.tools.rag_tool.chromadb.PersistentClient", return_value=fake_client), \
         patch("app.tools.rag_tool._embedding_model") as mock_model:
        mock_model.return_value.encode.return_value.tolist.return_value = [0.0]
        retrieve_context("I need a refund", "billing")

    where_clause = fake_collection.query.call_args.kwargs["where"]
    assert {"source_file": {"$ne": "precedent_memory"}} in where_clause["$and"]
    assert {"domain": "billing"} in where_clause["$and"]


def test_retrieve_context_filters_out_a_precedent_memory_document_even_if_returned() -> None:
    """Defense in depth: even if the where-clause exclusion were ever
    bypassed, a precedent_memory document must not reach the caller."""
    fake_collection = MagicMock()
    fake_collection.query.return_value = {
        "documents": [["Ticket Issue:\nSome other customer's issue\n\nResolution:\n..."]],
        "metadatas": [[{"source_file": "precedent_memory", "domain": "billing"}]],
        "distances": [[0.1]],
    }
    fake_client = MagicMock()
    fake_client.get_collection.return_value = fake_collection

    with patch("app.tools.rag_tool.chromadb.PersistentClient", return_value=fake_client), \
         patch("app.tools.rag_tool._embedding_model") as mock_model:
        mock_model.return_value.encode.return_value.tolist.return_value = [0.0]
        results = retrieve_context("I need a refund", "billing")

    assert results == []
