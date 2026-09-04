"""pipeline_tracer must add zero overhead when disabled (the default) and
never let a relay failure affect the caller - see Global Constraints in
docs/superpowers/plans/2026-09-05-ticket-pipeline-tracer.md."""

import importlib

import pytest


def _reload_tracer(monkeypatch, enabled: str) -> "module":
    monkeypatch.setenv("TICKET_TRACE_ENABLED", enabled)
    from app.tracing import pipeline_tracer
    return importlib.reload(pipeline_tracer)


def test_disabled_by_default_when_env_var_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("TICKET_TRACE_ENABLED", raising=False)
    from app.tracing import pipeline_tracer
    tracer = importlib.reload(pipeline_tracer)
    assert tracer.TRACE_ENABLED is False
    assert tracer._client is None


def test_emit_is_a_true_no_op_when_disabled(monkeypatch) -> None:
    tracer = _reload_tracer(monkeypatch, "false")
    calls = []
    monkeypatch.setattr(tracer.asyncio, "create_task", lambda *a, **k: calls.append(a))
    tracer.emit("t1", "svc", "step", "finished", {"x": 1})
    assert calls == []


def test_emit_fires_a_task_when_enabled(monkeypatch) -> None:
    tracer = _reload_tracer(monkeypatch, "true")
    calls = []
    monkeypatch.setattr(tracer.asyncio, "create_task", lambda coro: calls.append(coro) or coro.close())
    tracer.emit("t1", "svc", "step", "finished", {"x": 1})
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_post_swallows_a_relay_connection_error(monkeypatch) -> None:
    tracer = _reload_tracer(monkeypatch, "true")

    class _BoomClient:
        async def post(self, *a, **k):
            raise ConnectionError("relay is down")

    tracer._client = _BoomClient()
    await tracer._post({"ticket_id": "t1"})  # must not raise


@pytest.mark.asyncio
async def test_trace_node_wraps_an_async_node_with_started_and_finished_events(monkeypatch) -> None:
    tracer = _reload_tracer(monkeypatch, "true")
    seen = []
    monkeypatch.setattr(tracer, "emit", lambda *a, **k: seen.append((a, k)))

    async def fake_node(state):
        return {**state, "category": "Login Issue"}

    wrapped = tracer.trace_node("classification")(fake_node)
    result = await wrapped({"ticket_id": "t1"})

    assert result == {"ticket_id": "t1", "category": "Login Issue"}
    steps = [call[0][2] for call in seen]  # (ticket_id, service, step, status, ...)
    statuses = [call[0][3] for call in seen]
    assert steps == ["classification", "classification"]
    assert statuses == ["started", "finished"]


def test_trace_node_wraps_a_sync_node_without_awaiting_it(monkeypatch) -> None:
    tracer = _reload_tracer(monkeypatch, "true")
    monkeypatch.setattr(tracer, "emit", lambda *a, **k: None)

    def fake_sync_node(state):
        return {**state, "routing_decision": "billing"}

    wrapped = tracer.trace_node("routing")(fake_sync_node)
    result = wrapped({"ticket_id": "t1"})  # not awaited - must work as a plain call

    assert result == {"ticket_id": "t1", "routing_decision": "billing"}


def test_trace_node_is_a_pure_passthrough_when_disabled(monkeypatch) -> None:
    tracer = _reload_tracer(monkeypatch, "false")

    def fake_sync_node(state):
        return {**state, "routing_decision": "billing"}

    wrapped = tracer.trace_node("routing")(fake_sync_node)
    assert wrapped({"ticket_id": "t1"}) == {"ticket_id": "t1", "routing_decision": "billing"}


def test_surrogate_summarizer_shows_pii_types_and_fake_stand_ins_only(monkeypatch) -> None:
    tracer = _reload_tracer(monkeypatch, "true")
    state = {
        "pii_found": [{"type": "person", "start_char": 0, "end_char": 4}],
        "pii_shadow_map": {"Jane Doe": "Deshan Athukorarala"},
    }
    detail = tracer._SUMMARIZERS["surrogate"](state)
    assert detail == {"pii_types": ["person"], "fake_stand_ins": ["Jane Doe"]}
    assert "Deshan Athukorarala" not in str(detail)
