"""Real security & access-control test runner for the Clario system.

Sample-plan equivalent: §3.1.6 Security and Access Control Testing.

Like Phases 02/03/04, this runs against the REAL, already-running stack
(live `next dev` server on :3000, real production Supabase project) - no
mocked network calls, no stubbed auth. Every check below is a real HTTP
request or a real PostgREST query made with real credentials (either a
freshly-issued JWT for a disposable test account, or literally no
credentials at all, to prove what an anonymous caller can and cannot do).

Three areas, matching Testing/05-Security-Access-Control-Testing/README.md:
  A. Supabase Row Level Security - do the deployed policies actually
     confine a customer to their own data, and staff to all of it?
  B. Service-role Next.js API routes - since these routes use the
     Supabase SERVICE ROLE key (which bypasses RLS entirely), ownership
     must be enforced in application code. Is it?
  C. PII redaction boundary - does raw customer text ever reach the judge
     LLM or ChromaDB unredacted? (Backed mostly by the existing
     tests/tools/test_redaction_tool.py + tests/graph/test_response_judge_node.py
     unit suite, which is re-run here as evidence; one live adversarial
     check is added.)

Safety: every write this script performs targets data it created itself
(two disposable customer accounts, one disposable admin account, one
"canary" ticket tagged CANARY_MARKER). It never reads, modifies, or
deletes any real customer's ticket - except for section B1, which must
call the real unauthenticated GET /api/tickets to prove it leaks
production data; that response's contents are inspected in-process only
(counted, checked for known PII field names) and never written to disk or
printed verbatim - only a redacted sample and the total row count are
logged. All disposable accounts/tickets are deleted in a `finally` block
regardless of pass/fail.

Usage:
    cd clario-ml-sidecar
    source .venv/bin/activate
    python ../Testing/05-Security-Access-Control-Testing/run_security_tests.py
"""

from __future__ import annotations

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

import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from supabase import create_client  # noqa: E402

load_dotenv(SIDECAR_ROOT / ".env")
load_dotenv(REPO_ROOT / ".env")

SUPABASE_URL = os.environ["SUPABASE_PROJECT_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_PUBLIC_API"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SECRET_API"]
NEXTJS_URL = os.environ.get("NEXTJS_URL", "http://localhost:3000")

admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

RUN_ID = uuid.uuid4().hex[:8]
CANARY_MARKER = f"SECURITY-TEST-CANARY-{RUN_ID}-do-not-treat-as-real-PII"
TEST_PASSWORD = "ClarioSecTest-Pass-2026!"
REPORT_PATH = Path(__file__).resolve().parent / "security_test_results.json"


@dataclass
class CheckResult:
    id: str
    area: str
    description: str
    passed: bool
    evidence: str
    severity: str = "info"  # info | low | medium | high | critical


@dataclass
class Report:
    run_id: str = RUN_ID
    started_at: float = field(default_factory=time.time)
    checks: list = field(default_factory=list)

    def add(self, r: CheckResult) -> None:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.id} ({r.severity}) - {r.description}")
        print(f"       evidence: {r.evidence}")
        self.checks.append(r)


report = Report()


def sign_in(email: str, password: str):
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.auth.sign_in_with_password({"email": email, "password": password})
    return client


def rest_get(path: str, jwt: str | None) -> requests.Response:
    headers = {"apikey": SUPABASE_ANON_KEY}
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    else:
        headers["Authorization"] = f"Bearer {SUPABASE_ANON_KEY}"  # anonymous role
    return requests.get(f"{SUPABASE_URL}/rest/v1/{path}", headers=headers, timeout=15)


# ---------------------------------------------------------------------------
# Fixture setup: two disposable customers + one disposable admin + one canary
# ticket, all tagged with RUN_ID so cleanup is unambiguous even if this
# script crashes mid-run (idempotent re-run cleans up any prior leftovers).
# ---------------------------------------------------------------------------

CUSTOMER_A_EMAIL = "clario-sectest-customer-a@example.com"
CUSTOMER_B_EMAIL = "clario-sectest-customer-b@example.com"
ADMIN_EMAIL = "clario-sectest-admin@example.com"


def _cleanup_leftover_users() -> None:
    existing = admin_client.auth.admin.list_users()
    for u in existing:
        if u.email in (CUSTOMER_A_EMAIL, CUSTOMER_B_EMAIL, ADMIN_EMAIL):
            admin_client.auth.admin.delete_user(u.id)


def setup_fixtures() -> dict:
    _cleanup_leftover_users()

    a = admin_client.auth.admin.create_user(
        {"email": CUSTOMER_A_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    ).user
    b = admin_client.auth.admin.create_user(
        {"email": CUSTOMER_B_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    ).user
    adm = admin_client.auth.admin.create_user(
        {"email": ADMIN_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    ).user
    admin_client.table("users").update({"role": "admin"}).eq("id", adm.id).execute()

    # Canary ticket owned by customer A - the only ticket this script's
    # unauthenticated write tests (PUT/DELETE) are ever allowed to touch.
    canary = (
        admin_client.table("tickets")
        .insert(
            {
                "user_id": a.id,
                "customer_name": "Security Test Canary",
                "customer_email": CUSTOMER_A_EMAIL,
                "subject": CANARY_MARKER,
                "raw_text": f"{CANARY_MARKER}: this ticket exists only to prove access-control findings and is deleted at the end of this run.",
                "status": "received",
            }
        )
        .execute()
        .data[0]
    )

    return {"a": a, "b": b, "admin": adm, "canary_id": canary["id"]}


def teardown_fixtures(fixtures: dict) -> None:
    # Both canary tickets: since the fix makes B5's unauthenticated DELETE
    # correctly fail, the FIRST canary (used for B1-B5) is no longer deleted
    # by the test itself and must be cleaned up here explicitly, separately
    # from the second canary (used for the B6-B10 positive controls, which
    # legitimately deletes itself via B10 when that check passes).
    for key in ("canary_id", "canary2_id"):
        ticket_id = fixtures.get(key)
        if not ticket_id:
            continue
        try:
            admin_client.table("tickets").delete().eq("id", ticket_id).execute()
        except Exception as e:
            print(f"[cleanup] {key} already gone or failed to delete: {e}")
    for key in ("a", "b", "admin"):
        try:
            admin_client.auth.admin.delete_user(fixtures[key].id)
        except Exception as e:
            print(f"[cleanup] failed to delete {key}: {e}")


# ---------------------------------------------------------------------------
# Section A - Row Level Security, tested behaviorally with real JWTs
# ---------------------------------------------------------------------------


def section_a(fixtures: dict) -> dict:
    a_client = sign_in(CUSTOMER_A_EMAIL, TEST_PASSWORD)
    a_jwt = a_client.auth.get_session().access_token
    b_client = sign_in(CUSTOMER_B_EMAIL, TEST_PASSWORD)
    b_jwt = b_client.auth.get_session().access_token
    admin_jwt = sign_in(ADMIN_EMAIL, TEST_PASSWORD).auth.get_session().access_token

    # A1: customer B's JWT must not be able to SELECT customer A's canary ticket.
    resp = rest_get(f"tickets?id=eq.{fixtures['canary_id']}", b_jwt)
    rows = resp.json() if resp.ok else []
    report.add(CheckResult(
        "A1", "RLS",
        "Customer B cannot SELECT customer A's ticket via PostgREST",
        passed=(resp.status_code == 200 and rows == []),
        evidence=f"HTTP {resp.status_code}, rows returned={len(rows)}",
        severity="critical" if rows else "info",
    ))

    # A2: customer A's own JWT CAN select their own canary ticket (positive control).
    resp = rest_get(f"tickets?id=eq.{fixtures['canary_id']}", a_jwt)
    rows = resp.json() if resp.ok else []
    report.add(CheckResult(
        "A2", "RLS",
        "Customer A CAN select their own ticket (positive control)",
        passed=(resp.status_code == 200 and len(rows) == 1),
        evidence=f"HTTP {resp.status_code}, rows returned={len(rows)}",
    ))

    # A3: an anonymous request (anon key, no user session) must not see any tickets.
    resp = rest_get("tickets?select=id&limit=5", None)
    rows = resp.json() if resp.ok else []
    report.add(CheckResult(
        "A3", "RLS",
        "Anonymous (no session) cannot SELECT any row from tickets",
        passed=(resp.status_code == 200 and rows == []),
        evidence=f"HTTP {resp.status_code}, rows returned={len(rows)}",
        severity="critical" if rows else "info",
    ))

    # A4: staff (admin-role) JWT CAN see the canary ticket even though it
    # isn't theirs - positive control for the staff-visibility policy.
    resp = rest_get(f"tickets?id=eq.{fixtures['canary_id']}", admin_jwt)
    rows = resp.json() if resp.ok else []
    report.add(CheckResult(
        "A4", "RLS",
        "Staff (admin role) CAN select a ticket that isn't theirs (positive control)",
        passed=(resp.status_code == 200 and len(rows) == 1),
        evidence=f"HTTP {resp.status_code}, rows returned={len(rows)}",
    ))

    # A5: customer B cannot read customer A's public.users profile row.
    resp = rest_get(f"users?id=eq.{fixtures['a'].id}", b_jwt)
    rows = resp.json() if resp.ok else []
    report.add(CheckResult(
        "A5", "RLS",
        "Customer B cannot SELECT customer A's public.users row",
        passed=(resp.status_code == 200 and rows == []),
        evidence=f"HTTP {resp.status_code}, rows returned={len(rows)}",
        severity="high" if rows else "info",
    ))

    # A6: customer B cannot INSERT a ticket claiming to be customer A (user_id spoof).
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/tickets",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {b_jwt}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json={
            "user_id": fixtures["a"].id,
            "subject": f"{CANARY_MARKER}-spoof-attempt",
            "raw_text": "attempting to insert a ticket as another user",
        },
        timeout=15,
    )
    report.add(CheckResult(
        "A6", "RLS",
        "Customer B cannot INSERT a ticket with user_id spoofed to customer A",
        passed=(resp.status_code in (401, 403)),
        evidence=f"HTTP {resp.status_code}: {resp.text[:200]}",
        severity="high" if resp.status_code not in (401, 403) else "info",
    ))
    if resp.status_code == 201:
        # Clean up if the spoofed insert somehow succeeded.
        spoofed_id = resp.json()[0]["id"]
        admin_client.table("tickets").delete().eq("id", spoofed_id).execute()

    # A7/A7b/A7c: human_reviews - confirm staff can read it, and that
    # non-staff/anonymous cannot. (A first run of this script found the live
    # database enforces this correctly via a policy that supabase_schema.sql
    # didn't document at the time - that drift was fixed by adding the
    # matching CREATE POLICY to supabase_schema.sql; see A7d.)
    resp = rest_get("human_reviews?select=id&limit=5", admin_jwt)
    staff_rows = resp.json() if resp.ok else []
    report.add(CheckResult(
        "A7", "RLS",
        "Staff (admin role) CAN select from human_reviews (positive control)",
        passed=(resp.status_code == 200 and len(staff_rows) > 0),
        evidence=f"HTTP {resp.status_code}, rows returned={len(staff_rows)}",
    ))

    resp = rest_get("human_reviews?select=id&limit=5", b_jwt)
    rows = resp.json() if resp.ok else []
    report.add(CheckResult(
        "A7b", "RLS",
        "Non-staff (plain customer) JWT cannot select from human_reviews",
        passed=(resp.status_code == 200 and rows == []),
        evidence=f"HTTP {resp.status_code}, rows returned={len(rows)}",
        severity="high" if rows else "info",
    ))

    resp = rest_get("human_reviews?select=id&limit=5", None)
    rows = resp.json() if resp.ok else []
    report.add(CheckResult(
        "A7c", "RLS",
        "Anonymous (no session) cannot select from human_reviews",
        passed=(resp.status_code == 200 and rows == []),
        evidence=f"HTTP {resp.status_code}, rows returned={len(rows)}",
        severity="critical" if rows else "info",
    ))

    import re
    schema_file = REPO_ROOT / "supabase_schema.sql"
    schema_has_policy = bool(re.search(r'CREATE POLICY[^;]*ON public\.human_reviews', schema_file.read_text()))
    report.add(CheckResult(
        "A7d", "schema-drift",
        "supabase_schema.sql documents the human_reviews staff-read policy "
        "(previously: live DB had one, the checked-in schema file didn't)",
        passed=schema_has_policy,
        evidence=f"supabase_schema.sql {'contains' if schema_has_policy else 'is still missing'} "
                 f"a CREATE POLICY for human_reviews near its ENABLE ROW LEVEL SECURITY line",
        severity="low" if not schema_has_policy else "info",
    ))

    return {"a_jwt": a_jwt, "b_jwt": b_jwt, "admin_jwt": admin_jwt}


# ---------------------------------------------------------------------------
# Section B - service-role Next.js API routes (bypass RLS; must self-enforce)
# ---------------------------------------------------------------------------


def section_b(fixtures: dict, jwts: dict) -> None:
    # B1: GET /api/tickets with ZERO auth headers of any kind.
    resp = requests.get(f"{NEXTJS_URL}/api/tickets", timeout=30)
    data = resp.json().get("data", []) if resp.ok else []
    canary_present = any(t.get("id") == fixtures["canary_id"] for t in data)
    has_raw_text_field = any("raw_text" in t for t in data)
    has_email_field = any("customer_email" in t for t in data)
    report.add(CheckResult(
        "B1", "API-authz",
        "GET /api/tickets with no Authorization header at all",
        passed=not (resp.status_code == 200 and canary_present),
        evidence=(
            f"HTTP {resp.status_code}, {len(data)} tickets returned to an "
            f"UNAUTHENTICATED request (no cookie, no bearer token, no API key "
            f"of any kind beyond what a public browser tab has). The disposable "
            f"canary ticket from this run was {'present' if canary_present else 'absent'} "
            f"in the response. Per-row fields observed: "
            f"raw_text={'present' if has_raw_text_field else 'absent'}, "
            f"customer_email={'present' if has_email_field else 'absent'}. "
            f"Full response body is NOT persisted to disk or printed - this "
            f"count and field-presence check is the only evidence kept, to "
            f"avoid writing real customers' unredacted PII into a test report."
        ),
        severity="critical",
    ))

    # B2: GET /api/user_tickets?userId=<B> as an anonymous caller who supplies
    # customer B's user id with no proof of being customer B (IDOR).
    resp = requests.get(f"{NEXTJS_URL}/api/user_tickets", params={"userId": fixtures["b"].id}, timeout=30)
    data = resp.json().get("data", []) if resp.ok else []
    report.add(CheckResult(
        "B2", "API-authz",
        "GET /api/user_tickets?userId=<victim> with no proof of being that user (IDOR)",
        passed=resp.status_code in (401, 403),
        evidence=(
            f"HTTP {resp.status_code}, request supplied ONLY customer B's "
            f"userId (a UUID with no other secret) and no Authorization header "
            f"whatsoever, and the route returned {len(data)} row(s) with "
            f"HTTP 200 rather than 401/403. The route filters by the supplied "
            f"userId but never verifies the caller IS that user."
        ),
        severity="critical",
    ))

    # B3: PUT /api/tickets against the canary ticket, no auth - forge a resolution.
    resp = requests.put(
        f"{NEXTJS_URL}/api/tickets",
        json={"id": fixtures["canary_id"], "final_response": f"{CANARY_MARKER}-forged-by-security-test"},
        timeout=30,
    )
    report.add(CheckResult(
        "B3", "API-authz",
        "PUT /api/tickets (forge a resolution) against the canary ticket, no auth",
        passed=resp.status_code in (401, 403),
        evidence=f"HTTP {resp.status_code}: {resp.text[:200]}",
        severity="critical" if resp.status_code not in (401, 403) else "info",
    ))

    # B4: POST /api/customer_feedback as customer B, targeting customer A's
    # canary ticket, supplying A's own userId (which B2 just proved is
    # discoverable with zero auth) - cross-account write.
    resp = requests.post(
        f"{NEXTJS_URL}/api/customer_feedback",
        json={"ticketId": fixtures["canary_id"], "userId": fixtures["a"].id, "score": 1,
              "comment": f"{CANARY_MARKER}-cross-account-write-by-security-test"},
        timeout=30,
    )
    report.add(CheckResult(
        "B4", "API-authz",
        "POST /api/customer_feedback with no auth, only a userId+ticketId pair (chained with B2)",
        passed=resp.status_code in (401, 403),
        evidence=f"HTTP {resp.status_code}: {resp.text[:200]}. Ownership of the "
                 f"ticket BY that userId is checked server-side, but nothing "
                 f"verifies the REQUEST came from that user.",
        severity="high" if resp.status_code not in (401, 403) else "info",
    ))
    if resp.status_code == 200:
        admin_client.table("customer_feedback").delete().eq("ticket_id", fixtures["canary_id"]).execute()

    # B5: DELETE /api/tickets?id=<canary>, no auth - destructive action.
    # Run LAST in this section since it removes the canary ticket B1/B3 rely on.
    resp = requests.delete(f"{NEXTJS_URL}/api/tickets", params={"id": fixtures["canary_id"]}, timeout=30)
    verify = admin_client.table("tickets").select("id").eq("id", fixtures["canary_id"]).execute()
    actually_deleted = len(verify.data) == 0
    report.add(CheckResult(
        "B5", "API-authz",
        "DELETE /api/tickets?id=<canary>, no auth (destructive action)",
        passed=not actually_deleted,
        evidence=f"HTTP {resp.status_code}, ticket still in DB after call: {not actually_deleted}",
        severity="critical" if actually_deleted else "info",
    ))
    if actually_deleted:
        fixtures["canary_id"] = None  # already gone, skip double-delete in teardown

    # --- Positive controls: the same routes, called WITH a real, valid
    # session, must still work for the legitimate caller the fix targets.
    # Uses a second canary ticket since B5 above already removed the first.
    canary2 = (
        admin_client.table("tickets")
        .insert({
            "user_id": fixtures["a"].id,
            "customer_name": "Security Test Canary 2",
            "customer_email": CUSTOMER_A_EMAIL,
            "subject": f"{CANARY_MARKER}-positive-control",
            "raw_text": f"{CANARY_MARKER}: second canary, for positive-control (authenticated) checks.",
            "status": "received",
        })
        .execute()
        .data[0]
    )
    fixtures["canary2_id"] = canary2["id"]  # tracked separately from canary_id - see teardown_fixtures

    resp = requests.get(f"{NEXTJS_URL}/api/tickets", headers={"Authorization": f"Bearer {jwts['admin_jwt']}"}, timeout=30)
    data = resp.json().get("data", []) if resp.ok else []
    report.add(CheckResult(
        "B6", "API-authz",
        "GET /api/tickets WITH a valid staff session still works (positive control)",
        passed=(resp.status_code == 200 and any(t.get("id") == canary2["id"] for t in data)),
        evidence=f"HTTP {resp.status_code}, canary present={any(t.get('id') == canary2['id'] for t in data)}",
    ))

    resp = requests.get(
        f"{NEXTJS_URL}/api/user_tickets", params={"userId": fixtures["a"].id},
        headers={"Authorization": f"Bearer {jwts['a_jwt']}"}, timeout=30,
    )
    data = resp.json().get("data", []) if resp.ok else []
    report.add(CheckResult(
        "B7", "API-authz",
        "GET /api/user_tickets?userId=<self> WITH the matching session still works (positive control)",
        passed=(resp.status_code == 200 and any(t.get("id") == canary2["id"] for t in data)),
        evidence=f"HTTP {resp.status_code}, own ticket present={any(t.get('id') == canary2['id'] for t in data)}",
    ))

    resp = requests.post(
        f"{NEXTJS_URL}/api/customer_feedback",
        headers={"Authorization": f"Bearer {jwts['a_jwt']}"},
        json={"ticketId": canary2["id"], "userId": fixtures["a"].id, "score": 5, "comment": "great"},
        timeout=30,
    )
    report.add(CheckResult(
        "B8", "API-authz",
        "POST /api/customer_feedback WITH the ticket owner's own session still works (positive control)",
        passed=(resp.status_code == 200),
        evidence=f"HTTP {resp.status_code}: {resp.text[:200]}",
    ))

    resp = requests.put(
        f"{NEXTJS_URL}/api/tickets",
        headers={"Authorization": f"Bearer {jwts['admin_jwt']}"},
        json={"id": canary2["id"], "final_response": f"{CANARY_MARKER}-legit-resolution"},
        timeout=30,
    )
    report.add(CheckResult(
        "B9", "API-authz",
        "PUT /api/tickets WITH a valid staff session still works (positive control)",
        passed=(resp.status_code == 200),
        evidence=f"HTTP {resp.status_code}: {resp.text[:200]}",
    ))

    resp = requests.delete(
        f"{NEXTJS_URL}/api/tickets", params={"id": canary2["id"]},
        headers={"Authorization": f"Bearer {jwts['admin_jwt']}"}, timeout=30,
    )
    verify = admin_client.table("tickets").select("id").eq("id", canary2["id"]).execute()
    report.add(CheckResult(
        "B10", "API-authz",
        "DELETE /api/tickets?id=<canary2> WITH a valid staff session still works (positive control)",
        passed=(resp.status_code == 200 and len(verify.data) == 0),
        evidence=f"HTTP {resp.status_code}, ticket gone={len(verify.data) == 0}",
    ))
    if len(verify.data) == 0:
        fixtures["canary2_id"] = None


# ---------------------------------------------------------------------------
# Section C - PII redaction boundary (mostly backed by the existing pytest
# suite; one live adversarial check added here)
# ---------------------------------------------------------------------------


def section_c() -> None:
    from app.tools.redaction_tool import mask_pii, mask_pii_reversible

    adversarial_text = (
        "Hi, this is Kalana Wijesuriya. My email is kalana.w+billing@clario-test.dev, "
        "phone +94 71 234 5678, and my card is 4111-1111-1111-1111. I'm based in "
        "Colombo and work for Acme Corp. Please fix my account, Kalana."
    )
    masked, pii_found = mask_pii(adversarial_text)
    leaks = [
        val for val in (
            "Kalana Wijesuriya", "kalana.w+billing@clario-test.dev",
            "+94 71 234 5678", "4111-1111-1111-1111",
        )
        if val in masked
    ]
    report.add(CheckResult(
        "C1", "PII-redaction",
        "mask_pii() strips name/email/phone/card from a realistic multi-PII ticket",
        passed=(len(leaks) == 0),
        evidence=f"pii_found types={sorted({p['type'] for p in pii_found})}, "
                 f"leaked_raw_values_in_output={leaks or 'none'}",
        severity="critical" if leaks else "info",
    ))

    reversible_masked, shadow_map, _ = mask_pii_reversible(adversarial_text)
    reversible_leaks = [
        val for val in ("+94 71 234 5678", "4111-1111-1111-1111")
        if val in reversible_masked
    ]
    report.add(CheckResult(
        "C2", "PII-redaction",
        "mask_pii_reversible() never gives phone/card a reversible stand-in "
        "(only PERSON/EMAIL are reversible; everything else must stay a bracket token)",
        passed=(len(reversible_leaks) == 0),
        evidence=f"leaked_raw_values={reversible_leaks or 'none'}, "
                 f"shadow_map_covers={sorted(shadow_map.values())}",
        severity="critical" if reversible_leaks else "info",
    ))

    # C3: confirm every add_precedent() call site in the app passes
    # redacted_text, never raw_text, by static grep (behavioral proof would
    # require a full pipeline run with real LLM calls - this static check
    # plus the source excerpt is the evidence).
    import subprocess
    grep = subprocess.run(
        ["grep", "-n", "add_precedent(", "-r", "app/main.py"],
        cwd=SIDECAR_ROOT, capture_output=True, text=True,
    )
    call_lines = [l for l in grep.stdout.splitlines() if l.strip()]
    all_use_redacted = all("redacted_text" in l for l in call_lines) and len(call_lines) > 0
    report.add(CheckResult(
        "C3", "PII-redaction",
        "Every add_precedent() call site passes redacted_text (never raw_text) into ChromaDB",
        passed=all_use_redacted,
        evidence="; ".join(call_lines) if call_lines else "no call sites found",
        severity="critical" if not all_use_redacted else "info",
    ))


def main() -> None:
    print(f"=== Clario Security & Access Control Test Run {RUN_ID} ===")
    print(f"Supabase project: {SUPABASE_URL}")
    print(f"Next.js target:   {NEXTJS_URL}\n")

    fixtures = setup_fixtures()
    print(f"Fixtures created: customer_a={fixtures['a'].id}, customer_b={fixtures['b'].id}, "
          f"admin={fixtures['admin'].id}, canary_ticket={fixtures['canary_id']}\n")

    try:
        print("--- Section A: Row Level Security ---")
        jwts = section_a(fixtures)
        print("\n--- Section B: Service-role Next.js API route authorization ---")
        section_b(fixtures, jwts)
        print("\n--- Section C: PII redaction boundary ---")
        section_c()
    finally:
        print("\n--- Cleanup ---")
        teardown_fixtures(fixtures)

    passed = sum(1 for c in report.checks if c.passed)
    failed = [c for c in report.checks if not c.passed]
    total = len(report.checks)
    print(f"\n=== SUMMARY: {passed}/{total} checks passed ===")
    if failed:
        print(f"{len(failed)} FAILED (i.e. {len(failed)} real security gap(s) found):")
        for c in failed:
            print(f"  - {c.id} [{c.severity}] {c.description}")

    REPORT_PATH.write_text(json.dumps({
        "run_id": RUN_ID,
        "supabase_project": SUPABASE_URL,
        "nextjs_target": NEXTJS_URL,
        "summary": {"total": total, "passed": passed, "failed": len(failed)},
        "checks": [vars(c) for c in report.checks],
    }, indent=2))
    print(f"\nFull results written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
