"""Real integration-test runner for the Clario ml-sidecar pipeline.

Runs real tickets through the REAL production Supabase project and the
REAL ChromaDB store on disk, with real (local) draft generation and real
judge LLM calls (Gemini/OpenAI) - nothing here is mocked.

IMPORTANT: this submits over HTTP to the sidecar's ALREADY-RUNNING uvicorn
process (SIDECAR_URL, default http://localhost:8600) rather than importing
app.main and calling background_orchestration in-process. An earlier
version of this script did the in-process call, which loads its own copy
of the local Gemma-3 model - on this machine that model is already loaded
by the live `app.worker` / `uvicorn` processes, and loading a second copy
first OOM'd the GPU and then, when forced onto CPU, OOM'd system RAM badly
enough that the kernel killed an unrelated VS Code process. Submitting
over HTTP reuses the already-loaded model in the live process instead, and
is arguably a more realistic integration test anyway - it's exactly how
the Java gateway talks to this service in production.

The sidecar's own `tickets` table row must exist before submitting (the
sidecar only UPDATEs `tickets`, it never INSERTs one - that normally
happens upstream in the Java gateway), so this script creates it, and
cleans up every row and every Chroma entry it created in a `finally`
block, so nothing is left behind in production.

Every test ticket is tagged `[INTEGRATION-TEST <run_id>]` in its subject
as a secondary, human-visible safety net - cleanup itself is ID-driven,
not text-matching. See cleanup_sweep.py for crash recovery if a run is
killed before its own cleanup executes.

Prerequisite: the sidecar must already be running (this machine already
runs it persistently via `uvicorn app.main:app --port 8600`). Confirm with
`curl http://localhost:8600/health` before running this script.

Usage (must run with clario-ml-sidecar/ as the working directory, inside
its .venv, so .env loading resolves correctly):

    cd clario-ml-sidecar
    source .venv/bin/activate
    python ../Testing/02-Integration-Testing/run_integration_tests.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SIDECAR_ROOT = Path(__file__).resolve().parents[2] / "clario-ml-sidecar"
sys.path.insert(0, str(SIDECAR_ROOT))
os.chdir(SIDECAR_ROOT)  # so .env / CHROMA_PATH resolve the same way they do for the real app

import chromadb  # noqa: E402
import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from supabase import create_client  # noqa: E402

load_dotenv(SIDECAR_ROOT / ".env")  # load_dotenv() alone searches from this file's own path, not cwd

SIDECAR_URL = os.environ.get("SIDECAR_URL", "http://localhost:8600")
SUPABASE_URL = os.environ.get("SUPABASE_PROJECT_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_API", "")
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

from app.tools.rag_tool import _chroma_path, _COLLECTION_NAME  # noqa: E402

RUN_ID = uuid.uuid4().hex[:8]
REPORT_PATH = Path(__file__).resolve().parent / "integration_test_results.json"
POLL_TIMEOUT_S = 180
POLL_INTERVAL_S = 3


@dataclass
class ScenarioResult:
    name: str
    ticket_id: str
    passed: bool = True
    checks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    observed: dict = field(default_factory=dict)
    error: str | None = None


def _check(result: ScenarioResult, description: str, condition: bool) -> None:
    result.checks.append(description)
    if not condition:
        result.passed = False
        result.failures.append(description)


def _insert_ticket(scenario_name: str, raw_text: str) -> str:
    row = {
        "user_id": None,
        "subject": f"[INTEGRATION-TEST {RUN_ID}] {scenario_name}",
        "raw_text": raw_text,
        "status": "received",
    }
    result = supabase_client.table("tickets").insert(row).execute()
    return result.data[0]["id"]


def _cleanup_ticket(ticket_id: str) -> None:
    # ON DELETE CASCADE on ticket_classifications, ticket_drafts, response_evaluations
    # (via ticket_drafts), resolutions, and human_reviews means one delete is enough
    # for the Postgres side.
    supabase_client.table("tickets").delete().eq("id", ticket_id).execute()


def _cleanup_precedent(ticket_id: str) -> None:
    try:
        client = chromadb.PersistentClient(path=_chroma_path())
        collection = client.get_collection(_COLLECTION_NAME)
        collection.delete(ids=[f"precedent_{ticket_id}"])
    except Exception:
        pass  # collection/id may not exist if the ticket never resolved normally


async def _submit_and_wait(ticket_id: str, raw_text: str) -> None:
    """POST to the live sidecar, then poll Supabase until it is FULLY written.

    /process_ticket is fire-and-forget (returns immediately, processes via
    BackgroundTasks), so completion has to be observed through the DB, not
    the HTTP response. background_orchestration() flips `tickets.status` to
    its terminal value BEFORE writing ticket_classifications/ticket_drafts/
    response_evaluations/resolutions (the judge LLM call alone measured
    ~7s in isolation) - polling on status alone races those later writes
    and can read child tables before they exist. `resolutions` is the last
    write in both branches (1 row normally, 2 for an escalation), so that's
    what actually signals "done".
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SIDECAR_URL}/process_ticket",
            json={"ticket_id": ticket_id, "raw_text": raw_text},
            timeout=30,
        )
        resp.raise_for_status()

    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        ticket_row = supabase_client.table("tickets").select("status").eq("id", ticket_id).execute().data
        status = ticket_row[0]["status"] if ticket_row else None
        if status in {"resolved", "escalated"}:
            resolutions = supabase_client.table("resolutions").select("id").eq("ticket_id", ticket_id).execute().data
            expected = 2 if status == "escalated" else 1
            if len(resolutions) >= expected:
                return
        await asyncio.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"ticket {ticket_id} did not reach a fully-written terminal state within {POLL_TIMEOUT_S}s")


async def _run_scenario(name: str, raw_text: str, cleanup: bool = True) -> ScenarioResult:
    """Run one scenario. Pass cleanup=False when a later scenario (e.g. the
    cache-hit resubmission) still needs this ticket's Chroma precedent to
    exist - deleting it here would remove the very data the next scenario
    is testing against."""
    ticket_id = _insert_ticket(name, raw_text)
    result = ScenarioResult(name=name, ticket_id=ticket_id)
    try:
        await _submit_and_wait(ticket_id, raw_text)

        ticket_row = supabase_client.table("tickets").select("*").eq("id", ticket_id).execute().data
        classifications = supabase_client.table("ticket_classifications").select("*").eq("ticket_id", ticket_id).execute().data
        drafts = supabase_client.table("ticket_drafts").select("*").eq("ticket_id", ticket_id).execute().data
        evaluations = supabase_client.table("response_evaluations").select("*").eq("ticket_id", ticket_id).execute().data
        resolutions = supabase_client.table("resolutions").select("*").eq("ticket_id", ticket_id).execute().data
        reviews = supabase_client.table("human_reviews").select("*").eq("ticket_id", ticket_id).execute().data

        result.observed = {
            "ticket_status": ticket_row[0]["status"] if ticket_row else None,
            "classification_count": len(classifications),
            "category": classifications[0].get("category") if classifications else None,
            "confidence": classifications[0].get("confidence") if classifications else None,
            "draft_count": len(drafts),
            "draft_domains": [d.get("domain") for d in drafts],
            "evaluation_count": len(evaluations),
            "resolution_count": len(resolutions),
            "resolution_escalated_flags": [r.get("escalated") for r in resolutions],
            "human_review_count": len(reviews),
        }

        _check(result, "tickets row exists", bool(ticket_row))
        _check(result, "ticket status is resolved or escalated (not stuck at 'received')",
               bool(ticket_row) and ticket_row[0]["status"] in {"resolved", "escalated"})
        _check(result, "exactly one ticket_classifications row was written", len(classifications) == 1)
        _check(result, "resolutions row count is 1 (normal) or 2 (escalated, per the two-insert escalation path)",
               len(resolutions) in {1, 2})
        if ticket_row and ticket_row[0]["status"] == "escalated":
            _check(result, "escalated ticket has a human_reviews row", len(reviews) == 1)
            _check(result, "escalated ticket has 2 resolutions rows (normal-branch insert + escalation-branch insert)",
                   len(resolutions) == 2)
        else:
            _check(result, "resolved ticket has at least one ticket_drafts row", len(drafts) >= 1)
            _check(result, "resolved ticket has at least one response_evaluations row", len(evaluations) >= 1)
            _check(result, "resolved ticket has exactly one resolutions row", len(resolutions) == 1)

    except Exception as exc:  # noqa: BLE001 - report every scenario, never let one crash the run
        result.passed = False
        result.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    finally:
        if cleanup:
            _cleanup_ticket(ticket_id)
            _cleanup_precedent(ticket_id)
    return result


async def _run_cache_hit_scenario(first: ScenarioResult, raw_text: str) -> ScenarioResult:
    """Resubmit the exact same raw_text as `first` and expect a semantic-cache hit.

    background_orchestration persists the whole final state dict verbatim
    into tickets.raw_graph_payload, so that column is read back to check
    cache_hit / cache_source_ticket_id rather than needing a second,
    separate graph invocation.
    """
    name = "cache_hit_resubmission"
    ticket_id = _insert_ticket(name, raw_text)
    result = ScenarioResult(name=name, ticket_id=ticket_id)
    try:
        await _submit_and_wait(ticket_id, raw_text)

        ticket_row = supabase_client.table("tickets").select("*").eq("id", ticket_id).execute().data
        classifications = supabase_client.table("ticket_classifications").select("*").eq("ticket_id", ticket_id).execute().data
        payload = (ticket_row[0].get("raw_graph_payload") or {}) if ticket_row else {}

        result.observed = {
            "cache_hit": payload.get("cache_hit"),
            "cache_source_ticket_id": payload.get("cache_source_ticket_id"),
            "ticket_status": ticket_row[0]["status"] if ticket_row else None,
            "classification_count": len(classifications),
            "classification_category": classifications[0].get("category") if classifications else None,
        }
        _check(result, "second identical ticket registered a semantic cache hit", bool(payload.get("cache_hit")))
        _check(result, "cache hit points back at the first scenario's ticket_id",
               payload.get("cache_source_ticket_id") == first.ticket_id)
        # main.py inserts a ticket_classifications row unconditionally, even
        # though classification_node is skipped on the cache-hit path - the
        # row exists but every field is NULL. Documented, not "fixed" here:
        # see the integration test report for this as a data-quality finding.
        _check(result, "ticket_classifications row written on cache hit is present but empty (category is NULL)",
               len(classifications) == 1 and classifications[0].get("category") is None)
    except Exception as exc:  # noqa: BLE001
        result.passed = False
        result.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    finally:
        _cleanup_ticket(ticket_id)
        _cleanup_precedent(ticket_id)
    return result


async def _check_sidecar_reachable() -> None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{SIDECAR_URL}/health", timeout=5)
            resp.raise_for_status()
    except Exception as exc:
        raise SystemExit(
            f"Sidecar not reachable at {SIDECAR_URL}/health ({exc}). "
            "This script submits to an already-running uvicorn instance - "
            "start it first (or set SIDECAR_URL) before running integration tests."
        ) from exc


async def main() -> None:
    await _check_sidecar_reachable()

    print(f"=== Clario integration test run {RUN_ID} — {datetime.now(timezone.utc).isoformat()} ===")
    print(f"Sidecar: {SIDECAR_URL}")
    print(f"Target Supabase project: {SUPABASE_URL}")
    print(f"Chroma path: {_chroma_path()}\n")

    technical_text = (
        "I keep getting an error when I try to log in - it says my password is "
        "incorrect even though I know it's right. This has been happening for two "
        "days now and I can't access my account at all."
    )
    billing_text = (
        "I was charged twice for my subscription this month and I need a refund "
        "immediately. The billing statement shows two separate payments on the "
        "same day for the same plan."
    )
    ambiguous_text = (
        "My payment failed but money was still taken from my bank account, and "
        "now I can't log in to check my order status. I'm not sure if this is a "
        "billing issue or a login problem."
    )

    results: list[ScenarioResult] = []

    # cleanup=False: the cache-hit scenario below needs this ticket's Chroma
    # precedent to still exist; it (and the ticket row) are cleaned up
    # manually after that scenario runs, not by _run_scenario's own finally.
    technical_result = await _run_scenario("technical_resolved", technical_text, cleanup=False)
    results.append(technical_result)
    print(f"[{technical_result.name}] {'PASS' if technical_result.passed else 'FAIL'} — {technical_result.observed or technical_result.error}")

    billing_result = await _run_scenario("billing_resolved", billing_text)
    results.append(billing_result)
    print(f"[{billing_result.name}] {'PASS' if billing_result.passed else 'FAIL'} — {billing_result.observed or billing_result.error}")

    ambiguous_result = await _run_scenario("ambiguous_dual_domain", ambiguous_text)
    results.append(ambiguous_result)
    print(f"[{ambiguous_result.name}] {'PASS' if ambiguous_result.passed else 'FAIL'} — {ambiguous_result.observed or ambiguous_result.error}")

    try:
        if technical_result.passed and technical_result.observed.get("ticket_status") == "resolved":
            cache_result = await _run_cache_hit_scenario(technical_result, technical_text)
            results.append(cache_result)
            print(f"[{cache_result.name}] {'PASS' if cache_result.passed else 'FAIL'} — {cache_result.observed or cache_result.error}")
        else:
            print("[cache_hit_resubmission] SKIPPED — technical_resolved scenario did not resolve normally, no precedent to hit")
    finally:
        _cleanup_ticket(technical_result.ticket_id)
        _cleanup_precedent(technical_result.ticket_id)

    summary = {
        "run_id": RUN_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "scenarios": [
            {
                "name": r.name,
                "passed": r.passed,
                "checks": r.checks,
                "failures": r.failures,
                "observed": r.observed,
                "error": r.error,
            }
            for r in results
        ],
    }
    REPORT_PATH.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\n=== {summary['passed']}/{summary['total']} scenarios passed ===")
    print(f"JSON results written to {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
