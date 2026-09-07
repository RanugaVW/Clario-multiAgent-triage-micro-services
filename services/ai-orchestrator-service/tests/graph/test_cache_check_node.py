"""cache_check_node's HR guard - a ticket must never auto-resolve via a
cached precedent when it contains an HR hard-trigger phrase, even at high
similarity to a past resolution."""

from unittest.mock import MagicMock, patch

from app.graph.cache_check_node import cache_check_node


def _mock_high_similarity_hit(resolution_text: str):
    fake_collection = MagicMock()
    fake_collection.query.return_value = {
        "documents": [[f"Ticket Issue:\nSome past issue\n\nResolution:\n{resolution_text}"]],
        "metadatas": [[{"ticket_id": "past-ticket-1", "source_file": "precedent_memory"}]],
        "distances": [[0.05]],  # -> similarity ~0.975, above the 0.92 threshold
    }
    fake_client = MagicMock()
    fake_client.get_collection.return_value = fake_collection
    return fake_client


def test_cache_hit_is_refused_for_an_hr_hard_trigger_ticket_even_at_high_similarity() -> None:
    fake_client = _mock_high_similarity_hit("Please contact support for a refund.")
    with patch("app.graph.cache_check_node.chromadb.PersistentClient", return_value=fake_client), \
         patch("app.graph.cache_check_node._embedding_model") as mock_model:
        mock_model.return_value.encode.return_value.tolist.return_value = [0.0]
        result = cache_check_node({"raw_text": "My son enrolled without parental consent, please refund the payment."})

    assert result["cache_hit"] is False


def test_cache_hit_still_fires_normally_for_a_non_hr_ticket() -> None:
    fake_client = _mock_high_similarity_hit("Your refund has been processed.")
    with patch("app.graph.cache_check_node.chromadb.PersistentClient", return_value=fake_client), \
         patch("app.graph.cache_check_node._embedding_model") as mock_model:
        mock_model.return_value.encode.return_value.tolist.return_value = [0.0]
        result = cache_check_node({"raw_text": "I need a refund for my course, I never used it."})

    assert result["cache_hit"] is True
    assert result["routing_decision"] == "technical"
