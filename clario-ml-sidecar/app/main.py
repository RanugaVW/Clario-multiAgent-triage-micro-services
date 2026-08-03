"""Standalone FastAPI interface for the ticket-orchestration graph."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.graph.graph_builder import build_graph
from app.graph.handoff_node import build_handoff_package

logger = logging.getLogger(__name__)
app = FastAPI(title="Clario Agent Orchestration")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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


from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_PROJECT_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_API", "")
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    except Exception as e:
        logger.exception("Ticket orchestration failed; state=%r", initial_state)
        # Mark as escalated on failure
        try:
            supabase_client.table("tickets").update({"status": "escalated"}).eq("id", ticket.ticket_id).execute()
        except:
            pass
        raise HTTPException(status_code=500, detail="Ticket processing failed safely.") from e
        
    is_escalated = final_state.get("escalation_triggered", False)
    status = "escalated" if is_escalated else "resolved"
    final_response = final_state.get("final_response")
    handoff = build_handoff_package(final_state) if is_escalated else None

    try:
        # Update Ticket Status
        supabase_client.table("tickets").update({"status": status}).eq("id", ticket.ticket_id).execute()
        
        # Save Classifications
        classification_payload = {
            "ticket_id": ticket.ticket_id,
            "category": final_state.get("category"),
            "priority": final_state.get("priority"),
            "sentiment": final_state.get("sentiment"),
            "confidence": final_state.get("classification_confidence"),
            "source": "gemini"
        }
        supabase_client.table("ticket_classifications").insert(classification_payload).execute()
        
        # Save RAG Drafts for each domain processed
        agent_drafts = final_state.get("agent_drafts", {})
        rag_scores = final_state.get("rag_top_score", {})
        low_relevance = final_state.get("low_relevance_flags", {})
        retrieved = final_state.get("retrieved_context", {})
        for domain, draft_text in agent_drafts.items():
            sources = [
                {"text": r.get("text", ""), "source_file": r.get("source_file", ""), "score": r.get("score", 0)}
                for r in retrieved.get(domain, [])
            ]
            draft_payload = {
                "ticket_id": ticket.ticket_id,
                "domain": domain,
                "draft_text": draft_text,
                "rag_top_score": rag_scores.get(domain, 0.0),
                "low_relevance": low_relevance.get(domain, False),
                "retrieved_sources": sources,
                "reflection_attempt": final_state.get("reflection_count", 0),
            }
            supabase_client.table("ticket_drafts").insert(draft_payload).execute()
        
        # Save Resolution if resolved (resolved_by is NULL — no FK issue since column allows NULL)
        if not is_escalated and final_response:
            resolution_payload = {
                "ticket_id": ticket.ticket_id,
                "final_response": final_response,
                "escalated": False,
                "total_reflection_count": final_state.get("reflection_count", 0),
            }
            supabase_client.table("resolutions").insert(resolution_payload).execute()
        
        # Save to human_reviews if escalated
        if is_escalated:
            escalation_reasons = final_state.get("escalation_reasons", [])
            # Pick the best draft we have even if escalated
            best_draft = next(iter(agent_drafts.values()), None) if agent_drafts else None
            review_payload = {
                "ticket_id": ticket.ticket_id,
                "original_draft": best_draft,
                "decision": "pending",
                "notes": "Human review required: " + ", ".join(escalation_reasons) if escalation_reasons else "Escalated by system",
            }
            supabase_client.table("human_reviews").insert(review_payload).execute()
            # Also save as resolution so admin panel can track it
            supabase_client.table("resolutions").insert({
                "ticket_id": ticket.ticket_id,
                "final_response": best_draft or "Escalated to human review.",
                "escalated": True,
                "escalation_reasons": escalation_reasons,
                "total_reflection_count": final_state.get("reflection_count", 0),
            }).execute()
            
    except Exception as e:
        logger.error(f"Failed to save to Supabase: {e}")

    if is_escalated:
        return {"state": final_state, "handoff_package": handoff}
    return {"state": final_state, "final_response": final_response}
