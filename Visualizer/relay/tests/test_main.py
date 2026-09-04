from fastapi.testclient import TestClient

from main import app

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
