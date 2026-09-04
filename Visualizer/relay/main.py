"""Standalone relay for the Ticket Pipeline Tracer - external to every
production service, never deployed as part of the product. See
docs/superpowers/specs/2026-09-05-ticket-pipeline-tracer-design.md."""

from __future__ import annotations

import time

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
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


# ticket_id -> set of connected websockets currently watching it
_subscribers: dict[str, set[WebSocket]] = {}


def _broadcast(event: dict) -> None:
    for ws in list(_subscribers.get(event["ticket_id"], ())):
        # Fire-and-forget from a sync context: schedule the send, don't await
        # here - post_trace_event's caller (the real producer service) must
        # never be slowed down by a slow/stuck viewer connection.
        import asyncio
        asyncio.create_task(_safe_send(ws, event))


async def _safe_send(ws: WebSocket, event: dict) -> None:
    try:
        await ws.send_json(event)
    except Exception:
        pass  # a dead/slow viewer connection must never affect ingest


@app.websocket("/trace/ws")
async def trace_ws(websocket: WebSocket, ticket_id: str) -> None:
    await websocket.accept()
    _subscribers.setdefault(ticket_id, set()).add(websocket)
    try:
        for event in store.events_for(ticket_id):
            await websocket.send_json(event)
        while True:
            await websocket.receive_text()  # viewer never sends; just detects disconnect
    except WebSocketDisconnect:
        pass
    finally:
        _subscribers[ticket_id].discard(websocket)


@app.post("/trace/event", status_code=204)
async def post_trace_event(event: TraceEvent) -> Response:
    payload = event.model_dump()
    payload["timestamp"] = time.time()
    store.add(payload)
    _broadcast(payload)
    return Response(status_code=204)


@app.get("/trace/tickets")
async def get_trace_tickets() -> list[dict]:
    return store.tickets()
