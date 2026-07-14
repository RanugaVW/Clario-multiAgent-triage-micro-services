import pytest

pytestmark = pytest.mark.skip(reason="The validation node has not been implemented.")


def test_validation_node_rejects_invalid_agent_output() -> None:
    """Invalid drafts should return to the agent with validation feedback."""
