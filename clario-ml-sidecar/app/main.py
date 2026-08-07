"""Standalone FastAPI interface for the ticket-orchestration graph."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from app.graph.graph_builder import build_graph
from app.graph.handoff_node import build_handoff_package

logger = logging.getLogger(__name__)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload heavy ML models in the background to reduce latency on the first request."""
    import threading
    from app.tools.local_llm import _load_model as load_llm
    from app.tools.local_ocr import _load_model_singleton as load_ocr
    
    def preload_models():
        try:
            logger.info("Preloading ML Models at startup...")
            load_llm()
            load_ocr()
            logger.info("ML Models preloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to preload models: {e}")
            
    # Run in background thread so it doesn't block Uvicorn from starting up and binding the port
    threading.Thread(target=preload_models, daemon=True).start()
    
    yield
    # Cleanup on shutdown (if any)
    
app = FastAPI(title="Clario Agent Orchestration", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
graph = build_graph()
_UI = Path(__file__).with_name("static") / "index.html"


class TicketRequest(BaseModel):
    """Inbound ticket payload accepted by the standalone service."""

    ticket_id: str = Field(min_length=1)
    raw_text: str = Field(min_length=1, max_length=5000)
    image_base64: Optional[str] = None


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
import asyncio
from fastapi import Request
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_PROJECT_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_API", "")
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def verify_token(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ")[1]
    try:
        user_resp = supabase_client.auth.get_user(token)
        if not user_resp or not user_resp.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_resp.user
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# Track active processing tasks so we can cancel them if the user deletes the ticket
active_tasks = {}
active_tasks_lock = asyncio.Lock()

async def background_orchestration(ticket: TicketRequest, initial_state: dict, start_time: float):
    try:
        import time
        if ticket.image_base64:
            from app.tools.local_ocr import process_image_async
            ocr_text = await process_image_async(ticket.image_base64)
            # Sync the extracted text back to the database so the Admin can see it
            initial_state["raw_text"] += f"\n\n[OCR EXTRACTED TEXT FROM ATTACHMENT]\n{ocr_text}"
            try:
                supabase_client.table("tickets").update(
                    {"raw_text": initial_state["raw_text"]}
                ).eq("id", ticket.ticket_id).execute()
            except Exception as e:
                logger.error(f"Failed to update ticket {ticket.ticket_id} with OCR text: {e}")
            
        task = asyncio.create_task(graph.ainvoke(initial_state))
        async with active_tasks_lock:
            active_tasks[ticket.ticket_id] = task
        final_state = await task
        
        # Inject processing time into telemetry payload
        final_state["processing_time_ms"] = round((time.time() - start_time) * 1000, 2)
    except asyncio.CancelledError:
        logger.info(f"Ticket {ticket.ticket_id} processing cancelled by user deletion.")
        return
    except Exception as e:
        logger.exception("Ticket orchestration failed; state=%r", initial_state)
        try:
            supabase_client.table("tickets").update({"status": "escalated"}).eq("id", ticket.ticket_id).execute()
        except Exception as update_err:
            logger.warning(f"Failed to update escalated status: {update_err}")
        return
    finally:
        async with active_tasks_lock:
            active_tasks.pop(ticket.ticket_id, None)
        
    is_escalated = True
    status = "escalated"
    final_response = final_state.get("final_response")
    handoff = build_handoff_package(final_state) if is_escalated else None

    try:
        supabase_client.table("tickets").update({
            "status": status,
            "raw_graph_payload": final_state
        }).eq("id", ticket.ticket_id).execute()
        
        classification_payload = {
            "ticket_id": ticket.ticket_id,
            "category": final_state.get("category"),
            "priority": final_state.get("priority"),
            "sentiment": final_state.get("sentiment"),
            "confidence": final_state.get("classification_confidence"),
            "source": "gemini"
        }
        supabase_client.table("ticket_classifications").insert(classification_payload).execute()
        
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
        
        if not is_escalated and final_response:
            resolution_payload = {
                "ticket_id": ticket.ticket_id,
                "final_response": final_response,
                "escalated": False,
                "total_reflection_count": final_state.get("reflection_count", 0),
            }
            supabase_client.table("resolutions").insert(resolution_payload).execute()
        
        if is_escalated:
            escalation_reasons = final_state.get("escalation_reasons", []) or []
            if "Mandatory Human Review" not in escalation_reasons:
                escalation_reasons.append("Mandatory Human Review")
            best_draft = next(iter(agent_drafts.values()), None) if agent_drafts else None
            review_payload = {
                "ticket_id": ticket.ticket_id,
                "original_draft": best_draft,
                "decision": "pending",
                "notes": "Human review required: " + ", ".join(escalation_reasons) if escalation_reasons else "Escalated by system",
            }
            supabase_client.table("human_reviews").insert(review_payload).execute()
            supabase_client.table("resolutions").insert({
                "ticket_id": ticket.ticket_id,
                "final_response": best_draft or "Escalated to human review.",
                "escalated": True,
                "escalation_reasons": escalation_reasons,
                "total_reflection_count": final_state.get("reflection_count", 0),
            }).execute()
            
    except Exception as e:
        logger.error(f"Failed to save to Supabase: {e}")

@app.post("/process_ticket")
async def process_ticket(ticket: TicketRequest, background_tasks: BackgroundTasks) -> dict:
    """Trigger background ticket processing and return immediately."""
    import time
    start_time = time.time()
    
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
    
    # Fire and forget the background orchestration properly
    background_tasks.add_task(background_orchestration, ticket, initial_state, start_time)
    
    return {"status": "processing", "message": "Ticket submitted successfully"}

@app.get('/customer_tickets/{user_id}')
async def get_customer_tickets(user_id: str, user = Depends(verify_token)):
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access these tickets.")
    try:
        res = supabase_client.table('tickets').select('*, resolutions(*)').eq('user_id', user_id).order('created_at', desc=True).execute()
        return res.data
    except Exception as e:
        logger.error(f'Failed to fetch tickets: {e}')
        return []

@app.delete('/customer_tickets/{ticket_id}')
async def delete_customer_ticket(ticket_id: str, force: bool = False, user = Depends(verify_token)):
    try:
        # Check permissions
        is_admin = getattr(user, 'app_metadata', {}).get('role') == 'admin' if hasattr(user, 'app_metadata') else False
        if force and not is_admin:
            raise HTTPException(status_code=403, detail="Only admins can force delete")
            
        if not is_admin:
            ticket_res = supabase_client.table('tickets').select('user_id').eq('id', ticket_id).execute()
            if not ticket_res.data or ticket_res.data[0].get('user_id') != user.id:
                raise HTTPException(status_code=403, detail="Not authorized to delete this ticket")

        # Cancel the task if it's currently running
        async with active_tasks_lock:
            task = active_tasks.get(ticket_id)
        if task:
            task.cancel()
            logger.info(f"Cancelled active task for ticket {ticket_id}")
            
        if force:
            # Hard delete for admins
            supabase_client.table('tickets').delete().eq('id', ticket_id).execute()
        else:
            # Soft delete from user side by replacing the UUID with a zero UUID
            supabase_client.table('tickets').update({'user_id': '00000000-0000-0000-0000-000000000000'}).eq('id', ticket_id).execute()
        return {"status": "success", "message": "Ticket deleted and processing stopped."}
    except Exception as e:
        logger.error(f'Failed to delete ticket: {e}')
        raise HTTPException(status_code=500, detail="Failed to delete ticket")

class EmbedResolvedTicketRequest(BaseModel):
    ticket_id: str = Field(min_length=1)
    ticket_text: str = Field(min_length=1, max_length=5000)
    final_response: str = Field(min_length=1, max_length=5000)
    domain: str = Field(min_length=1, max_length=100)

@app.post('/embed_resolved_ticket')
async def embed_resolved_ticket(request: EmbedResolvedTicketRequest):
    """Embeds a resolved ticket into the vector store as precedent memory."""
    try:
        from app.tools.redaction_tool import mask_pii
        from app.tools.rag_tool import add_precedent
        
        # We must mask the PII before saving to ChromaDB to prevent leakage
        redacted_text, _ = mask_pii(request.ticket_text)
        add_precedent(request.ticket_id, redacted_text, request.final_response, request.domain)
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to embed resolved ticket: {e}")
        return {"status": "error", "message": str(e)}
