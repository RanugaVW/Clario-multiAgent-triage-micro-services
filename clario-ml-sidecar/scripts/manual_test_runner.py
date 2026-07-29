"""Send manual fixtures to the local service and print terminal orchestration fields."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

URL = "http://localhost:8600/process_ticket"
FIXTURES = Path(__file__).with_name("manual_test_tickets.json")


def main() -> None:
    """Run each fixture against a locally running FastAPI service."""
    for ticket in json.loads(FIXTURES.read_text(encoding="utf-8")):
        response = httpx.post(URL, json=ticket, timeout=90)
        response.raise_for_status()
        payload = response.json()
        state = payload["state"]
        summary = payload.get("handoff_package", {}).get("reasoning_summary", payload.get("final_response"))
        print(json.dumps({
            "ticket_id": ticket["ticket_id"], "routing_decision": state.get("routing_decision"),
            "failure_type": state.get("failure_type"), "escalation_triggered": state.get("escalation_triggered"),
            "reasoning_summary": summary,
        }, indent=2))


if __name__ == "__main__":
    main()
