# Clario — Test Execution & Results

This folder holds the **real, executed** testing results for the Clario system
(CS3501 multi-agent customer-support-triage platform: `clario-ml-sidecar`
Python/FastAPI/LangGraph backend, `frontend` Next.js app, `ml_finetuning`
model-training/data-curation pipeline, and Supabase).

It follows the phase breakdown from the course's reference document,
`docs/Sample test plan report.pdf` ("Master Test Plan" — a generic template
for a different sample system), adapted to what Clario actually is: an
AI agent pipeline plus a web app, not a plain PHP/Symfony CRUD system. Each
phase below maps to a section of that sample plan; the mapping is recorded
in each phase's own README.

## Phase Status

| # | Phase | Sample-plan equivalent | Status |
|---|-------|------------------------|--------|
| 01 | [Unit Testing](01-Unit-Testing/) | §3.1.2 Function Testing (unit-level) | **Complete** — see report |
| 02 | [Integration Testing](02-Integration-Testing/) | §3.1.1 Data & Database Integrity Testing, §3.1.2 Function Testing (end-to-end) | **Complete** — see report |
| 03 | [UI / E2E Testing](03-UI-E2E-Testing/) | §3.1.3 User Interface Testing | Planned |
| 04 | [Performance & Load Testing](04-Performance-Load-Testing/) | §3.1.4 Performance Profiling, §3.1.5 Load Testing | Planned |
| 05 | [Security & Access Control Testing](05-Security-Access-Control-Testing/) | §3.1.6 Security and Access Control Testing | Planned |
| 06 | [Failover & Recovery Testing](06-Failover-Recovery-Testing/) | §3.1.7 Failover and Recovery Testing | Planned |

Configuration testing (§3.1.8 in the sample plan) is not tracked as a
separate phase — Clario runs as a containerized web service, not a
multi-platform desktop client, so that phase does not apply the way it did
in the sample system.

## How results were produced

Every result in this folder comes from actually running the project's real
test suites (`pytest` for the two Python services, `vitest` for the
frontend) on 2026-09-03 and capturing the unmodified console output. No
numbers here are estimated or fabricated — where a suite failed, the raw
failure output is kept alongside the analysis.

## Deliverables per phase (mirrors §4 of the sample plan)

Each populated phase folder contains, at minimum:
- **Raw test logs** — unedited tool output (`test-log.txt` / equivalent)
- **A written report** — scope, environment, pass/fail/skip counts, and for
  every failure: root cause and severity, not just "failed"
