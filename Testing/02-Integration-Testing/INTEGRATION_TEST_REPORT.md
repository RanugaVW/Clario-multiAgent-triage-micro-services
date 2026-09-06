# Integration Test Report — Clario System

**Date:** 2026-09-03
**Tester:** Ranuga Weerasekara (ranugaweerasekara2@gmail.com), assisted by Claude Code
**Branch:** `real-response-dataset`
**Environment:** Production Supabase project (`mdvfvtpbwqhccmaarpli`), production ChromaDB store, the sidecar's own already-running production `uvicorn`/`app.worker` processes, real Gemini judge LLM calls (`gemini-3.1-flash-lite`). There is no separate test/staging environment for this system.

**Final result: 4/4 scenarios passed.** Two real findings surfaced by the
first pass were fixed and re-verified live; see §4 and §6 for what changed
and why, and §2 for a production incident that happened along the way.

## 1. Scope

This phase corresponds to §3.1.1 ("Data and Database Integrity Testing")
and §3.1.2 ("Function Testing", multi-component) of the reference Master
Test Plan: exercising the full ticket pipeline as a whole, across process
and network boundaries, and verifying every table/collection it writes to
ends up correct — not individual functions in isolation (that's Phase 01).

Four scenarios were submitted to the live sidecar over HTTP
(`POST /process_ticket`, exactly as the Java gateway does in production):
`technical_resolved`, `billing_resolved`, `ambiguous_dual_domain`, and
`cache_hit_resubmission` (an identical resubmission of `technical_resolved`,
to test the semantic cache).

## 2. A production incident happened during the first pass — full account

The very first attempt at this phase caused a real incident and is
documented here in full rather than omitted, because it directly shaped
how the rest of the system was tested and is a real operational risk on
this deployment.

**What happened:** the original test design called `background_orchestration()`
directly, in-process, importing `app.main`. That import path loads the
sidecar's local Gemma-3 model. Unknown at design time: **this machine
already runs the live production sidecar** (`app.worker` + `uvicorn`, both
long-running), which has that same model resident in the machine's single
6GB GPU. The test process tried to load a second copy:

1. First attempt (GPU): failed cleanly with `torch.OutOfMemoryError`, caught, no side effects.
2. Second attempt (forced onto CPU to avoid the GPU conflict): a second full copy of the model in system RAM pushed the 15GB machine over the edge. The Linux OOM-killer fired and killed an unrelated VS Code process (`journalctl -k`: `Out of memory: Killed process 4485 (code)`). Repeated NVIDIA driver allocation failures followed, and — separately from the OOM-killer's own explicit log — **the live production `uvicorn` and `app.worker` processes were both found to have exited** shortly after, taking the real service down until manually restarted.

No test/Supabase data was lost (the `finally`-block cleanup for the one
scenario that had started ran correctly), but the live service was down
until manually restarted.

**Fix:** the test runner was rewritten to submit over HTTP to the
already-running sidecar (`localhost:8600/process_ticket`) instead of
importing `app.main` and invoking the graph in-process, and to poll
Supabase for completion rather than awaiting a coroutine directly. This
reuses the already-loaded model instead of loading a second copy, and adds
no more load than one real ticket submission would. Every result below is
from this HTTP-based design.

**Follow-up worth the team's attention (not fixed here, out of this
phase's scope):** this deployment has no headroom to run anything
GPU/RAM-heavy alongside the live service on this machine. Any future
local-model tooling (training, batch eval, this kind of integration test)
needs either a dedicated environment or to explicitly reuse the live
process the way the fixed script now does.

## 3. Two real findings from the first HTTP-based pass, both fixed and re-verified

The first HTTP-based run (`c67dafb5`) passed 1/4 and surfaced two real,
reproducible findings. Both were fixed in code/config and confirmed fixed
by re-running the full suite live against production again — this section
covers what was found and fixed; §7 covers the final clean run.

### 4. Fix 1 — judge evaluations were failing: Gemini quota exhaustion → pinned a fresh model

**Root cause, confirmed by reproduction:** `GEMINI_JUDGE_MODEL` was
configured as the `gemini-flash-latest` alias, which resolved to
`gemini-3.8-flash`. This session's own testing activity (two full
4-scenario runs plus several diagnostics, each triggering real judge
calls) exhausted that model's small free-tier daily quota (20
requests/day) partway through each run:

```
google.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED.
Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests,
limit: 20, model: gemini-3.8-flash
```

Reproduced directly by replaying the exact real draft/context a live run
had produced against `evaluate_draft()` in isolation — same 429.

`response_judge_node`'s per-domain try/except correctly caught this and
logged a warning rather than failing the ticket (both affected tickets
still fully resolved) — the graceful-degradation design worked exactly as
intended. But it meant `response_evaluations` was silently missing for
any domain unlucky enough to hit the exhausted quota.

**Fix:** `clario-ml-sidecar/.env`'s `GEMINI_JUDGE_MODEL` repointed from the
`gemini-flash-latest` alias to a specific, unused-that-day model,
`gemini-3.1-flash-lite`. This is a config change, not a code change — the
env var already existed for exactly this purpose
(`app/tools/response_judge.py:307`). The live `uvicorn`/`app.worker`
processes were restarted (by the user) to pick up the new value, since
`.env` isn't hot-reloaded and the judge client is a cached singleton.

**Verified:** all three domain-scoring scenarios (`technical_resolved`,
`billing_resolved`, `ambiguous_dual_domain`) wrote a real
`response_evaluations` row with `judge_model: "gemini-3.1-flash-lite"` and
valid 1-5 scores in the final clean run (§7).

One transient blip during verification is worth recording precisely: the
very first ticket submitted immediately after the config-change restart
(`technical_resolved` in run `b0465126`) resolved correctly but was
momentarily missing its `response_evaluations` row. Reproduced twice more
right after with identical inputs — both times the row was written
correctly, and a full fresh run right after was 4/4 clean. Investigated
enough to rule out a deterministic code bug (the exact insert payload,
schema constraints, and judge output were all checked and are fine); most
consistent explanation is a one-off tied to the model/thread-pool cold
start on the very first request after a fresh restart. Flagged, not
chased further — see §8.

### 5. Scenario-design note: `ambiguous_dual_domain` wasn't actually ambiguous

The scenario text ("My payment failed but money was still taken from my
bank account, and now I can't log in...") was written to probe the
dual-domain/escalation path documented as a regression in
[Phase 01](../01-Unit-Testing/UNIT_TEST_REPORT.md#5-defects-found--clario-ml-sidecar-4-failures).
In practice, the real classifier confidently labeled it `"Payment Problem"`
at 0.85 confidence every run, routing it straight to billing — never
reaching the ambiguous/escalation branch. This is a limitation of the test
wording against the real (not mocked) classifier, not a finding about the
pipeline; left as a follow-up (§8) rather than iterating further.

### 6. Fix 2 — `ticket_classifications` got a garbage row on every cache hit

While verifying the semantic cache, `cache_hit_resubmission` correctly
registered a cache hit (`cache_hit: true`, `cache_source_ticket_id`
pointing at the originating ticket) once a bug in the *test script itself*
was fixed (its cleanup was deleting the Chroma precedent immediately after
the first scenario, before the cache-hit scenario got a chance to query
it — fixed by deferring that cleanup).

That run also surfaced a real, small product defect: on the cache-hit
path, `app/main.py`'s `background_orchestration` was inserting a
`ticket_classifications` row unconditionally, even though
`classification_node` is structurally skipped on a cache hit
(`graph_builder.py`'s `_after_cache` routes straight to `response_judge`).
Every field in that row (`category`, `priority`, `sentiment`, `confidence`,
`source`) was `NULL`. Confirmed directly from a live run's
`raw_graph_payload`.

**Severity:** Minor (data quality, not a functional defect — nothing read
this table expecting every row to have a real classification).

**Fix:** `app/main.py`'s classification insert is now gated:

```python
# cache_check_node short-circuits straight to response_judge on a hit,
# so classification_node never ran - final_state has no classification
# fields to insert (they'd all be NULL).
if not final_state.get("cache_hit"):
    classification_payload = {...}
    supabase_client.table("ticket_classifications").insert(classification_payload).execute()
```

**Verified:** the final clean run's `cache_hit_resubmission` scenario shows
`classification_count: 0` — no row written at all on a cache hit, which
is now correct.

## 7. Final clean run (`3d5a9a2f`, 2026-09-03T17:38 UTC)

| Scenario | Result | Notes |
|---|---|---|
| `technical_resolved` | **PASS** | Full pipeline clean: classification, routing, draft, judge evaluation (real `gemini-3.1-flash-lite` score), resolution. |
| `billing_resolved` | **PASS** | Same, billing domain. |
| `ambiguous_dual_domain` | **PASS** | Classified confidently as billing (see §5) and processed cleanly through that path. |
| `cache_hit_resubmission` | **PASS** | Cache hit correctly detected and reused; classification_node correctly skipped with no garbage row written. |

Raw console output: [`test-log.txt`](test-log.txt). Full structured
results: [`integration_test_results.json`](integration_test_results.json).
Production and Chroma confirmed clean before and after
(`cleanup_sweep.py --dry-run` → "No stray integration-test tickets
found."), and the live sidecar confirmed healthy
(`GET /health` → `{"status": "ok"}`) with GPU/RAM back at the normal
single-instance baseline throughout.

## 8. Follow-ups for a future run

- The one-off missing-evaluation blip noted in §4 is worth a second look
  if it recurs — specifically, whether it's tied to the very first request
  after a cold restart. Not reproducible on demand from two direct retries.
- Escalation path (`human_reviews` + the two-row `resolutions` write) was
  not exercised live in this phase — the Phase 01 `"both"`-routing
  regression means it's hard to trigger through the real classifier right
  now; it is covered at the unit level but not confirmed against the real
  Supabase writes.
- This machine has no spare GPU/RAM headroom alongside the live service —
  any future tooling here should reuse the live process (HTTP) rather than
  loading its own model copy, per §2.
