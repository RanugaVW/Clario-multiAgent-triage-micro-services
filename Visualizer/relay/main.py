"""Standalone relay for the Ticket Pipeline Tracer - external to every
production service, never deployed as part of the product. See
docs/superpowers/specs/2026-09-05-ticket-pipeline-tracer-design.md."""

from __future__ import annotations

import time

from fastapi import FastAPI, Response
from pydantic import BaseModel

from store import TraceStore

app = FastAPI(title="Ticket Pipeline Tracer Relay")
store = TraceStore()


class TraceEvent(BaseModel):
    ticket_id: str
    service: str
    step: str
    status: str
    detail: dict = {}
    correlation_id: str | None = None


@app.post("/trace/event", status_code=204)
async def post_trace_event(event: TraceEvent) -> Response:
    payload = event.model_dump()
    payload["timestamp"] = time.time()
    store.add(payload)
    return Response(status_code=204)


@app.get("/trace/tickets")
async def get_trace_tickets() -> list[dict]:
    return store.tickets()
