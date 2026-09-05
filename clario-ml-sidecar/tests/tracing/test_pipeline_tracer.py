"""pipeline_tracer must add zero overhead when disabled (the default) and
never let a relay failure affect the caller - see Global Constraints in
docs/superpowers/plans/2026-09-05-ticket-pipeline-tracer.md."""

import concurrent.futures
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


@pytest.mark.asyncio
async def test_emit_fires_a_task_when_enabled(monkeypatch) -> None:
    # emit() takes the fast path (asyncio.create_task in the calling
    # thread's own loop) when called from an async context that already has
    # a running loop - the common case for async nodes.
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


def test_emit_from_thread_with_no_event_loop_does_not_raise(monkeypatch) -> None:
    """Verify emit() silently handles RuntimeError when called from a thread pool.

    LangGraph runs sync nodes via loop.run_in_executor(), which executes them
    in a worker thread with no running event loop. Calling emit() from such a
    thread would raise RuntimeError on asyncio.create_task() unless we catch it.
    """
    tracer = _reload_tracer(monkeypatch, "true")

    def call_emit_in_thread():
        # This runs in a thread pool with no event loop
        tracer.emit("t1", "svc", "step", "finished", {"x": 1})
        return True

    # Execute emit() in a thread with no event loop - must not raise
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(call_emit_in_thread).result(timeout=5)
        assert result is True


@pytest.mark.asyncio
async def test_bind_loop_captures_the_running_loop() -> None:
    import asyncio as _asyncio

    from app.tracing import pipeline_tracer as tracer

    tracer._loop = None
    tracer.bind_loop()
    assert tracer._loop is _asyncio.get_running_loop()


@pytest.mark.asyncio
async def test_emit_from_a_worker_thread_reaches_the_bound_loop_via_run_coroutine_threadsafe(monkeypatch) -> None:
    """This is the real bug: LangGraph dispatches sync nodes via
    loop.run_in_executor(None, func, ...), a worker thread with no event
    loop of its own. Before the fix, asyncio.get_running_loop() raised
    RuntimeError there and the caught exception silently dropped the event -
    not merely avoided a crash. bind_loop() (called at the pipeline's real
    entry points) plus emit()'s run_coroutine_threadsafe fallback must
    actually deliver the event onto the loop that's running the pipeline.
    """
    tracer = _reload_tracer(monkeypatch, "true")
    posted = []

    async def fake_post(payload):
        posted.append(payload)

    monkeypatch.setattr(tracer, "_post", fake_post)
    tracer.bind_loop()  # capture *this* running loop, as main.py/worker.py do

    def call_emit_in_thread():
        # Runs in a plain worker thread - no event loop here at all.
        tracer.emit("t1", "svc", "cache_check", "finished", {"x": 1})

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(call_emit_in_thread).result(timeout=5)

    # The threadsafe reschedule is itself async - give the loop a tick to
    # actually run the scheduled coroutine.
    for _ in range(20):
        if posted:
            break
        await __import__("asyncio").sleep(0.01)

    assert len(posted) == 1
    assert posted[0]["step"] == "cache_check"


@pytest.mark.asyncio
async def test_sync_node_under_a_real_langgraph_ainvoke_actually_emits_events(monkeypatch) -> None:
    """End-to-end proof for the real bug: build a minimal two-node
    LangGraph (one sync node, one async node - both wrapped via
    trace_node()) and run it through .ainvoke(), the same entry point
    app/main.py's background_orchestration uses for the real graph.
    LangGraph's own runtime, not a hand-rolled executor, is what dispatches
    the sync node into a worker thread - so this proves the real dispatch
    path, not a mocked stand-in for it.
    """
    from langgraph.graph import END, StateGraph
    from typing_extensions import TypedDict

    tracer = _reload_tracer(monkeypatch, "true")
    posted = []

    async def fake_post(payload):
        posted.append(payload)

    monkeypatch.setattr(tracer, "_post", fake_post)
    tracer.bind_loop()  # exactly what main.py/worker.py do before running the graph

    class State(TypedDict):
        ticket_id: str
        touched: list

    def sync_node(state: State) -> State:
        return {**state, "touched": state["touched"] + ["sync"]}

    async def async_node(state: State) -> State:
        return {**state, "touched": state["touched"] + ["async"]}

    graph = StateGraph(State)
    graph.add_node("sync_step", tracer.trace_node("cache_check")(sync_node))
    graph.add_node("async_step", tracer.trace_node("classification")(async_node))
    graph.set_entry_point("sync_step")
    graph.add_edge("sync_step", "async_step")
    graph.add_edge("async_step", END)
    compiled = graph.compile()

    result = await compiled.ainvoke({"ticket_id": "t-e2e", "touched": []})
    assert result["touched"] == ["sync", "async"]

    # Give any cross-thread-rescheduled coroutines a moment to actually run.
    for _ in range(50):
        if len(posted) >= 4:
            break
        await __import__("asyncio").sleep(0.02)

    steps_and_statuses = [(p["step"], p["status"]) for p in posted]
    assert ("cache_check", "started") in steps_and_statuses
    assert ("cache_check", "finished") in steps_and_statuses
    assert ("classification", "started") in steps_and_statuses
    assert ("classification", "finished") in steps_and_statuses
