import pytest

pytestmark = pytest.mark.skip(reason="The RAG tool has not been implemented.")


def test_rag_tool_returns_relevant_grounded_context() -> None:
    """Retrieved context should include source metadata for the agent response."""
