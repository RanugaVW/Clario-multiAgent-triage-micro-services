import pytest

pytestmark = pytest.mark.skip(reason="The routing node has not been implemented.")


def test_routing_node_selects_the_specialist(ticket_state: dict[str, str]) -> None:
    """A technical ticket should route to the technical specialist."""
