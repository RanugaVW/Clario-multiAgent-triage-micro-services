from fastapi.testclient import TestClient

from main import app, store

client = TestClient(app)


def test_post_trace_event_returns_204():
    res = client.post("/trace/event", json={
        "ticket_id": "t1", "service": "ai-orchestrator-service",
        "step": "cache_check", "status": "finished", "detail": {"cache_hit": False},
    })
    assert res.status_code == 204


def test_get_trace_tickets_reflects_posted_events():
    client.post("/trace/event", json={
        "ticket_id": "t2", "service": "ai-orchestrator-service",
        "step": "surrogate", "status": "started", "detail": {},
    })
    tickets = {t["ticket_id"]: t for t in client.get("/trace/tickets").json()}
    assert tickets["t2"]["latest_step"] == "surrogate"
    assert tickets["t2"]["latest_status"] == "started"


def test_post_trace_event_missing_required_field_is_a_422():
    res = client.post("/trace/event", json={"service": "x", "step": "y", "status": "z"})
    assert res.status_code == 422


def test_a_persisted_event_carrying_both_ids_merges_the_correlation_timeline():
    correlation_id = "corr-merge-1"
    real_ticket_id = "real-merge-1"

    # Frontend's own "submit" event, keyed by the correlation id (no real
    # ticket_id exists yet).
    client.post("/trace/event", json={
        "ticket_id": correlation_id, "correlation_id": correlation_id,
        "service": "frontend", "step": "submit", "status": "done", "detail": {},
    })
    # ticket-core-service's "persisted" event carries both ids - this is the
    # one place the merge can happen.
    client.post("/trace/event", json={
        "ticket_id": real_ticket_id, "correlation_id": correlation_id,
        "service": "ticket-core-service", "step": "persisted", "status": "done", "detail": {},
    })

    ticket_ids = {t["ticket_id"] for t in client.get("/trace/tickets").json()}
    assert real_ticket_id in ticket_ids
    assert correlation_id not in ticket_ids

    events = store.events_for(real_ticket_id)
    assert [e["step"] for e in events] == ["submit", "persisted"]
