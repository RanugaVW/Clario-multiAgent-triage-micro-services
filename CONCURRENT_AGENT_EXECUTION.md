# Running Technical + Billing Agents Concurrently — Feasibility Report

## TL;DR

Yes, this is implementable — LangGraph 1.2.9 (the pinned version, `requirements.txt`) natively supports fanning out to multiple nodes in one super-step. It is **not** implemented today for a documented reason (see below), and doing it safely requires more than just changing two edges: three separate state fields would silently race or crash if fanned out as-is, and one shared object (the circuit breaker) has a real thread-safety gap that only becomes visible once two branches run at the same time. None of this is fixed today because nothing has ever exercised the concurrent path — it's exactly the kind of bug that stays invisible until you actually try.

This report is a design/audit document, not a changelog — nothing in the pipeline has been modified. Section 5 is a concrete, ready-to-implement plan if you want to proceed.

---

## 1. Why it's sequential today (the actual root cause)

`app/graph/graph_builder.py`, `_both_specialists_node`, states it directly:

> "Runs technical_agent_node then billing_agent_node *sequentially*, not as a parallel LangGraph fan-out: both nodes return `{**state, ...}`, and two concurrent branches writing the same TypedDict keys in one step hits LangGraph's `InvalidUpdateError` ('Can receive only one value per step')."

`app/graph/state.py` defines `TicketState` as a plain `TypedDict` — every field has the default "last write wins" channel. When two nodes run in the same super-step and both return a value for the same key, LangGraph doesn't know how to combine them, so it raises rather than guess. Sequential composition works around this by having each node read-merge-write off the *other's already-applied* result, so there's only ever one writer per step. That's a real constraint, not a stylistic choice — reversing it means telling LangGraph explicitly how to merge every field both branches touch.

## 2. What real concurrency would actually buy you

It's worth being precise about where the win comes from, because it's narrower than "two agents at once = 2x faster."

- **Classification is not on this path.** The GPU-bound local LoRA model is guarded by `_llm_lock` (`app/tools/local_llm.py`, a `threading.Lock` around `_model.generate`), but that lock only guards *classification* inference, which already happened before routing. Drafting (`generate_draft`, same file) calls the Gemini API, not the local model — so there's no GPU contention to worry about for this specific change.
- **The real win is overlapping two independent network calls.** `technical_agent_node` and `billing_agent_node` (`app/agents/technical_agent/node.py`, `app/agents/billing_agent/node.py`) each do: `retrieve_context()` (Chroma, synchronous) → `generate()` (Gemini, already offloaded to a thread pool via `asyncio.get_event_loop().run_in_executor` in `app/tools/llm_client.py`). Run sequentially, wall-clock time ≈ technical\_time + billing\_time. Run concurrently, wall-clock time ≈ max(technical\_time, billing\_time).
- **This is measurable against your own numbers.** `Testing/04-Performance-Load-Testing/TEST_REPORT.md` recorded single-request pipeline times of ~24,101.7ms (technical) and ~5,165.8ms (billing). If those figures transfer to the dual-domain path, sequential ≈ 29,267ms vs. a theoretical concurrent ≈ 24,102ms — a real latency cut for "both"-routed tickets, but bounded by whichever domain is slower, not by the sum. It only benefits `routing_decision == "both"` tickets specifically — check how frequently that routing outcome actually occurs before treating this as a broad system-wide speedup.
- **`retrieve_context` itself is not currently async-safe.** It's a plain synchronous function called directly inside an `async def` node — not wrapped in `run_in_executor`/`asyncio.to_thread`. If you just `asyncio.gather()` the two node coroutines without changing this, the two Chroma retrievals will still serialize on the single-threaded event loop before either draft call even starts, quietly eating most of the benefit above.

## 3. The concrete failure modes if this is done carelessly

These are not hypothetical — they follow directly from reading the two node implementations side by side.

**a) `InvalidUpdateError` on plain dict/scalar fields.** `agent_drafts`, `retrieved_context`, `rag_top_score`, and `low_relevance_flags` are all written by both nodes via `{**state.get(field, {}), domain: value}`. If both branches read the *same* base state and write in the same super-step, LangGraph sees two different dict values for one key and rejects the step — exactly the error the code comment already anticipates.

**b) A silent, incorrect merge on `failure_type`.** Look closely at the write: `"failure_type": "dependency_failure" if draft is None else state.get("failure_type", "none")`. On success, a node just echoes back whatever was already in state — it doesn't try to overwrite. That means if technical succeeds and billing's Chroma circuit breaker is open, one branch writes `"dependency_failure"` and the other writes back `"none"` (unchanged) from the *same* base state — two different values, same key, same step. This is worse than case (a) because it's not obviously wrong from reading either node in isolation; it only shows up when you reason about both branches together.

**c) Double-counting (or silent loss) of `llm_call_count`.** Both nodes compute `state.get("llm_call_count", 0) + calls_made`. If both read `llm_call_count = 5` from the same base state, technical writes `5 + 1 = 6` and billing writes `5 + 1 = 6` — LangGraph would (best case) reject the conflicting values, or (worse, if you "fix" this by making the field a naive reducer that just takes the last write) silently drop one node's calls entirely. Either way, the `total_llm_calls` telemetry persisted to Supabase (`main.py`, per the field's own docstring) becomes wrong the moment this runs concurrently — a data-integrity issue, not a crash, which is the more dangerous kind because nothing tells you it happened.

**d) A genuine, currently-latent thread-safety gap in the circuit breaker.** `CircuitBreaker.allow_request()` / `record_success()` / `record_failure()` (`app/tools/circuit_breaker.py`) mutate `self._half_open_in_flight` and a `deque` with no lock. Today this is safe by accident — every call is strictly sequential, so there's never a second thread touching the same breaker at the same instant. The moment technical and billing run concurrently, both go through `get_breaker("local_draft")` (a single shared, process-global instance from `_BREAKERS`, itself an unlocked dict) from two different OS threads (the `run_in_executor` thread pool uses real threads, not just coroutines). If the breaker is half-open, both threads can read `_half_open_in_flight = False` before either sets it `True` — a classic TOCTOU race that lets two probe requests through when the breaker was designed to allow exactly one. This bug exists in the code right now; it simply has no way to manifest until something calls it from two threads simultaneously.

## 4. Is it worth it — the honest tradeoffs

**Advantages if done correctly:**
- Real, measurable latency reduction specifically for dual-domain ("both") tickets — a legitimate customer-facing win and a legitimate "we implemented true concurrent multi-agent execution, safely" claim for the viva, upgrading §5.4 of `DIFFERENTIATION_REPORT.md` from a caveat into a strength.
- Forces fixing the circuit-breaker race regardless of whether you keep the change — that bug is real today, just unobserved.

**Costs:**
- **State-schema complexity.** Every field two branches can touch needs an explicit `Annotated[T, reducer_fn]` merge function instead of the default. That's a permanent increase in how much a reader needs to understand about `TicketState` to safely add a new field later — the current plain-`TypedDict` design is easy to reason about specifically because nothing merges concurrently.
- **Increased third-party API pressure.** Two simultaneous Gemini calls per dual-domain ticket instead of one at a time. Under any real load (many "both" tickets arriving close together), this roughly doubles instantaneous concurrent Gemini usage from that path, which pushes you toward rate limits — and toward the circuit breaker tripping — faster than the sequential version would. The `Testing/04` report already flagged serial worker processing as a deliberate, observed characteristic of the current system; concurrency here interacts with that broader queuing behavior and should be load-tested together, not in isolation.
- **Harder debugging and tracing.** The `started`/`finished` trace events (`app/tracing/pipeline_tracer.py`, surfaced in `Visualizer/`) for `technical_agent` and `billing_agent` are currently strictly ordered. Once concurrent, their spans overlap in time — the viewer's timeline rendering and anyone reading raw trace logs need to stop assuming one finishes before the other starts.
- **Narrow applicability.** This only changes behavior for tickets where `routing_decision == "both"`. If that's a small fraction of total traffic, the aggregate throughput impact is real but small — the latency win is per-ticket, not system-wide.

## 5. If you decide to proceed: the concrete, safe implementation plan

This is scoped as its own small task, not a drive-by edit — it touches the shared state schema, which every node in the graph depends on.

1. **Add reducers in `state.py`** for every field both specialists write:
   - `agent_drafts`, `retrieved_context`, `rag_top_score`, `low_relevance_flags` → `Annotated[dict, lambda a, b: {**a, **b}]`. Safe because technical and billing always write disjoint keys (`"technical"` vs `"billing"`), so a shallow union can never lose data regardless of write order.
   - `llm_call_count` → `Annotated[int, operator.add]`, **and** change both node functions to return only their own `calls_made` delta (not `state.get(...) + calls_made`). The reducer then does the summing — this also happens to make the solo-dispatch (non-"both") path more correct, since it removes a stale-read risk there too.
   - `failure_type` → a small custom reducer that prefers `"dependency_failure"` over any other value, and otherwise keeps the incoming value unless it's the unchanged default — this needs to be written carefully since `failure_type` is also written by `validation_node` outside the fan-out; the reducer must degrade to normal single-writer behavior everywhere else in the graph.
2. **Change the routing edge** so `routing_decision == "both"` fans out to `["technical_agent", "billing_agent"]` directly (LangGraph's native multi-target conditional edge) instead of dispatching to the composite `_both_specialists_node`. Both existing per-domain nodes already exist as standalone graph nodes for the single-domain paths — no new node code needed, just reuse them as fan-out targets. `validation` already has both as predecessors in effect; LangGraph's super-step barrier means it won't run until both branches complete.
3. **Wrap `retrieve_context()` calls in `asyncio.to_thread(...)`** inside both agent nodes, so retrieval genuinely overlaps instead of serializing on the event loop before the draft calls even begin.
4. **Add a lock inside `CircuitBreaker`** (`app/tools/circuit_breaker.py`) around the read-modify-write in `allow_request`/`record_success`/`record_failure` — a plain `threading.Lock` is enough given these are short, non-blocking critical sections. Fix this regardless of whether the rest of this plan proceeds; it's a latent bug today.
5. **Retire `_both_specialists_node`** once the fan-out is verified working (or keep it behind a feature flag during rollout, if you want a fallback).
6. **Re-verify, don't just re-run green:**
   - Unit tests in `tests/graph/` and `tests/agents/` for both node behaviors.
   - `Testing/04-Performance-Load-Testing` — re-measure dual-domain latency specifically, to get the *actual* number instead of the projected max()-based estimate in §2.
   - `Testing/12-Data-Science-Evaluation` Track B and Track D — re-run to confirm `failure_type` and escalation decisions for dual-domain tickets are unchanged in *outcome*, only in timing. This is the step that would catch a subtly wrong reducer (e.g., case 3b above) before it reaches production, since a wrong merge could change which tickets get escalated without ever throwing an exception.

## 6. Recommendation

Feasible, moderate effort, real but narrow benefit. The risk isn't "can LangGraph do this" — it can — the risk is that a fast version of this change (just swap the edges, ignore the state schema) reproduces the exact `InvalidUpdateError` already documented in the code, or worse, ships case 3(b)/3(c) as a silent correctness bug in escalation telemetry that only a full Track B/D re-run would catch. Treat it as a scoped task with the six steps above, not a same-session edit.

I haven't implemented any of this yet — say the word if you want me to proceed with the plan in Section 5.
