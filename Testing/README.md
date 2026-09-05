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
| 03 | [UI / E2E Testing](03-UI-E2E-Testing/) | §3.1.3 User Interface Testing | **Complete** — see report |
| 04 | [Performance & Load Testing](04-Performance-Load-Testing/) | §3.1.4 Performance Profiling, §3.1.5 Load Testing | **Complete** — see report |
| 05 | [Security & Access Control Testing](05-Security-Access-Control-Testing/) | §3.1.6 Security and Access Control Testing | **Complete** — see report (6 findings, all fixed & re-verified: 23/23) |
| 06 | [Failover & Recovery Testing](06-Failover-Recovery-Testing/) | §3.1.7 Failover and Recovery Testing | **Complete** — see report (3 findings, all fixed & re-verified: 16/16) |
| 07 | [API Testing](07-API-Testing/) | §3.1.2 Function Testing (HTTP API contracts) | **Complete** — see report (5 findings, all fixed & re-verified: 46/46) |
| 08 | [Selenium Functional Testing](08-Selenium-Functional-Testing/) | §3.1.3 User Interface Testing (Selenium) | **Complete** — see report (8/8) |
| 09 | [REST Assured API Integration Testing](09-RestAssured-API-Testing/) | §3.1.1/§3.1.2 Integration Testing (REST Assured) | **Complete** — see report (13/13) |
| 10 | [JMeter Basic Performance Testing](10-JMeter-Performance-Testing/) | §3.1.4/§3.1.5 Basic Performance Testing (JMeter) | **Complete** — see report |
| 11 | [OCR Vision Model vs Tesseract Evaluation](11-OCR-Vision-Model-Evaluation/) | none — see phase README | **Infrastructure ready** — awaiting real sample images |

Phases 08–10 map to the specific tool set assigned separately from the
sample plan (Selenium, REST Assured, JMeter) — each phase's own README
records that mapping and, where relevant, why the other tools in that
assignment (e.g. HP LoadRunner, BlazeMeter) weren't used.

Phase 11 doesn't map to the sample plan at all — it's an ML model-quality
comparison (naive OCR vs. a vision-language model), not a functional,
integration, performance, or security test. It follows the phase-folder
convention below purely for consistency.

Configuration testing (§3.1.8 in the sample plan) is not tracked as a
separate phase — Clario runs as a containerized web service, not a
multi-platform desktop client, so that phase does not apply the way it did
in the sample system.

## How results were produced

Every result in this folder comes from actually running the project's real
test suites (`pytest` for the two Python services, `vitest` for the
frontend, `playwright` for browser-driven UI/E2E) on 2026-09-03 and
2026-09-04 and capturing the unmodified console output. No numbers here
are estimated or fabricated — where a suite failed, the raw failure output
is kept alongside the analysis.

## Deliverables per phase (mirrors §4 of the sample plan)

Each populated phase folder contains, at minimum:
- **Raw test logs** — unedited tool output (`test-log.txt` / equivalent)
- **A written report** — scope, environment, pass/fail/skip counts, and for
  every failure: root cause and severity, not just "failed"
