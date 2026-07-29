import pytest

pytestmark = pytest.mark.skip(reason="The technical agent has not been implemented.")


def test_technical_agent_creates_a_grounded_draft() -> None:
    """Technical replies should use retrieved documentation and cite its basis."""
