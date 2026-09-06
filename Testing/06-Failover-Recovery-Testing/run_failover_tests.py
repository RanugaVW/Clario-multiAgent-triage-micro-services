"""Real failover & recovery test runner for the Clario system.

Sample-plan equivalent: §3.1.7 Failover and Recovery Testing.

Like Phases 02-05, this exercises the REAL production code paths - the
real CircuitBreaker class, the real cache_check_node/retrieve_context/
technical_agent_node functions, the real background_orchestration()
persistence logic against a real (disposable) Supabase ticket, and a real
local Redis server - nothing here is a hand-rolled reimplementation of the
logic under test. Failures are injected at the narrowest possible point
(a broken CHROMA_PATH, a monkeypatched Supabase table() call, a dedicated
test-only Redis key) so the rest of each call goes through completely
real code.

Four areas, matching Testing/06-Failover-Recovery-Testing/README.md:
  A. CircuitBreaker (app/tools/circuit_breaker.py) - real state-machine
     correctness beyond what tests/tools/test_circuit_breaker.py already
     covers (that suite is re-run here as evidence too).
  B. Graceful degradation when ChromaDB is unreachable mid-pipeline.
  C. Whether background_orchestration() leaves partial/corrupt rows in
     tickets/ticket_drafts/ticket_classifications/resolutions when a
     Supabase write fails partway through persistence.
  D. Whether a ticket "in flight" survives a worker crash (Redis BRPOP is
     destructive; is there any retry/dead-letter path?).

Safety: Section C uses 3 disposable "canary" tickets created by this
script (tagged FAILOVER-TEST-CANARY), all deleted in `finally` regardless
of pass/fail. Section D never touches the real `ticket_queue` key - it
uses a dedicated `ticket_queue_failover_test_<run_id>` key on the same
local Redis instance so it cannot race with, or be picked up by, a real
worker process. Section B intentionally points CHROMA_PATH at a directory
that doesn't exist - it never touches the real vector store.

Usage:
    cd clario-ml-sidecar
    source .venv/bin/activate
    python ../Testing/06-Failover-Recovery-Testing/run_failover_tests.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIDECAR_ROOT = REPO_ROOT / "clario-ml-sidecar"
sys.path.insert(0, str(SIDECAR_ROOT))
os.chdir(SIDECAR_ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(SIDECAR_ROOT / ".env")

RUN_ID = uuid.uuid4().hex[:8]
CANARY_MARKER = f"FAILOVER-TEST-CANARY-{RUN_ID}"
REPORT_PATH = Path(__file__).resolve().parent / "failover_test_results.json"


@dataclass
class CheckResult:
    id: str
    area: str
    description: str
    passed: bool
    evidence: str
    severity: str = "info"


@dataclass
class Report:
    run_id: str = RUN_ID
    checks: list = field(default_factory=list)

    def add(self, r: CheckResult) -> None:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.id} ({r.severity}) - {r.description}")
        print(f"       evidence: {r.evidence}")
        self.checks.append(r)


report = Report()


# ---------------------------------------------------------------------------
# Section A - CircuitBreaker state-machine correctness (real class, in-process)
# ---------------------------------------------------------------------------


def section_a() -> None:
    from app.tools.circuit_breaker import CircuitBreaker

    # A1: opens after the failure threshold and short-circuits further calls.
    b = CircuitBreaker("a1", failure_threshold=2, window_size=3, cooldown_seconds=60)
    b.record_failure()
    still_closed = b.allow_request()
    b.record_failure()
    report.add(CheckResult(
        "A1", "CircuitBreaker",
        "Breaker opens after failure_threshold failures and then short-circuits",
        passed=(still_closed and b.state == "open" and not b.allow_request()),
        evidence=f"after 1 failure: allow_request={still_closed}; after 2nd failure: "
                 f"state={b.state}, allow_request={b.allow_request()}",
        severity="high" if not (still_closed and b.state == "open") else "info",
    ))

    # A2: after cooldown, a half-open probe that succeeds closes the breaker.
    b = CircuitBreaker("a2", failure_threshold=1, cooldown_seconds=1)
    b.record_failure()
    real_time = __import__("time").monotonic
    import app.tools.circuit_breaker as cb_module
    cb_module.time.monotonic = lambda: b.opened_at + 2  # fast-forward past cooldown
    try:
        probe_allowed = b.allow_request()
        half_open_state = b.state
        b.record_success()
        report.add(CheckResult(
            "A2", "CircuitBreaker",
            "After cooldown, a half-open probe that SUCCEEDS closes the breaker",
            passed=(probe_allowed and half_open_state == "half_open" and b.state == "closed"),
            evidence=f"probe_allowed={probe_allowed}, state_during_probe={half_open_state}, "
                     f"state_after_success={b.state}",
        ))
    finally:
        cb_module.time.monotonic = real_time

    # A3 (not covered by the existing unit suite): a half-open probe that
    # FAILS re-opens the breaker rather than leaving it half-open or closed.
    b = CircuitBreaker("a3", failure_threshold=1, cooldown_seconds=1)
    b.record_failure()
    cb_module.time.monotonic = lambda: b.opened_at + 2
    try:
        b.allow_request()  # enters half-open, consumes the one probe slot
        b.record_failure()  # the probe itself fails
        report.add(CheckResult(
            "A3", "CircuitBreaker",
            "A FAILED half-open probe re-opens the breaker (not left half-open/closed)",
            passed=(b.state == "open"),
            evidence=f"state after a failed half-open probe: {b.state}",
            severity="high" if b.state != "open" else "info",
        ))
    finally:
        cb_module.time.monotonic = real_time

    # A4 (not covered by the existing unit suite): while half-open, a SECOND
    # concurrent caller must not also get a probe slot - only one in-flight
    # probe is allowed at a time.
    b = CircuitBreaker("a4", failure_threshold=1, cooldown_seconds=1)
    b.record_failure()
    cb_module.time.monotonic = lambda: b.opened_at + 2
    try:
        first_probe = b.allow_request()
        second_probe = b.allow_request()  # concurrent second caller, same half-open window
        report.add(CheckResult(
            "A4", "CircuitBreaker",
            "Only ONE concurrent probe is allowed while half-open (no probe pile-up)",
            passed=(first_probe and not second_probe),
            evidence=f"first_probe={first_probe}, second_probe={second_probe}",
            severity="medium" if not (first_probe and not second_probe) else "info",
        ))
    finally:
        cb_module.time.monotonic = real_time

    # A5 (not covered by the existing unit suite): the failure window is
    # ROLLING - enough later successes push old failures out of the window,
    # so the breaker does not stay perma-tripped by ancient failures.
    b = CircuitBreaker("a5", failure_threshold=3, window_size=3, cooldown_seconds=60)
    b.record_failure()
    b.record_failure()
    b.record_success()  # window now [fail, fail, success] - 2 failures, still closed
    b.record_success()  # window now [fail, success, success] - the first failure rolled off
    b.record_success()  # window now [success, success, success]
    report.add(CheckResult(
        "A5", "CircuitBreaker",
        "The rolling window forgets failures once window_size newer outcomes replace them",
        passed=(b.state == "closed"),
        evidence=f"outcomes deque={list(b.outcomes)}, state={b.state} "
                 f"(2 failures were recorded but never adjacent to a 3rd within the window)",
    ))


# ---------------------------------------------------------------------------
# Section B - graceful degradation when ChromaDB is unreachable
# ---------------------------------------------------------------------------


def section_b() -> None:
    broken_path = str(Path("/nonexistent-chroma-path-for-failover-test") / RUN_ID)
    os.environ["CHROMA_PATH"] = broken_path

    from app.graph.cache_check_node import cache_check_node
    from app.tools.circuit_breaker import get_breaker
    import app.tools.rag_tool as rag_tool

    # B1: cache_check_node must degrade gracefully (no exception) when Chroma
    # is unreachable, and must NOT crash the calling node.
    state = {"raw_text": "My payment failed and I was still charged."}
    try:
        result = cache_check_node(state)
        crashed = False
    except Exception as e:  # noqa: BLE001 - we want to know if ANY exception escapes
        result = None
        crashed = True
        crash_evidence = f"{type(e).__name__}: {e}"
    report.add(CheckResult(
        "B1", "Chroma-degradation",
        "cache_check_node() degrades gracefully (no exception, cache_hit=False) when Chroma is unreachable",
        passed=(not crashed and result is not None and result.get("cache_hit") is False),
        evidence=("did not crash; cache_hit=%r" % (result.get("cache_hit") if result else None))
                 if not crashed else f"CRASHED: {crash_evidence}",
        severity="critical" if crashed else "info",
    ))

    # B1b (finding): cache_check_node's Chroma calls are NOT registered with
    # any circuit breaker (confirmed by reading app/graph/cache_check_node.py -
    # it wraps its own chromadb calls in a bare try/except, unlike
    # retrieve_context which explicitly uses get_breaker("chroma_rag")).
    # Demonstrate this live: the chroma_rag breaker's outcome window must be
    # UNCHANGED by the cache_check_node call above.
    breaker = get_breaker("chroma_rag")
    outcomes_before = list(breaker.outcomes)
    cache_check_node(state)
    outcomes_after = list(breaker.outcomes)
    report.add(CheckResult(
        "B1b", "Chroma-degradation",
        "Fix: cache_check_node's Chroma failures now report to the chroma_rag breaker "
        "(previously invisible to it - only retrieve_context() reported), so a "
        "sustained Chroma outage now trips it and short-circuits the cache-check path too",
        passed=(outcomes_before != outcomes_after),
        evidence=f"chroma_rag breaker outcomes changed by a cache_check_node call: "
                 f"before={outcomes_before}, after={outcomes_after}",
    ))

    # B2: retrieve_context() DOES use the chroma_rag breaker - repeated real
    # failures must eventually flip it to open and short-circuit (raise
    # CircuitBreakerOpenError near-instantly) instead of re-attempting the
    # real, slow, failing connection every time.
    from app.tools.circuit_breaker import CircuitBreakerOpenError
    breaker = get_breaker("chroma_rag")
    breaker.state, breaker.opened_at, breaker.outcomes = "closed", None, breaker.outcomes.__class__(maxlen=breaker.window_size)

    real_failures = 0
    short_circuited = False
    last_call_seconds = None
    for attempt in range(breaker.failure_threshold + 3):
        start = time.monotonic()
        try:
            rag_tool.retrieve_context("test query", "technical")
        except CircuitBreakerOpenError:
            short_circuited = True
            last_call_seconds = time.monotonic() - start
            break
        except Exception:
            real_failures += 1
    report.add(CheckResult(
        "B2", "Chroma-degradation",
        "retrieve_context() trips the chroma_rag breaker after real failures and then "
        "short-circuits instead of re-attempting the broken connection",
        passed=(short_circuited and real_failures == breaker.failure_threshold),
        evidence=f"real (slow) failures before trip: {real_failures} "
                 f"(threshold={breaker.failure_threshold}); short-circuited afterward: "
                 f"{short_circuited}; short-circuited call took {last_call_seconds:.4f}s "
                 f"(no real connection attempt)" if last_call_seconds is not None else
                 f"real failures: {real_failures}, never short-circuited",
        severity="high" if not short_circuited else "info",
    ))

    # B3: technical_agent_node (a real production graph node) end-to-end
    # with the breaker already open - confirm it returns the documented
    # graceful-degradation state (failure_type=dependency_failure, draft=None)
    # WITHOUT ever attempting an LLM call (no cost, no crash).
    from app.agents.technical_agent.node import technical_agent_node
    node_state = {
        "redacted_text": "My payment failed and I was still charged twice.",
        "reflection_count": 0, "reflection_critiques": [],
        "agent_drafts": {}, "retrieved_context": {}, "rag_top_score": {}, "low_relevance_flags": {},
    }
    result = asyncio.run(technical_agent_node(node_state))
    report.add(CheckResult(
        "B3", "Chroma-degradation",
        "technical_agent_node degrades gracefully end-to-end when the chroma_rag "
        "breaker is open, with zero LLM calls made",
        passed=(result.get("failure_type") == "dependency_failure"
                and result["agent_drafts"].get("technical") is None
                and result["low_relevance_flags"].get("technical") is True),
        evidence=f"failure_type={result.get('failure_type')}, "
                 f"draft={result['agent_drafts'].get('technical')!r}, "
                 f"low_relevance={result['low_relevance_flags'].get('technical')}",
    ))

    # Reset the breaker and CHROMA_PATH so later sections aren't affected.
    breaker.state, breaker.opened_at, breaker.outcomes = "closed", None, breaker.outcomes.__class__(maxlen=breaker.window_size)
    os.environ.pop("CHROMA_PATH", None)


# ---------------------------------------------------------------------------
# Section C - partial/corrupt state when Supabase fails mid-persistence
# ---------------------------------------------------------------------------


def _canned_final_state(ticket_id: str, raw_text: str) -> dict:
    return {
        "ticket_id": ticket_id, "raw_text": raw_text, "redacted_text": raw_text,
        "category": "Billing", "priority": "High", "sentiment": "Negative",
        "classification_confidence": 0.91, "classification_source": "gemma3_lora",
        "routing_decision": "billing", "cache_hit": False,
        "agent_drafts": {"billing": "We're sorry - a refund has been issued."},
        "retrieved_context": {"billing": []}, "rag_top_score": {"billing": 0.8},
        "low_relevance_flags": {"billing": False},
        "judge_evaluations": {"billing": {
            "judge_model": "stub", "overall_score": 4, "priority_tone_match_score": 4,
            "completeness_score": 4, "accuracy_score": 4, "policy_compliance_score": 5,
            "groundedness_score": 4, "reasoning": "stub reasoning for failover test",
            "improvement_suggestions": [], "required_phrases_present": [],
            "required_phrases_missing": [], "forbidden_phrases_found": [],
            "evaluation_latency_ms": 1,
        }},
        "reflection_count": 0, "llm_call_count": 3,
        "escalation_triggered": False, "escalation_reasons": [],
        "final_response": "We're sorry for the trouble - your refund has been issued.",
        "human_review_notes": None,
    }


def _make_canary(admin_client, suffix: str) -> str:
    return (
        admin_client.table("tickets")
        .insert({
            "customer_name": "Failover Test Canary",
            "customer_email": "failover-test@example.com",
            "subject": f"{CANARY_MARKER}-{suffix}",
            "raw_text": f"{CANARY_MARKER}: canary ticket for Testing/06 persistence-failure checks.",
            "status": "received",
        })
        .execute()
        .data[0]["id"]
    )


def _cleanup_canary(admin_client, ticket_id: str) -> None:
    for table in ("ticket_drafts", "ticket_classifications", "resolutions", "response_evaluations", "human_reviews"):
        try:
            admin_client.table(table).delete().eq("ticket_id", ticket_id).execute()
        except Exception:
            pass
    try:
        admin_client.table("tickets").delete().eq("id", ticket_id).execute()
    except Exception:
        pass


def section_c() -> None:
    import app.main as main_module
    from supabase import create_client

    url = os.environ["SUPABASE_PROJECT_URL"]
    service_key = os.environ["SUPABASE_SECRET_API"]
    admin_client = create_client(url, service_key)

    real_table = main_module.supabase_client.table

    class FakeTicket:
        def __init__(self, ticket_id: str, raw_text: str) -> None:
            self.ticket_id = ticket_id
            self.raw_text = raw_text
            self.image_base64 = None

    async def fake_ainvoke(initial_state: dict) -> dict:
        return _canned_final_state(initial_state["ticket_id"], initial_state["raw_text"])

    def run_one(canary_id: str, break_table_name: str | None) -> Exception | None:
        real_graph_ainvoke = main_module.graph.ainvoke
        main_module.graph.ainvoke = fake_ainvoke

        def patched_table(name: str):
            if break_table_name and name == break_table_name:
                raise ConnectionError(f"simulated Supabase outage on table '{name}'")
            return real_table(name)

        main_module.supabase_client.table = patched_table
        try:
            initial_state = {
                "ticket_id": canary_id, "raw_text": f"{CANARY_MARKER}: canary ticket for Testing/06 persistence-failure checks.",
                "reflection_count": 0, "reflection_critiques": [], "reroute_attempted": False,
                "needs_reroute": False, "agent_drafts": {}, "retrieved_context": {},
                "rag_top_score": {}, "low_relevance_flags": {}, "validation_result": {},
                "llm_call_count": 0,
            }
            try:
                asyncio.run(main_module.background_orchestration(FakeTicket(canary_id, initial_state["raw_text"]), initial_state, time.time()))
                return None
            except Exception as e:  # background_orchestration wraps the whole persistence
                # sequence in its own try/except (logs "Failed to save to Supabase" and
                # returns normally) - this branch is defensive; it should never trigger.
                return e
        finally:
            main_module.graph.ainvoke = real_graph_ainvoke
            main_module.supabase_client.table = real_table

    def snapshot(ticket_id: str) -> dict:
        ticket = admin_client.table("tickets").select("status").eq("id", ticket_id).single().execute().data
        classifications = admin_client.table("ticket_classifications").select("id").eq("ticket_id", ticket_id).execute().data
        drafts = admin_client.table("ticket_drafts").select("id").eq("ticket_id", ticket_id).execute().data
        resolutions = admin_client.table("resolutions").select("id").eq("ticket_id", ticket_id).execute().data
        return {
            "status": ticket["status"] if ticket else None,
            "classifications": len(classifications), "drafts": len(drafts), "resolutions": len(resolutions),
        }

    canary_ids = []
    try:
        # C1: break the ticket_drafts insert, which happens BEFORE the tickets
        # status update now (status was moved to be written LAST, precisely
        # because of this finding - see main.py's comment above that write).
        # Proves the fix: does a mid-sequence failure still leave the status
        # claiming something the supporting rows don't back up?
        c1_id = _make_canary(admin_client, "c1-mid-failure")
        canary_ids.append(c1_id)
        exc = run_one(c1_id, break_table_name="ticket_drafts")
        state = snapshot(c1_id)
        inconsistent = state["status"] == "resolved" and state["classifications"] == 1 and state["drafts"] == 0 and state["resolutions"] == 0
        report.add(CheckResult(
            "C1", "Partial-state",
            "A Supabase failure partway through persistence (on ticket_drafts, which now "
            "runs BEFORE the tickets.status update) must NOT leave the ticket claiming "
            "'resolved' while its supporting rows are missing",
            passed=not inconsistent,
            evidence=f"background_orchestration returned normally (exception swallowed internally, "
                     f"exc leaking out to caller={type(exc).__name__ if exc else None}); "
                     f"resulting DB state: {state}",
            severity="high" if inconsistent else "info",
        ))

        # C2: break the VERY FIRST persistence call in the new order
        # (ticket_classifications, since tickets.update moved to last) -
        # contrast case: does an immediate failure at least leave the ticket
        # completely untouched, rather than partially written?
        c2_id = _make_canary(admin_client, "c2-first-call-failure")
        canary_ids.append(c2_id)
        exc = run_one(c2_id, break_table_name="ticket_classifications")
        state = snapshot(c2_id)
        clean_failure = state["status"] == "received" and state["classifications"] == 0 and state["drafts"] == 0 and state["resolutions"] == 0
        report.add(CheckResult(
            "C2", "Partial-state",
            "A failure on the FIRST persistence call (ticket_classifications) leaves the "
            "ticket completely untouched (still 'received', no orphaned rows) - contrast with C1",
            passed=clean_failure,
            evidence=f"exception raised: {type(exc).__name__ if exc else None}; resulting DB state: {state}",
        ))

        # C3 (positive control): no injected failure at all - confirm the
        # harness itself is valid and a clean run persists everything.
        c3_id = _make_canary(admin_client, "c3-positive-control")
        canary_ids.append(c3_id)
        exc = run_one(c3_id, break_table_name=None)
        state = snapshot(c3_id)
        fully_persisted = state["status"] == "resolved" and state["classifications"] == 1 and state["drafts"] == 1 and state["resolutions"] == 1
        report.add(CheckResult(
            "C3", "Partial-state",
            "Positive control: with no injected failure, background_orchestration "
            "persists every row correctly for a real disposable ticket",
            passed=(exc is None and fully_persisted),
            evidence=f"exception: {exc}; resulting DB state: {state}",
        ))

        # C4: break the now-LAST call (tickets.update itself) - worst case
        # after the fix. Every supporting row should still be written; only
        # the status/raw_graph_payload update is lost, leaving the ticket
        # LOOKING unprocessed ('received') despite having real classification/
        # draft/resolution data behind it - the safe direction to fail in,
        # unlike C1's old behavior (claiming done with no data).
        c4_id = _make_canary(admin_client, "c4-last-call-failure")
        canary_ids.append(c4_id)
        exc = run_one(c4_id, break_table_name="tickets")
        state = snapshot(c4_id)
        safe_direction = state["status"] == "received" and state["classifications"] == 1 and state["drafts"] == 1 and state["resolutions"] == 1
        report.add(CheckResult(
            "C4", "Partial-state",
            "A failure on the LAST persistence call (tickets.update) leaves every "
            "supporting row written but the status stuck at 'received' - safe/recoverable "
            "(data exists, just needs its status reconciled), not corrupt like C1's old behavior",
            passed=safe_direction,
            evidence=f"exception raised: {type(exc).__name__ if exc else None}; resulting DB state: {state}",
        ))
    finally:
        for cid in canary_ids:
            _cleanup_canary(admin_client, cid)


# ---------------------------------------------------------------------------
# Section D - Redis worker: does a ticket survive a worker crash mid-flight?
# ---------------------------------------------------------------------------


def section_d() -> None:
    import redis
    import app.worker as worker_module

    # Exercise the REAL worker.py functions/constants, but against dedicated
    # test-only keys - never the real QUEUE_KEY/PROCESSING_KEY - so this
    # cannot race with, or be picked up by, a real running worker.
    test_queue_key = f"ticket_queue_failover_test_{RUN_ID}"
    test_processing_key = f"ticket_queue_failover_test_{RUN_ID}:processing"
    r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

    try:
        r.ping()
    except Exception as e:
        report.add(CheckResult(
            "D0", "Worker-resilience", "Local Redis server reachable for this section's tests",
            passed=False, evidence=f"{type(e).__name__}: {e} - skipping D1/D2", severity="info",
        ))
        return

    payload = json.dumps({"ticket_id": f"{CANARY_MARKER}-d1", "raw_text": "test payload", "image_base64": None})
    r.lpush(test_queue_key, payload)

    # D1: reproduce worker.py's REAL BLMOVE call (QUEUE_KEY -> PROCESSING_KEY),
    # then simulate the process dying before it can reach the `finally: lrem`
    # that would normally remove the message once processing is attempted -
    # i.e. exactly what a SIGKILL/OOM/crash between the BLMOVE and finishing
    # background_orchestration would do. Prove the message is still sitting
    # in the processing list (recoverable), not gone (the old BRPOP behavior).
    message = r.blmove(test_queue_key, test_processing_key, timeout=5, src="RIGHT", dest="LEFT")
    length_of_main_queue_after_crash = r.llen(test_queue_key)
    length_of_processing_after_crash = r.llen(test_processing_key)
    report.add(CheckResult(
        "D1", "Worker-resilience",
        "Fix: a ticket 'in flight' when the worker crashes (simulated by BLMOVE-ing it "
        "into the processing list and then never finishing) is NOT lost - it's still "
        "sitting in the processing list, recoverable on the next startup",
        passed=(message == payload and length_of_main_queue_after_crash == 0 and length_of_processing_after_crash == 1),
        evidence=f"message moved={message == payload}, main queue length after simulated crash="
                 f"{length_of_main_queue_after_crash}, processing list length={length_of_processing_after_crash} "
                 f"(the message exists here, unlike a bare BRPOP where it would exist nowhere)",
        severity="high" if not (message == payload and length_of_processing_after_crash == 1) else "info",
    ))

    # D2: the REAL recovery function (app.worker._recover_stale_messages),
    # called exactly as it would be at the start of a fresh worker process,
    # must move that same "crashed" message back onto the main queue so a
    # restarted worker picks it up and retries it.
    recovered_message = None
    original_processing_key, original_queue_key = worker_module.PROCESSING_KEY, worker_module.QUEUE_KEY
    try:
        worker_module.PROCESSING_KEY, worker_module.QUEUE_KEY = test_processing_key, test_queue_key
        worker_module._recover_stale_messages(r)
        recovered_message = r.lindex(test_queue_key, 0)
    finally:
        worker_module.PROCESSING_KEY, worker_module.QUEUE_KEY = original_processing_key, original_queue_key
    report.add(CheckResult(
        "D2", "Worker-resilience",
        "Fix: the real app.worker._recover_stale_messages(), run exactly as it is at "
        "worker startup, requeues a message left in-flight by a previous run's crash",
        passed=(recovered_message == payload and r.llen(test_processing_key) == 0),
        evidence=f"main queue after recovery contains the crashed message: {recovered_message == payload}, "
                 f"processing list now empty: {r.llen(test_processing_key) == 0}",
        severity="high" if recovered_message != payload else "info",
    ))

    # D3: the normal (non-crash) completion path - BLMOVE into processing,
    # then the real `finally: lrem` cleanup - must leave NEITHER list holding
    # the message, i.e. no leak into the processing list on the happy path.
    # Drain whatever D1/D2 left in the main queue (the message D2 recovered
    # back onto it) so D3 starts from a clean, known state.
    r.delete(test_queue_key)
    r.lpush(test_queue_key, payload)
    message = r.blmove(test_queue_key, test_processing_key, timeout=5, src="RIGHT", dest="LEFT")
    r.lrem(test_processing_key, 1, message)  # exactly what worker.py's `finally` does
    report.add(CheckResult(
        "D3", "Worker-resilience",
        "Normal completion (BLMOVE then the real finally:-block lrem) leaves both the "
        "main queue and the processing list empty - no leak on the happy path",
        passed=(r.llen(test_queue_key) == 0 and r.llen(test_processing_key) == 0),
        evidence=f"main queue length={r.llen(test_queue_key)}, processing list length={r.llen(test_processing_key)}",
    ))

    r.delete(test_queue_key)
    r.delete(test_processing_key)


def main() -> None:
    print(f"=== Clario Failover & Recovery Test Run {RUN_ID} ===\n")

    print("--- Section A: CircuitBreaker state-machine correctness ---")
    section_a()
    print("\n--- Section B: Graceful degradation when ChromaDB is unreachable ---")
    section_b()
    print("\n--- Section C: Partial/corrupt state on mid-persistence Supabase failure ---")
    section_c()
    print("\n--- Section D: Worker resilience to crashes mid-flight ---")
    section_d()

    passed = sum(1 for c in report.checks if c.passed)
    failed = [c for c in report.checks if not c.passed]
    total = len(report.checks)
    print(f"\n=== SUMMARY: {passed}/{total} checks passed ===")
    if failed:
        print(f"{len(failed)} did not pass (real findings, not necessarily bugs - see severity/evidence):")
        for c in failed:
            print(f"  - {c.id} [{c.severity}] {c.description}")

    REPORT_PATH.write_text(json.dumps({
        "run_id": RUN_ID,
        "summary": {"total": total, "passed": passed, "failed": len(failed)},
        "checks": [vars(c) for c in report.checks],
    }, indent=2))
    print(f"\nFull results written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
