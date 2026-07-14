"""Contract for the ticket state carried between Clario services."""

import json
from pathlib import Path


FIXTURE = Path(__file__).parents[1] / "fixtures" / "sample_tickets.json"
VALID_STATES = {"new", "in_progress", "resolved"}
REQUIRED_FIELDS = {"ticket_id", "state", "subject", "description", "category", "priority"}


def test_sample_tickets_follow_the_ticket_state_contract() -> None:
    tickets = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert tickets
    assert {ticket["ticket_id"] for ticket in tickets} == {
        "TCK-1001", "TCK-1002", "TCK-1003"
    }
    for ticket in tickets:
        assert REQUIRED_FIELDS <= ticket.keys()
        assert ticket["state"] in VALID_STATES
        assert all(isinstance(ticket[field], str) and ticket[field] for field in REQUIRED_FIELDS)
