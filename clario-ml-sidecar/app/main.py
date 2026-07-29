"""Standalone FastAPI interface for the ticket-orchestration graph."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.graph.graph_builder import build_graph
from app.graph.handoff_node import build_handoff_package

logger = logging.getLogger(__name__)
app = FastAPI(title="Clario Agent Orchestration")
graph = build_graph()
_UI = Path(__file__).with_name("static") / "index.html"


class TicketRequest(BaseModel):
    """Inbound ticket payload accepted by the standalone service."""

    ticket_id: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)


@app.get("/health")
async def health() -> dict[str, str]:
    """Report that the standalone orchestration service is ready."""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def ticket_interface() -> FileResponse:
    """Serve the small local testing interface for ticket submission."""
    return FileResponse(_UI)


@app.post("/process_ticket")
async def process_ticket(ticket: TicketRequest) -> dict:
    """Process one ticket and return its final state plus its terminal payload."""
    initial_state = {
        "ticket_id": ticket.ticket_id,
        "raw_text": ticket.raw_text,
        "reflection_count": 0,
        "reflection_critiques": [],
        "reroute_attempted": False,
        "needs_reroute": False,
        "agent_drafts": {},
        "retrieved_context": {},
        "rag_top_score": {},
        "low_relevance_flags": {},
        "validation_result": {},
    }
    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception:
        logger.exception("Ticket orchestration failed; state=%r", initial_state)
        raise HTTPException(status_code=500, detail="Ticket processing failed safely.") from None
    if final_state.get("escalation_triggered"):
        return {"state": final_state, "handoff_package": build_handoff_package(final_state)}
    return {"state": final_state, "final_response": final_state.get("final_response")}
