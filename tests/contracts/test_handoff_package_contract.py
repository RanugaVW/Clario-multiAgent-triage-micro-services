"""Contract for the package passed from orchestration to a specialist agent."""

import json
from pathlib import Path


FIXTURE = Path(__file__).parents[1] / "fixtures" / "sample_tickets.json"


def make_handoff(ticket: dict[str, str]) -> dict[str, object]:
    """Reference handoff shape; production handoff serialization must preserve it."""
    return {
        "ticket": ticket,
        "routing": {"target_agent": f"{ticket['category']}_agent", "reason": "fixture"},
        "context": [],
    }


def test_handoff_package_contains_ticket_routing_and_context() -> None:
    ticket = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
    handoff = make_handoff(ticket)

    assert set(handoff) == {"ticket", "routing", "context"}
    assert handoff["ticket"]["ticket_id"] == ticket["ticket_id"]
    assert handoff["routing"]["target_agent"] == "technical_agent"
    assert isinstance(handoff["context"], list)
