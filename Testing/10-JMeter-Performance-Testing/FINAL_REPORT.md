# Final Report — 10 JMeter Basic Performance Testing

This is the summary we are submitting for this stage, in the generic
reporting format our reference Master Test Plan asks for in its own §4.2.
The full narrative writeup is in [`TEST_REPORT.md`](TEST_REPORT.md); this
page is the short version for the record.

**Date:** 2026-09-04
**Team:** Clario QA Team
**Test case field:** Basic load on two real endpoints (the sidecar health
check and the staff ticket list) using JMeter, chosen from our assigned
tool list over HP LoadRunner (licensed, not installable here), BlazeMeter
(a paid runner for the same kind of plan we already built), and Gatling

## Metrics

| Metric | Value |
|---|---|
| No. of requests executed (clean run) | 250 |
| No. of pass (clean run) | 250 |
| No. of fail (clean run) | 0 |
| Pass percentage (clean run) | 100% |
| No. of requests executed (under real contention) | 250 |
| No. of pass (under contention) | 249 |
| No. of fail (under contention) | 1 |
| Pass percentage (under contention) | 99.6% |

## Comments

We ran two thread groups against the real, live system: a health-check
endpoint with no authentication, and the staff ticket-list endpoint with
a real staff token. In a clean run with nothing else competing for the
machine, all 250 requests succeeded, with the ticket-list endpoint
showing the same tail-latency variance our load-testing stage already
measured for that same database query. We then repeated the exact same
plan while our Selenium browser suite was also running against the same
live servers, deliberately, to see what real contention on this shared
machine looks like — one request timed out at the 15-second limit under
that load, a real and disclosed effect of shared-machine contention, not
an application defect. We found no application bugs in this stage; the
one failure is an honest environmental observation, kept in the record
rather than discarded.

## Files referenced

- [`TEST_REPORT.md`](TEST_REPORT.md) — full findings for both runs
- [`clario-basic-performance.jmx`](clario-basic-performance.jmx) — the JMeter test plan
- [`results.jtl`](results.jtl) — raw results data
- [`report/index.html`](report/index.html) — the full interactive JMeter HTML dashboard
