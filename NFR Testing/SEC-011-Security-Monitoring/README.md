# SEC-011 — Security Monitoring

**Status before:** 🔴 Not Implemented — nothing detected repeated failed authentication; no rate signal, no alert.
**Status after:** 🟡 Partial — repeated failures from one source now raise an alert record in all three Java services. Delivery to an administrator and a dashboard view are not built.

Builds on `FR Testing/FR-049-Security-Event-Logging/` (the audit records this monitors).

## What changed

New `FailedAuthTracker` (`com.clario.config`, one copy per Java service), fed by the same
authentication entry point that writes the FR-049 audit record. It keeps a sliding window of
failure timestamps per source (`request.getRemoteAddr()`); when a source reaches the threshold it
emits **one** record at ERROR on the dedicated `security.alert` logger:

```
event=SECURITY_ALERT type=REPEATED_AUTH_FAILURE source=203.0.113.9 failures=10 windowSeconds=60
```

Configuration (also SUP-002): `SECURITY_ALERT_FAILED_AUTH_THRESHOLD` (default 10) and
`SECURITY_ALERT_WINDOW_SECONDS` (default 60), surfaced in each `application.properties`.

Design decisions:

- **Detection only, never blocking.** A wrong threshold cannot lock a real user out. Blocking is
  a policy decision (and would need shared state across gateway replicas) — deliberately not done.
- **One alert per source per window.** A sustained attack yields a steady trickle, not a flood.
- **Bounded memory.** At most 10,000 sources are tracked; stale ones are purged, and past that limit
  new sources simply go untracked. A flood of spoofed distinct sources cannot exhaust the heap, and
  authentication itself is never affected.
- **Monitoring can't break requests.** `recordFailure` swallows its own faults (logging
  `SECURITY_MONITOR_ERROR`), so a bug here still returns the normal 401.
- **Credentials never appear** in the alert — only source, count and window.

## No Supabase changes needed.

## Tests (run with `.env` hidden and Redis unreachable, matching CI)

`FailedAuthTrackerTest` (10 cases, deterministic fake clock): below threshold silent; exactly one
ERROR alert at the threshold; no flood within a window; re-alert after the window; failures spread
outside the window never alert; sources independent; memory bound holds; stale sources purged;
a broken clock never propagates; invalid config rejected.
`SecurityAlertingTest` (per service): three real rejected HTTP requests through the actual filter
chain → exactly one alert, all three responses still 401, token text absent from the alert.

Mutation check: removing the `recordFailure` call from `SecurityConfig` made
`SecurityAlertingTest` fail, so the test genuinely guards the wiring.

```
api-gateway:           Tests run: 22, Failures: 0, Errors: 0 -- BUILD SUCCESS
agent-review-service:  Tests run: 28, Failures: 0, Errors: 0 -- BUILD SUCCESS
ticket-core-service:   Tests run: 31, Failures: 0, Errors: 0 -- BUILD SUCCESS
```

## What's still open

- **"Critical security events generate notifications"** — the alert is a log record. There is no
  email/Slack/pager channel in the system (FR-058 is unimplemented); a log-based alerting rule on
  the `security.alert` logger would be the cheapest way to connect one.
- **"Available through administrative dashboards"** — no dashboard reads this.
- **Source identity behind a proxy.** Downstream services see the gateway's address, so
  per-client detection is meaningful at `api-gateway` (the edge) and coarse at the two internal
  services. `X-Forwarded-For` is intentionally not trusted, since a client can forge it.
- Counters are per-instance and in memory; they reset on restart and are not shared between replicas.
