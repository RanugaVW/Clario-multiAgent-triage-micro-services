import time

from store import TraceStore


def _event(ticket_id="t1", step="cache_check", status="finished"):
    return {"ticket_id": ticket_id, "service": "ai-orchestrator-service",
            "step": step, "status": status, "timestamp": time.time(), "detail": {}}


def test_add_then_events_for_returns_it_in_order():
    store = TraceStore()
    store.add(_event(step="cache_check"))
    store.add(_event(step="surrogate"))
    events = store.events_for("t1")
    assert [e["step"] for e in events] == ["cache_check", "surrogate"]


def test_events_for_unknown_ticket_returns_empty_list():
    store = TraceStore()
    assert store.events_for("nope") == []


def test_tickets_lists_latest_step_and_status_per_ticket():
    store = TraceStore()
    store.add(_event(ticket_id="t1", step="cache_check", status="finished"))
    store.add(_event(ticket_id="t1", step="surrogate", status="started"))
    store.add(_event(ticket_id="t2", step="cache_check", status="finished"))
    tickets = {t["ticket_id"]: t for t in store.tickets()}
    assert tickets["t1"]["latest_step"] == "surrogate"
    assert tickets["t1"]["latest_status"] == "started"
    assert tickets["t2"]["latest_step"] == "cache_check"


def test_caps_at_50_tickets_evicting_the_least_recently_updated():
    store = TraceStore(max_tickets=2)
    store.add(_event(ticket_id="t1"))
    store.add(_event(ticket_id="t2"))
    store.add(_event(ticket_id="t3"))
    ticket_ids = {t["ticket_id"] for t in store.tickets()}
    assert ticket_ids == {"t2", "t3"}
    assert store.events_for("t1") == []


def test_prunes_events_older_than_one_hour():
    store = TraceStore()
    stale = _event(ticket_id="t1", step="cache_check")
    stale["timestamp"] = time.time() - 3700
    store.add(stale)
    store.add(_event(ticket_id="t1", step="surrogate"))
    events = store.events_for("t1")
    assert [e["step"] for e in events] == ["surrogate"]


def test_merge_correlation_prepends_correlation_events_under_the_real_ticket_id():
    store = TraceStore()
    store.add(_event(ticket_id="corr-1", step="submit"))
    store.add(_event(ticket_id="corr-1", step="received"))
    store.add(_event(ticket_id="real-1", step="persisted"))

    store.merge_correlation("corr-1", "real-1")

    events = store.events_for("real-1")
    assert [e["step"] for e in events] == ["submit", "received", "persisted"]
    assert store.events_for("corr-1") == []


def test_merge_correlation_is_a_noop_when_ids_are_already_equal():
    store = TraceStore()
    store.add(_event(ticket_id="t1", step="cache_check"))
    store.merge_correlation("t1", "t1")
    assert [e["step"] for e in store.events_for("t1")] == ["cache_check"]


def test_merge_correlation_is_a_noop_when_nothing_is_filed_under_the_correlation_id():
    store = TraceStore()
    store.add(_event(ticket_id="real-1", step="persisted"))
    store.merge_correlation("corr-does-not-exist", "real-1")
    assert [e["step"] for e in store.events_for("real-1")] == ["persisted"]
