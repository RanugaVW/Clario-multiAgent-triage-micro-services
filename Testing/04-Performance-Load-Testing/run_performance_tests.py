"""Real performance & load test runner for the Clario system.

Sample-plan equivalent: §3.1.4 Performance Profiling, §3.1.5 Load Testing.

Like Phase 02, this submits real tickets to the REAL, already-running
production stack (Java gateway on :8080, Redis, the sidecar's already-loaded
model, real Gemini API calls, real Supabase) - nothing here is mocked. It
does NOT import app.main or load its own copy of the local model (that
caused a real OOM incident during Phase 02 - see that phase's report); it
either submits over HTTP to the already-running sidecar/gateway, or calls
genuinely lightweight, safe-to-duplicate code directly in-process (Chroma
retrieval uses a small ~80MB CPU sentence-transformer, not the multi-GB
local Gemma model - confirmed safe by reading app/tools/rag_tool.py before
this script was written).

Real LLM ticket submissions this script makes: 6 total (3 sequential in
Stage A, 3 concurrent in Stage B) - deliberately modest given this session's
prior real experience with judge-model free-tier quota exhaustion (see
Phase 02 report §4) and the single shared 6GB-GPU/15GB-RAM machine this
runs on (see Phase 02 report §2). Stage C (Chroma + Supabase query latency)
makes zero LLM calls and is repeated much more densely since it's free and
safe.

Every ticket this script creates - both the Stage A sidecar-direct ones and
the Stage B real-account gateway ones - is deleted again in a `finally`
block, tagged by RUN_ID for the gateway-created ones (which don't accept a
custom subject prefix the way Phase 02's direct-insert tickets did, so
they're identified and cleaned up by exact ticket id instead, collected as
each is created).

Usage (must run with clario-ml-sidecar/ as the working directory, inside
its .venv, so .env loading resolves correctly - identical prerequisite to
Phase 02):

    cd clario-ml-sidecar
    source .venv/bin/activate
    python ../Testing/04-Performance-Load-Testing/run_performance_tests.py
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIDECAR_ROOT = REPO_ROOT / "clario-ml-sidecar"
sys.path.insert(0, str(SIDECAR_ROOT))
os.chdir(SIDECAR_ROOT)  # so .env / CHROMA_PATH resolve the same way they do for the real app

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from supabase import create_client  # noqa: E402

load_dotenv(SIDECAR_ROOT / ".env")  # load_dotenv() alone searches from this file's own path, not cwd
load_dotenv(REPO_ROOT / ".env")  # real account credentials live in the repo-root .env, not the sidecar's

SIDECAR_URL = os.environ.get("SIDECAR_URL", "http://localhost:8600")
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8080")
SUPABASE_URL = os.environ.get("SUPABASE_PROJECT_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_PUBLIC_API", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SECRET_API", "")
supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

from app.tools.rag_tool import _chroma_path, _COLLECTION_NAME, retrieve_context  # noqa: E402
import chromadb  # noqa: E402

RUN_ID = uuid.uuid4().hex[:8]
REPORT_PATH = Path(__file__).resolve().parent / "performance_test_results.json"
POLL_TIMEOUT_S = 180
POLL_INTERVAL_S = 3

REAL_ACCOUNTS = [
    ("admin", os.environ.get("ADMIN_ACCOUNT_EMAIL"), os.environ.get("ADMIN_PASSWORD")),
    ("user_1", os.environ.get("USER_1_EMAIL"), os.environ.get("USER_1_PASSWORD")),
    ("user_2", os.environ.get("USER_2_EMAIL"), os.environ.get("USER_2_PASSWORD")),
]

STAGE_A_TICKETS = [
    ("technical_login", "Hi I'm Warusha, I cannot login to my account. I need this to be fixed immediately because I have a submission to do today"),
    ("billing_payment", "Payment failed but the money was taken from my bank account."),
    ("refund_request", "I need a refund for the AI course, it did not meet my expectations at all."),
]

STAGE_B_TICKETS = [
    "My subscription renewed but I wanted to cancel it before the renewal date, please help.",
    "The app keeps crashing every time I try to upload a screenshot, this is a bug.",
    "I was charged twice for the same course this month, please look into this.",
]

CHROMA_QUERIES = [
    ("technical", "app keeps crashing on startup"),
    ("technical", "cannot reset my password"),
    ("technical", "login page shows a blank screen"),
    ("billing", "refund for a course I did not like"),
    ("billing", "double charge on my card"),
    ("billing", "subscription cancellation request"),
] * 5  # 30 real, varied retrieval calls


def _mem_snapshot() -> dict:
    """Real free/GPU memory readings, shelled out - same tool used to monitor
    the machine throughout this session, not a synthetic number."""
    snap: dict = {}
    try:
        out = subprocess.run(["free", "-m"], capture_output=True, text=True, timeout=5).stdout
        mem_line = [l for l in out.splitlines() if l.startswith("Mem:")][0].split()
        snap["ram_used_mb"] = int(mem_line[2])
        snap["ram_available_mb"] = int(mem_line[6])
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        used, total = [int(x.strip()) for x in out.split(",")]
        snap["gpu_used_mb"] = used
        snap["gpu_total_mb"] = total
    except Exception:
        pass
    return snap


def _percentiles(values: list[float]) -> dict:
    if not values:
        return {}
    s = sorted(values)
    def pct(p: float) -> float:
        idx = min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))
        return s[idx]
    return {
        "min": round(s[0], 1), "p50": round(pct(50), 1), "p95": round(pct(95), 1),
        "max": round(s[-1], 1), "mean": round(statistics.mean(s), 1), "n": len(s),
    }


@dataclass
class TicketTiming:
    label: str
    ticket_id: str
    submit_accept_ms: float
    total_wall_ms: float
    status: str
    processing_time_ms: float | None
    total_llm_calls: int | None
    total_reflection_count: int | None
    error: str | None = None


created_ticket_ids: list[str] = []  # every ticket this script creates, for guaranteed cleanup


def _insert_ticket_direct(scenario_name: str, raw_text: str) -> str:
    row = {
        "user_id": None,
        "subject": f"[PERF-TEST {RUN_ID}] {scenario_name}",
        "raw_text": raw_text,
        "status": "received",
    }
    result = supabase_client.table("tickets").insert(row).execute()
    tid = result.data[0]["id"]
    created_ticket_ids.append(tid)
    return tid


async def _wait_for_terminal(ticket_id: str) -> tuple[str, dict]:
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        ticket_row = supabase_client.table("tickets").select("status,raw_graph_payload").eq("id", ticket_id).execute().data
        status = ticket_row[0]["status"] if ticket_row else None
        if status in {"resolved", "escalated"}:
            resolutions = supabase_client.table("resolutions").select("*").eq("ticket_id", ticket_id).execute().data
            expected = 2 if status == "escalated" else 1
            if len(resolutions) >= expected:
                return status, ticket_row[0].get("raw_graph_payload") or {}
        await asyncio.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"ticket {ticket_id} did not reach a fully-written terminal state within {POLL_TIMEOUT_S}s")


async def stage_a_sequential() -> list[TicketTiming]:
    """§3.1.4 Performance Profiling - one real ticket at a time, straight to
    the already-running sidecar (mirrors Phase 02's proven-safe HTTP design),
    measuring the pipeline's own genuine end-to-end wall-clock time."""
    print("\n=== Stage A: sequential single-request latency (sidecar-direct) ===")
    results = []
    async with httpx.AsyncClient() as client:
        for label, raw_text in STAGE_A_TICKETS:
            ticket_id = _insert_ticket_direct(label, raw_text)
            t0 = time.perf_counter()
            resp = await client.post(f"{SIDECAR_URL}/process_ticket", json={"ticket_id": ticket_id, "raw_text": raw_text}, timeout=30)
            resp.raise_for_status()
            t_accept = (time.perf_counter() - t0) * 1000
            try:
                status, payload = await _wait_for_terminal(ticket_id)
                t_total = (time.perf_counter() - t0) * 1000
                timing = TicketTiming(
                    label=label, ticket_id=ticket_id, submit_accept_ms=round(t_accept, 1),
                    total_wall_ms=round(t_total, 1), status=status,
                    processing_time_ms=payload.get("processing_time_ms"),
                    total_llm_calls=payload.get("llm_call_count"),
                    total_reflection_count=payload.get("reflection_count"),
                )
            except Exception as exc:
                timing = TicketTiming(
                    label=label, ticket_id=ticket_id, submit_accept_ms=round(t_accept, 1),
                    total_wall_ms=-1, status="ERROR", processing_time_ms=None,
                    total_llm_calls=None, total_reflection_count=None, error=str(exc),
                )
            print(f"  {label}: status={timing.status} wall={timing.total_wall_ms}ms pipeline_internal={timing.processing_time_ms}ms llm_calls={timing.total_llm_calls}")
            results.append(timing)
    return results


def _login(email: str, password: str) -> str:
    r = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def _submit_via_gateway(client: httpx.AsyncClient, token: str, raw_text: str, subject_tag: str) -> tuple[str, float]:
    t0 = time.perf_counter()
    resp = await client.post(
        f"{GATEWAY_URL}/api/tickets",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"rawText": raw_text, "subject": subject_tag},
        timeout=30,
    )
    resp.raise_for_status()
    accept_ms = (time.perf_counter() - t0) * 1000
    ticket_id = resp.json()["id"]
    created_ticket_ids.append(ticket_id)
    return ticket_id, accept_ms


async def stage_b_concurrent_load() -> list[TicketTiming]:
    """§3.1.5 Load Testing - a small, deliberately modest concurrent batch
    (3 real accounts, 3 simultaneous submissions) through the REAL
    user-facing path (Java gateway -> Postgres insert -> Redis dispatch).

    app/worker.py's queue consumer is a single sequential BRPOP loop with no
    concurrency of its own (see worker.py) - this stage measures exactly
    that real architectural fact: whether the system queues correctly under
    concurrent submission and what real serialized drain time results,
    rather than assuming (incorrectly) that the pipeline itself parallelizes."""
    print("\n=== Stage B: concurrent load (3 real accounts, real gateway, real worker queue) ===")
    tokens = [(name, _login(email, pw)) for name, email, pw in REAL_ACCOUNTS if email and pw]
    if len(tokens) < len(REAL_ACCOUNTS):
        print(f"  WARNING: only {len(tokens)}/{len(REAL_ACCOUNTS)} real accounts had usable credentials in .env")

    mem_before = _mem_snapshot()
    print(f"  memory before: {mem_before}")

    async with httpx.AsyncClient() as client:
        t_batch_start = time.perf_counter()
        submit_tasks = [
            _submit_via_gateway(client, token, raw_text, f"[PERF-TEST {RUN_ID}] concurrent_{i}")
            for i, ((name, token), raw_text) in enumerate(zip(tokens, STAGE_B_TICKETS))
        ]
        submissions = await asyncio.gather(*submit_tasks, return_exceptions=True)

    results = []
    wait_tasks = []
    for (name, _tok), sub in zip(tokens, submissions):
        if isinstance(sub, Exception):
            results.append(TicketTiming(label=f"concurrent_{name}", ticket_id="", submit_accept_ms=-1,
                                         total_wall_ms=-1, status="SUBMIT_ERROR", processing_time_ms=None,
                                         total_llm_calls=None, total_reflection_count=None, error=str(sub)))
            continue
        ticket_id, accept_ms = sub
        print(f"  {name}: submitted {ticket_id} (gateway accept: {round(accept_ms, 1)}ms)")
        wait_tasks.append((name, ticket_id, accept_ms))

    # Poll all three concurrently too, so the measured drain time reflects
    # real simultaneous waiting, not this script serializing its own polls.
    async def _wait_one(name: str, ticket_id: str, accept_ms: float) -> TicketTiming:
        try:
            status, payload = await _wait_for_terminal(ticket_id)
            total_ms = (time.perf_counter() - t_batch_start) * 1000
            return TicketTiming(
                label=f"concurrent_{name}", ticket_id=ticket_id, submit_accept_ms=round(accept_ms, 1),
                total_wall_ms=round(total_ms, 1), status=status,
                processing_time_ms=payload.get("processing_time_ms"),
                total_llm_calls=payload.get("llm_call_count"),
                total_reflection_count=payload.get("reflection_count"),
            )
        except Exception as exc:
            return TicketTiming(label=f"concurrent_{name}", ticket_id=ticket_id, submit_accept_ms=round(accept_ms, 1),
                                 total_wall_ms=-1, status="ERROR", processing_time_ms=None,
                                 total_llm_calls=None, total_reflection_count=None, error=str(exc))

    results.extend(await asyncio.gather(*[_wait_one(n, t, a) for n, t, a in wait_tasks]))
    batch_total_ms = (time.perf_counter() - t_batch_start) * 1000
    mem_after = _mem_snapshot()
    print(f"  memory after: {mem_after}")
    for r in results:
        print(f"  {r.label}: status={r.status} wall_from_batch_start={r.total_wall_ms}ms pipeline_internal={r.processing_time_ms}ms")
    print(f"  batch total drain time: {round(batch_total_ms, 1)}ms")
    return results, batch_total_ms, mem_before, mem_after


def stage_c_chroma_latency() -> dict:
    """Free, safe, repeatable - a small CPU sentence-transformer + local
    Chroma reads, no LLM calls, no risk to the live GPU-resident model."""
    print("\n=== Stage C1: ChromaDB retrieval latency (30 real queries, no API cost) ===")
    timings_by_domain: dict[str, list[float]] = {"technical": [], "billing": []}
    for domain, query in CHROMA_QUERIES:
        t0 = time.perf_counter()
        retrieve_context(query, domain, k=4)
        timings_by_domain[domain].append((time.perf_counter() - t0) * 1000)
    result = {d: _percentiles(v) for d, v in timings_by_domain.items()}
    print(f"  technical: {result['technical']}")
    print(f"  billing: {result['billing']}")
    return result


def stage_c_supabase_latency() -> dict:
    """Free, safe, repeatable - real read queries against the real
    production table at its real current size."""
    print("\n=== Stage C2: Supabase query latency (20 real reads, no API cost) ===")
    counts = supabase_client.table("tickets").select("id", count="exact").limit(1).execute()
    total_tickets = counts.count
    print(f"  real tickets table size: {total_tickets} rows")

    list_timings, single_timings, joined_timings = [], [], []
    sample_ids = [r["id"] for r in supabase_client.table("tickets").select("id").limit(20).execute().data]

    for _ in range(20):
        t0 = time.perf_counter()
        supabase_client.table("tickets").select("*").order("created_at", desc=True).limit(25).execute()
        list_timings.append((time.perf_counter() - t0) * 1000)

    for tid in sample_ids:
        t0 = time.perf_counter()
        supabase_client.table("tickets").select("*").eq("id", tid).single().execute()
        single_timings.append((time.perf_counter() - t0) * 1000)

    for tid in sample_ids:
        t0 = time.perf_counter()
        supabase_client.table("tickets").select(
            "*, resolutions(*), ticket_classifications(*), customer_feedback(*), users:user_id(email)"
        ).eq("id", tid).execute()
        joined_timings.append((time.perf_counter() - t0) * 1000)

    result = {
        "real_table_size": total_tickets,
        "list_25_rows": _percentiles(list_timings),
        "single_by_id": _percentiles(single_timings),
        "joined_full_detail": _percentiles(joined_timings),
    }
    print(f"  list (25 rows): {result['list_25_rows']}")
    print(f"  single by id: {result['single_by_id']}")
    print(f"  joined full detail (admin console shape): {result['joined_full_detail']}")
    return result


def _cleanup_all() -> None:
    print(f"\n=== Cleanup: deleting {len(created_ticket_ids)} test ticket(s) ===")
    client = chromadb.PersistentClient(path=_chroma_path())
    for tid in created_ticket_ids:
        try:
            supabase_client.table("tickets").delete().eq("id", tid).execute()
        except Exception as e:
            print(f"  WARNING: failed to delete ticket {tid}: {e}")
        try:
            collection = client.get_collection(_COLLECTION_NAME)
            collection.delete(ids=[f"precedent_{tid}"])
        except Exception:
            pass  # no precedent was written for this ticket, or it never resolved
    print("  done.")


async def main() -> None:
    print(f"Performance & Load Test run {RUN_ID} — sidecar={SIDECAR_URL} gateway={GATEWAY_URL}")
    print(f"Baseline memory: {_mem_snapshot()}")

    report: dict = {"run_id": RUN_ID}
    try:
        stage_a = await stage_a_sequential()
        report["stage_a_sequential_latency"] = [vars(t) for t in stage_a]

        stage_b_results, batch_ms, mem_before, mem_after = await stage_b_concurrent_load()
        report["stage_b_concurrent_load"] = {
            "results": [vars(t) for t in stage_b_results],
            "batch_total_drain_ms": round(batch_ms, 1),
            "memory_before": mem_before,
            "memory_after": mem_after,
        }

        report["stage_c_chroma_latency_ms"] = stage_c_chroma_latency()
        report["stage_c_supabase_latency_ms"] = stage_c_supabase_latency()
        report["final_memory"] = _mem_snapshot()

    except Exception:
        report["fatal_error"] = traceback.format_exc()
        print(f"\nFATAL ERROR:\n{report['fatal_error']}")
    finally:
        _cleanup_all()
        REPORT_PATH.write_text(json.dumps(report, indent=2, default=str))
        print(f"\nResults written to {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
