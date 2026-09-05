"""Standalone FastAPI interface for the ticket-orchestration graph."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from app.graph.graph_builder import build_graph
from app.graph.handoff_node import build_handoff_package
from app.tracing import pipeline_tracer

logger = logging.getLogger(__name__)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload heavy ML models in the background to reduce latency on the first request."""
    import threading
    from app.tools.local_llm import _load_model as load_llm
    from app.tools.local_ocr import _load_model_singleton as load_ocr
    from apscheduler.schedulers.background import BackgroundScheduler
    from app.jobs.sync_judge_references import sync_judge_references

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

    # Feeds admin-corrected judge scores back into the judge's reference pool
    # every 24h. Upsert-based, so a duplicate run (e.g. worker.py also holds
    # this lifespan) or a restart mid-cycle is harmless.
    scheduler = BackgroundScheduler()
    scheduler.add_job(sync_judge_references, "interval", hours=24, id="sync_judge_references")
    scheduler.start()

    yield
    scheduler.shutdown(wait=False)

app = FastAPI(title="Clario Agent Orchestration", lifespan=lifespan)

# Defaults to the local dev frontend; override for deployments where the
# frontend is served from somewhere else (e.g. an EC2-hosted demo talking
# back to this service on the developer's machine).
_CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ALLOWED_ORIGINS,
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


def should_cache_precedent(
    cache_hit: bool, groundedness_score: int | None, min_groundedness: int
) -> tuple[bool, str]:
    """Decide whether a resolved ticket's response is safe to store as a
    reusable precedent. Returns (should_cache, reason_if_not).

    Two independent guards, both found live (a customer got an answer
    referencing another customer's assignment deadline that was never
    mentioned in their own ticket):

    1. Never re-store a cache HIT as a new precedent. cache_check_node
       returns the OLD stored document verbatim as final_response; without
       this guard, every reuse re-embeds that same text under a new
       ticket_id, so one leaky precedent compounds every time it's served.
    2. Gate NEW precedents on groundedness_score. response_judge_node
       already runs an independent LLM judge that scores whether the draft
       "references or aligns with retrieved KB context" - a sentence like
       "given your deadline" is by definition not grounded in KB content (a
       generic support article), so a working judge scores it low. This is
       real, independent verification, not the same generation call
       trusting its own output. Fails closed: an unscored response (the
       judge call itself errored) is treated the same as a low-scoring one
       - no confirmed groundedness means no verified safety to cache on.
    """
    if cache_hit:
        return False, "cache_hit"
    if groundedness_score is None or groundedness_score < min_groundedness:
        return False, f"groundedness_score={groundedness_score!r} (need >= {min_groundedness})"
    return True, ""


def get_user_role(user_id: str) -> str:
    """Looks up a user's real role from public.users - the schema stores it
    there (see supabase_schema.sql), not on the Supabase auth user's
    app_metadata, which this schema never populates. A previous check here
    read app_metadata.role, which was always None, so no admin could ever
    force-delete a ticket (found live in Testing/07-API-Testing)."""
    try:
        res = supabase_client.table("users").select("role").eq("id", user_id).single().execute()
        return (res.data or {}).get("role", "user")
    except Exception:
        return "user"

# Track active processing tasks so we can cancel them if the user deletes the ticket
active_tasks = {}
active_tasks_lock = asyncio.Lock()

async def background_orchestration(ticket: TicketRequest, initial_state: dict, start_time: float):
    # Capture the loop actually running this pipeline (both the /process_ticket
    # background-task path and the worker.py path call this function) so
    # emit() can reschedule onto it from a sync node's executor thread
    # (which has no loop of its own) - see pipeline_tracer.bind_loop.
    pipeline_tracer.bind_loop()
    try:
        import time
        from app.tools.redaction_tool import mask_pii
        from app.tools.rag_tool import add_precedent
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
        # The graph (including handoff, if escalation triggered it) has now
        # fully run - this is the point the spec calls "visible to user":
        # the pipeline's own work is done and whatever it produced is about
        # to be persisted/surfaced.
        pipeline_tracer.emit(ticket.ticket_id, "ai-orchestrator-service", "visible_to_user", "done")

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

    is_escalated = bool(final_state.get("escalation_triggered"))
    status = "escalated" if is_escalated else "resolved"
    final_response = final_state.get("final_response")
    handoff = build_handoff_package(final_state) if is_escalated else None

    if not is_escalated and final_response:
        domain = final_state.get("routing_decision") or final_state.get("category") or "technical"
        if domain not in {"technical", "billing"}:
            domain = "technical"
        judge_eval = final_state.get("judge_evaluations", {}).get(domain) or {}
        min_groundedness = int(os.environ.get("PRECEDENT_MIN_GROUNDEDNESS", "4"))
        cache_ok, skip_reason = should_cache_precedent(
            bool(final_state.get("cache_hit")), judge_eval.get("groundedness_score"), min_groundedness
        )
        if not cache_ok:
            logger.info(f"Not caching ticket {ticket.ticket_id}'s response as a precedent - {skip_reason}")
        else:
            try:
                redacted_text = final_state.get("redacted_text") or ticket.raw_text
                if redacted_text == ticket.raw_text:
                    redacted_text, _ = mask_pii(ticket.raw_text)
                # resolve_node restores this customer's real name/email into
                # final_response, but a cache hit reuses the stored precedent
                # verbatim for other, unrelated future customers - so it must
                # never carry any one customer's identity baked in.
                redacted_response, _ = mask_pii(final_response)
                add_precedent(ticket.ticket_id, redacted_text, redacted_response, domain)
            except Exception as embed_err:
                logger.warning(f"Failed to embed precedent for ticket {ticket.ticket_id}: {embed_err}")

    try:
        # cache_check_node short-circuits straight to response_judge on a hit,
        # so classification_node never ran - final_state has no classification
        # fields to insert (they'd all be NULL).
        if not final_state.get("cache_hit"):
            classification_payload = {
                "ticket_id": ticket.ticket_id,
                "category": final_state.get("category"),
                "priority": final_state.get("priority"),
                "sentiment": final_state.get("sentiment"),
                "confidence": final_state.get("classification_confidence"),
                # Was hardcoded to "gemini" regardless of what actually classified
                # the ticket - classify_ticket_local runs the local fine-tuned
                # adapter (source "llama32_lora"), never Gemini directly.
                "source": final_state.get("classification_source"),
            }
            supabase_client.table("ticket_classifications").insert(classification_payload).execute()
        
        agent_drafts = final_state.get("agent_drafts", {})
        rag_scores = final_state.get("rag_top_score", {})
        low_relevance = final_state.get("low_relevance_flags", {})
        retrieved = final_state.get("retrieved_context", {})
        judge_evaluations = final_state.get("judge_evaluations", {})
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
            draft_result = supabase_client.table("ticket_drafts").insert(draft_payload).execute()

            judge_eval = judge_evaluations.get(domain)
            if judge_eval and draft_result.data:
                try:
                    eval_payload = {
                        "ticket_id": ticket.ticket_id,
                        "draft_id": draft_result.data[0].get("id"),
                        "domain": domain,
                        "judge_model": judge_eval.get("judge_model"),
                        "overall_score": judge_eval.get("overall_score"),
                        "priority_tone_match_score": judge_eval.get("priority_tone_match_score"),
                        "completeness_score": judge_eval.get("completeness_score"),
                        "accuracy_score": judge_eval.get("accuracy_score"),
                        "policy_compliance_score": judge_eval.get("policy_compliance_score"),
                        "groundedness_score": judge_eval.get("groundedness_score"),
                        "judge_reasoning": judge_eval.get("reasoning"),
                        "improvement_suggestions": judge_eval.get("improvement_suggestions"),
                        "required_phrases_present": judge_eval.get("required_phrases_present"),
                        "required_phrases_missing": judge_eval.get("required_phrases_missing"),
                        "forbidden_phrases_found": judge_eval.get("forbidden_phrases_found"),
                        "priority_at_evaluation": final_state.get("priority"),
                        "category_at_evaluation": final_state.get("category"),
                        "evaluation_latency_ms": judge_eval.get("evaluation_latency_ms"),
                    }
                    supabase_client.table("response_evaluations").insert(eval_payload).execute()
                except Exception as e:
                    logger.warning(f"Failed to save response evaluation for ticket {ticket.ticket_id} domain {domain}: {e}")
        
        if not is_escalated and final_response:
            resolution_payload = {
                "ticket_id": ticket.ticket_id,
                "final_response": final_response,
                "escalated": False,
                "total_reflection_count": final_state.get("reflection_count", 0),
                "total_llm_calls": final_state.get("llm_call_count", 0),
            }
            supabase_client.table("resolutions").insert(resolution_payload).execute()
        elif final_response:
            resolution_payload = {
                "ticket_id": ticket.ticket_id,
                "final_response": final_response,
                "escalated": True,
                "total_reflection_count": final_state.get("reflection_count", 0),
                "total_llm_calls": final_state.get("llm_call_count", 0),
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
                "total_llm_calls": final_state.get("llm_call_count", 0),
            }).execute()

        # Flip the ticket's status LAST, only after every supporting row
        # above has been written successfully. Writing this first (as it
        # used to) meant a failure on any later insert left the ticket
        # marked "resolved"/"escalated" with some or all of its supporting
        # data missing - a real failure mode found and reproduced in
        # Testing/06-Failover-Recovery-Testing (finding C1). If anything
        # above raises, this line never runs and the ticket simply stays in
        # its prior status instead of silently lying about being done.
        supabase_client.table("tickets").update({
            "status": status,
            "raw_graph_payload": final_state
        }).eq("id", ticket.ticket_id).execute()

    except Exception as e:
        logger.error(f"Failed to save to Supabase for ticket {ticket.ticket_id}: {e}")

@app.post("/process_ticket")
async def process_ticket(ticket: TicketRequest, background_tasks: BackgroundTasks, user = Depends(verify_token)) -> dict:
    """Trigger background ticket processing and return immediately."""
    import time
    start_time = time.time()

    # Had no auth at all - anyone who could reach this port could trigger a
    # full LLM pipeline run against any ticket_id for free (found live in
    # Testing/07-API-Testing). The real submission path (ticket-core-service
    # dispatching to Redis, consumed by worker.py) never calls this HTTP
    # route, so ownership can only be checked against whatever ticket row
    # already exists for this ticket_id.
    ticket_res = supabase_client.table("tickets").select("user_id").eq("id", ticket.ticket_id).execute()
    if not ticket_res.data or ticket_res.data[0].get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to process this ticket.")

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
        "llm_call_count": 0,
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
        # Check permissions. Used to read auth app_metadata.role, which this
        # schema never populates (role lives in public.users.role) - so
        # force-delete silently never authorized any real admin. Found live
        # in Testing/07-API-Testing.
        is_admin = get_user_role(user.id) == "admin"
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
            # Soft delete from user side by clearing ownership. Used to write
            # a literal all-zero placeholder UUID, but tickets.user_id has a
            # foreign key to public.users(id) with no such row - every
            # non-force delete unconditionally raised a Postgres FK
            # violation (found live in Testing/07-API-Testing, reproduced
            # for every ticket regardless of who owned it). NULL is what
            # this same column's own ON DELETE SET NULL already uses for
            # "owner is gone", and a foreign key always permits NULL.
            supabase_client.table('tickets').update({'user_id': None}).eq('id', ticket_id).execute()
        return {"status": "success", "message": "Ticket deleted and processing stopped."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to delete ticket: {e}')
        raise HTTPException(status_code=500, detail="Failed to delete ticket")

class EmbedResolvedTicketRequest(BaseModel):
    ticket_id: str = Field(min_length=1)
    ticket_text: str = Field(min_length=1, max_length=5000)
    final_response: str = Field(min_length=1, max_length=5000)
    domain: str = Field(min_length=1, max_length=100)

@app.post('/embed_resolved_ticket')
async def embed_resolved_ticket(request: EmbedResolvedTicketRequest, user = Depends(verify_token)):
    """Embeds a resolved ticket into the vector store as precedent memory."""
    # Had no auth at all - anyone who found this URL could inject fabricated
    # "precedent" answers straight into the RAG store, which are later
    # served verbatim to unrelated future customers (found live in
    # Testing/07-API-Testing). Only staff resolve tickets, so this mirrors
    # the same staff-only boundary /api/tickets already enforces.
    if get_user_role(user.id) not in ("admin", "agent"):
        raise HTTPException(status_code=403, detail="Staff access required")
    try:
        from app.tools.redaction_tool import mask_pii
        from app.tools.rag_tool import add_precedent
        
        # We must mask the PII before saving to ChromaDB to prevent leakage.
        # This precedent gets reused verbatim for other, unrelated future
        # customers, so the stored response must never carry this customer's
        # identity either - an admin's manually-typed reply will often
        # address them by name directly.
        redacted_text, _ = mask_pii(request.ticket_text)
        redacted_response, _ = mask_pii(request.final_response)
        add_precedent(request.ticket_id, redacted_text, redacted_response, request.domain)
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to embed resolved ticket: {e}")
        return {"status": "error", "message": str(e)}
