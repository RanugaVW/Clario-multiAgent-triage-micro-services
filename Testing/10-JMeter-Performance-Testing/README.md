# 10 — JMeter Basic Performance Testing

**Status:** Complete — see [`TEST_REPORT.md`](TEST_REPORT.md).

**Assigned-table mapping:** Basic Performance Testing → JMeter (of the four
tools listed — JMeter, HP LoadRunner, Gatling, BlazeMeter — JMeter was
chosen; see TEST_REPORT.md §1 for why).

## Scope

A real JMeter test plan (`clario-basic-performance.jmx`), run in non-GUI
mode against the live stack: `clario-ml-sidecar`'s `/health` (unauthenticated,
:8600) and the Next.js staff console's `GET /api/tickets` (authenticated,
:3000). Two Thread Groups simulate modest concurrent load (10 users × 20
loops on `/health`, 5 users × 10 loops on `/api/tickets`) — "basic" by
design, since full load/stress testing of the LangGraph pipeline itself is
already [`Testing/04-Performance-Load-Testing`](../04-Performance-Load-Testing/)'s
job. This phase demonstrates JMeter specifically, on the lighter-weight,
always-available HTTP surface.

## How to run this

Requires the frontend (`:3000`) and `clario-ml-sidecar` (`:8600`) running.

```bash
Testing/10-JMeter-Performance-Testing/run_tests.sh
```

Downloads JMeter locally into `.tools/` at the repo root if it isn't there
yet (no system install), creates one disposable staff account for the
`/api/tickets` token, runs the plan, generates an HTML dashboard report
into `report/index.html`, and tears the fixture down.

### Opening the plan in the JMeter GUI (optional, for learning)

```bash
.tools/apache-jmeter-5.6.3/bin/jmeter -t Testing/10-JMeter-Performance-Testing/clario-basic-performance.jmx
```
This opens the actual test plan used for the real run above in JMeter's own
GUI, showing the two Thread Groups, their HTTP Samplers, and the Response
Assertions checking each one returned `200`. `authToken` is read from a
JMeter property (`${__P(authToken,)}`) rather than hardcoded, so running it
from the GUI needs `-JauthToken=<a real token>` passed the same way, or the
`/api/tickets` sampler will get `401`s.

## Why JMeter (and not the other 3 listed)

- **HP LoadRunner** — commercial, licensed enterprise software; not
  installable in this environment (and generally not free even outside it).
- **BlazeMeter** — a paid cloud service that *runs* JMeter test plans at
  scale. Building the `.jmx` here first is the more fundamental artifact:
  it's the same file BlazeMeter would consume if that became available.
- **Gatling** — a real, free, code-first alternative (Scala/Java DSL). Not
  chosen only because JMeter is the more universally-taught, GUI-plus-CLI
  tool for exactly this kind of assignment, and its plans are portable to
  BlazeMeter unchanged.

## Files in this folder

| File | What it is |
|---|---|
| `clario-basic-performance.jmx` | The real JMeter test plan — importable into the JMeter GUI |
| `setup_fixtures.py` / `teardown_fixtures.py` | Create/delete the one disposable staff account this run needs |
| `run_tests.sh` | Runs the whole phase end-to-end, downloading JMeter if needed |
| `TEST_REPORT.md` | Results and analysis |
| `test-log.txt` | Raw JMeter CLI output |
| `results.jtl` | Raw per-sample results (git-ignored, regenerated per run) |
| `report/` | Generated HTML dashboard (`report/index.html`) - git-ignored, regenerated per run |
