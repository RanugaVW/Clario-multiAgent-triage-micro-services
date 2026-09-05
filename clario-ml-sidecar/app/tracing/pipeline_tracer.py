"""Fire-and-forget event emission for the standalone Ticket Pipeline Tracer
(Visualizer/relay/ - a separate, non-production process). Disabled by
default. See docs/superpowers/specs/2026-09-05-ticket-pipeline-tracer-design.md.

Hard constraint: tracing must never slow down or fail real ticket
processing. TRACE_ENABLED is read once at import time, so when disabled no
HTTP client is ever constructed and emit() is a true no-op - not merely
suppressed. Every producer call is fire-and-forget (asyncio.create_task,
never awaited by the caller) and swallows its own errors.
"""

from __future__ import annotations

import asyncio
import inspect
import os
from typing import Callable

import httpx

TRACE_ENABLED = os.environ.get("TICKET_TRACE_ENABLED", "false").lower() == "true"
RELAY_URL = os.environ.get("TICKET_TRACE_RELAY_URL", "http://localhost:8700")
_SERVICE_NAME = "ai-orchestrator-service"

_client: httpx.AsyncClient | None = httpx.AsyncClient(timeout=1.0) if TRACE_ENABLED else None

# The event loop actually running the pipeline, captured via bind_loop() at
# the pipeline's real entry points (app/main.py's background_orchestration,
# app/worker.py's process_queue). LangGraph dispatches sync nodes via
# loop.run_in_executor(None, func, ...), a worker thread with no event loop
# of its own - asyncio.get_running_loop() fails there, so emit() needs this
# reference to reschedule the post back onto the loop that's actually
# running, instead of silently dropping the event.
_loop: asyncio.AbstractEventLoop | None = None

# Keep references to in-flight emit tasks so they aren't garbage collected
# mid-flight (per asyncio.create_task's own documented risk).
_background_tasks: set[asyncio.Task] = set()


def bind_loop() -> None:
    """Call from an async context before any node runs, so emit() can
    reschedule work from a sync node's executor thread (which has no loop
    of its own) back onto the loop actually running the pipeline. Safe to
    call every time (idempotent, cheap) - re-captures on each call so a
    stale loop from a prior process/reload is never used."""
    global _loop
    if not TRACE_ENABLED:
        return
    try:
        _loop = asyncio.get_running_loop()
    except RuntimeError:
        pass


async def _post(payload: dict) -> None:
    if _client is None:
        return
    try:
        await _client.post(f"{RELAY_URL}/trace/event", json=payload)
    except Exception:
        pass  # relay down/slow/unreachable - never allowed to affect the real pipeline


def _track(task: asyncio.Task | None) -> None:
    if task is None:
        return
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def emit(ticket_id: str, service: str, step: str, status: str, detail: dict | None = None) -> None:
    """Fire a trace event and return immediately. True no-op when disabled."""
    if not TRACE_ENABLED:
        return
    payload = {
        "ticket_id": ticket_id, "service": service, "step": step,
        "status": status, "detail": detail or {},
    }
    try:
        # Fast path: already running inside the calling thread's own event
        # loop (the common case for async nodes, and for anything called
        # directly from the async request/worker handlers).
        asyncio.get_running_loop()
        _track(asyncio.create_task(_post(payload)))
    except RuntimeError:
        # No running loop in this thread - this is a sync node executing in
        # LangGraph's executor thread pool. Reschedule onto the loop that's
        # actually running the pipeline, captured earlier via bind_loop().
        if _loop is not None and not _loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(_post(payload), _loop)
            except RuntimeError:
                pass  # loop closed/shutting down between the check and the call - fail silently


def _summarize_cache_check(state: dict) -> dict:
    return {"cache_hit": state.get("cache_hit")}


def _summarize_surrogate(state: dict) -> dict:
    pii_found = state.get("pii_found", [])
    shadow_map = state.get("pii_shadow_map", {})
    return {
        "pii_types": sorted({p["type"] for p in pii_found}),
        "fake_stand_ins": list(shadow_map.keys()),  # keys are the FAKE values; never the real ones
    }


def _summarize_classification(state: dict) -> dict:
    return {
        "category": state.get("category"),
        "priority": state.get("priority"),
        "sentiment": state.get("sentiment"),
        "confidence": state.get("classification_confidence"),
    }


def _summarize_routing(state: dict) -> dict:
    return {"routing_decision": state.get("routing_decision")}


def _agent_summary(state: dict, domain: str) -> dict:
    return {
        "rag_top_score": state.get("rag_top_score", {}).get(domain),
        "low_relevance": state.get("low_relevance_flags", {}).get(domain),
        "reflection_count": state.get("reflection_count", 0),
    }


def _summarize_technical_agent(state: dict) -> dict:
    return _agent_summary(state, "technical")


def _summarize_billing_agent(state: dict) -> dict:
    return _agent_summary(state, "billing")


def _summarize_both_specialists(state: dict) -> dict:
    return {"technical": _agent_summary(state, "technical"), "billing": _agent_summary(state, "billing")}


def _summarize_validation(state: dict) -> dict:
    results = state.get("validation_result", {})
    return {
        "passed": all(r.get("passed", False) for r in results.values()) if results else None,
        "failure_type": state.get("failure_type"),
    }


def _summarize_reflection(state: dict) -> dict:
    return {"attempt": state.get("reflection_count")}


def _summarize_response_judge(state: dict) -> dict:
    evaluations = state.get("judge_evaluations", {})
    return {
        domain: {"groundedness_score": ev.get("groundedness_score"), "overall_score": ev.get("overall_score")}
        for domain, ev in evaluations.items()
    }


def _summarize_escalation(state: dict) -> dict:
    return {
        "escalation_triggered": state.get("escalation_triggered"),
        "escalation_reasons": state.get("escalation_reasons"),
    }


def _summarize_handoff(state: dict) -> dict:
    return {"escalation_triggered": state.get("escalation_triggered"), "failure_type": state.get("failure_type")}


def _summarize_resolve(state: dict) -> dict:
    # resolve_node is where surrogate's fake stand-ins (see _summarize_surrogate)
    # get swapped back for the customer's real values, right before handoff -
    # surfacing the count (never the values themselves, real or fake) is the
    # only visible proof in the trace that the restoration half of the PII
    # round-trip actually ran, not just the masking half.
    shadow_map = state.get("pii_shadow_map") or {}
    return {
        "final_response_present": state.get("final_response") is not None,
        "pii_restored_count": len(shadow_map),
    }


_SUMMARIZERS: dict[str, Callable[[dict], dict]] = {
    "cache_check": _summarize_cache_check,
    "surrogate": _summarize_surrogate,
    "classification": _summarize_classification,
    "routing": _summarize_routing,
    "technical_agent": _summarize_technical_agent,
    "billing_agent": _summarize_billing_agent,
    "both_specialists": _summarize_both_specialists,
    "validation": _summarize_validation,
    "reflection": _summarize_reflection,
    "response_judge": _summarize_response_judge,
    "escalation": _summarize_escalation,
    "handoff": _summarize_handoff,
    "resolve": _summarize_resolve,
}


def trace_node(step_name: str) -> Callable[[Callable], Callable]:
    """Wrap one LangGraph node with started/finished trace events.

    Used only in graph_builder.py, once per registered node - the 13 node
    files themselves are never modified. Preserves the wrapped node's
    original sync-vs-async calling convention exactly, since this codebase
    mixes both (classification_node/validation_node/the specialist agents
    are async; cache_check_node/routing_node/handoff_node/escalation_node/
    analyzer_node/resolve_node are sync) and LangGraph dispatches each
    according to its own signature.
    """
    summarize = _SUMMARIZERS.get(step_name, lambda _state: {})

    def _decorator(node_fn: Callable) -> Callable:
        if not TRACE_ENABLED:
            return node_fn

        if inspect.iscoroutinefunction(node_fn):
            async def _wrapped_async(state: dict) -> dict:
                ticket_id = state.get("ticket_id", "unknown")
                emit(ticket_id, _SERVICE_NAME, step_name, "started")
                result = await node_fn(state)
                try:
                    detail = summarize(result)
                except Exception:
                    detail = {}
                emit(ticket_id, _SERVICE_NAME, step_name, "finished", detail)
                return result
            return _wrapped_async

        def _wrapped_sync(state: dict) -> dict:
            ticket_id = state.get("ticket_id", "unknown")
            emit(ticket_id, _SERVICE_NAME, step_name, "started")
            result = node_fn(state)
            try:
                detail = summarize(result)
            except Exception:
                detail = {}
            emit(ticket_id, _SERVICE_NAME, step_name, "finished", detail)
            return result
        return _wrapped_sync

    return _decorator
