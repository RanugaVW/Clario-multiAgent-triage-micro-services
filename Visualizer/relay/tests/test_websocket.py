import time

from fastapi.testclient import TestClient

from main import app, store

client = TestClient(app)


def test_new_connection_receives_backlog_then_live_events():
    store.add({"ticket_id": "t9", "service": "s", "step": "cache_check",
               "status": "finished", "detail": {}, "timestamp": time.time()})

    with client.websocket_connect("/trace/ws?ticket_id=t9") as ws:
        backlog = ws.receive_json()
        assert backlog["step"] == "cache_check"

        client.post("/trace/event", json={
            "ticket_id": "t9", "service": "s", "step": "surrogate",
            "status": "started", "detail": {},
        })
        live = ws.receive_json()
        assert live["step"] == "surrogate"


def test_connection_for_a_ticket_with_no_events_yet_gets_only_live_events():
    with client.websocket_connect("/trace/ws?ticket_id=empty-ticket") as ws:
        client.post("/trace/event", json={
            "ticket_id": "empty-ticket", "service": "s", "step": "cache_check",
            "status": "started", "detail": {},
        })
        live = ws.receive_json()
        assert live["step"] == "cache_check"


def test_a_client_watching_a_different_ticket_never_receives_this_ticket_s_events():
    with client.websocket_connect("/trace/ws?ticket_id=other-ticket") as ws:
        client.post("/trace/event", json={
            "ticket_id": "not-other-ticket", "service": "s", "step": "cache_check",
            "status": "started", "detail": {},
        })
        client.post("/trace/event", json={
            "ticket_id": "other-ticket", "service": "s", "step": "surrogate",
            "status": "started", "detail": {},
        })
        live = ws.receive_json()
        assert live["step"] == "surrogate"
