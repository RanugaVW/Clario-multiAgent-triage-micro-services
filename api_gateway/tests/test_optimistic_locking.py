import pytest

pytestmark = pytest.mark.skip(reason="Ticket persistence and versioning have not been implemented.")


def test_stale_ticket_update_is_rejected() -> None:
    """A stale version must yield a conflict without overwriting newer data."""
