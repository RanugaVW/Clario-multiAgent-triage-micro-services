# PROTOTYPE_CHANGES.md
## Clario — Prototype Deviations, Changes & Justifications
### Group 23 | August 2026

> This document records every deliberate change made to the prototype that deviates from or extends the original project specification documents:
> - **Feasibility Study** (Group 23, 2026)
> - **Software Requirements Specification (SRS)** v1
> - **Software Architecture Document (SAD)** v2.0

---

## 1. Did We Go Against the Spec?

**Short answer: No, not against — but significantly simplified for prototype delivery.**

The core architectural decisions (LangGraph state machine, RAG pipeline, ChromaDB, multi-agent routing, SurrogateShield PII redaction, Supabase persistence, validation node, escalation flow) are all fully implemented exactly as specified. What changed are the **external service integrations** and the **API Gateway layer**, both of which were simplified to make the prototype runnable without institutional cloud accounts or Java infrastructure.

---

## 2. Changes Made — Full Detail

---

### 2.1 🔴 Gemini API → Local LLM / Template-Based Synthesis

| | Spec (SAD § 8.2, SRS § 3.4) | Prototype |
|---|---|---|
| **Classification** | Google Gemini API (`gemini-2.0-flash`) via structured JSON prompt | Local keyword-based classifier + BART zero-shot (HuggingFace) |
| **Draft generation** | Gemini API specialist prompt → LLM response | RAG-synthesis template engine (instant, grounded) |
| **Validation judge** | Gemini API LLM judge (CoT JSON: on_topic, grounded, tone) | Local heuristic judge (keyword overlap + tone check) |

**Why changed:**
The Gemini API key provisioned for the project used a non-standard format incompatible with the `google-genai` Python SDK. All API calls returned `ClientError` (rate-limit/auth failure) after 3 retries, causing `draft=None` → `dependency_failure` escalation for every ticket. Rather than block the entire prototype on an API key fix, the pipeline was made **fully local and offline-capable**:

- The **classification** fallback (keyword-based) was already designed in `classification_tool.py` — it is now the primary path.
- **Draft generation** was replaced with a **RAG-context synthesizer** (`local_llm.py:generate_draft`). This extracts actionable sentences from ChromaDB retrieved chunks and formats a structured, professional support response. This is grounded (no hallucination possible), instant, and produces better output than `flan-t5-base` (which was tested and hallucinated for technical tickets).
- The **validation judge** was replaced with a local heuristic that checks keyword overlap between ticket text, draft, and retrieved context.

**What the spec says about this:** SAD §3 "Architectural Goals" explicitly states *"Ensure grounded, non-hallucinated responses via RAG with relevance thresholding."* — the prototype **meets this goal** via the template synthesizer. The Gemini dependency is an implementation detail, not an architectural requirement.

---

### 2.2 🔴 Spring Boot Gateway Bypassed → Direct Supabase from Frontend

| | Spec (SAD § 8.3, SRS § 2.2) | Prototype |
|---|---|---|
| **Auth** | Spring Boot JWT (SecurityConfig.java, AuthController.java) | Supabase Auth (email-password) |
| **Ticket persistence** | Spring Boot TicketController → TicketService → PostgreSQL via JDBC | Next.js frontend → Supabase JS SDK directly |
| **ML Sidecar trigger** | Spring Boot async thread → POST /process_ticket | Next.js `fetch()` → POST /process_ticket directly |
| **Optimistic locking** | Spring `@Version` JPA entity (409 Conflict on concurrent edit) | Not implemented in prototype |

**Why changed:**
The `clario-app` Spring Boot service exists in the codebase but is not integrated into the prototype demo flow. The frontend calls Supabase directly and the ML sidecar directly to enable rapid iteration and eliminate the need for a running JVM service. This is a **prototype-only simplification** — the Spring Boot gateway is architecturally required for production and exists in the `clario-app/` directory.

**SRS impact:** SRS FR-01 (ticket submission via authenticated REST endpoint) is partially met — auth exists via Supabase, but not via the Spring Boot JWT chain. SRS FR-09 (optimistic locking for concurrent agent edits) is **not implemented** in the prototype.

---

### 2.3 🟡 Mock Fallback Removed → Real Error Surfacing

| | Before (prototype bug) | After |
|---|---|---|
| **Backend unreachable** | Silently returned a hardcoded fake payload and saved it to Supabase | Throws a clear UI error telling the user exactly what to do |

**Why changed:**
The original prototype code had a `catch (fetchErr)` block that swallowed all network errors and returned a hardcoded mock response (`"billing"` category, fake summary). This caused every ticket submission to appear "resolved" in the DB even when the ML sidecar was not running — polluting the database with fake data. The fix surfaces the real error and gives actionable guidance.

---

### 2.4 🟡 UI: "My Tickets" Button and History Drawer

| | Spec (SRS FR-04) | Prototype |
|---|---|---|
| **Customer ticket history** | Customer can view their ticket history and resolution status | "My Tickets" slide-in drawer on user page |

**Why changed:**
The SRS specifies ticket history as a requirement. The original prototype showed only resolved tickets in a permanently visible bottom section (which hid pending tickets). Replaced with a **"My Tickets" button** in the header and a **slide-in drawer** showing all tickets with their AI responses and status badges (Resolved / Pending).

---

### 2.5 🟡 Admin Panel: "All Tickets" Tab Added

| | Spec (SRS FR-07, SAD § 8.4) | Prototype |
|---|---|---|
| **Admin visibility** | Admin sees all tickets, classifications, and resolutions | New "All Tickets" 4th tab in admin panel |

**Why changed:**
The SRS requires admin users to monitor all ticket states. The original admin panel had tabs for AI Agents, Pipeline Nodes, and Human Review Queue — but no flat view of all tickets. The new tab shows every ticket with: customer email, raw issue text, classification chips (category, priority, sentiment, confidence), final AI response or escalation reason, and a status badge.

---

### 2.6 🟢 Supabase Used Instead of Self-Hosted PostgreSQL

| | Spec (SAD § 7 Deployment) | Prototype |
|---|---|---|
| **Database** | PostgreSQL 16 in Docker Compose | Supabase (managed PostgreSQL + Auth + REST API) |

**Why changed:**
The spec calls for Docker Compose with a local `postgres:16` container. For the prototype, **Supabase** replaces this. The same schema tables exist (tickets, users, ticket_classifications, resolutions) — Supabase is just a managed host. This is **not a data model deviation**.

---

### 2.7 🟢 Frontend Connects Directly to ML Sidecar

| | Spec (SAD § 6 Process View) | Prototype |
|---|---|---|
| **Sidecar invocation** | Spring Boot async thread → POST /process_ticket (internal network) | Next.js browser → POST http://localhost:8600/process_ticket (direct) |

**Why changed:**
In production, the browser never talks to the sidecar directly — Spring Boot mediates. In the prototype, to avoid needing Spring Boot running, the Next.js frontend calls the sidecar directly. CORS is configured on the sidecar for `http://localhost:3000`.

---

### 2.8 🟢 LangGraph Graph — Fully Implemented Per Spec

The LangGraph state machine is **fully implemented as documented** in SAD § 9:

| Node | Spec | Status |
|---|---|---|
| `cache_check_node` | SAD § 9.2 | ✅ Implemented |
| `surrogate_node` (SurrogateShield) | SAD § 9.2 | ✅ Implemented |
| `analyzer_node` (Semantic Distillation) | SAD § 9.2 | ✅ Implemented |
| `classification_node` | SAD § 9.2 | ✅ Implemented (local fallback) |
| `routing_node` | SAD § 9.2 | ✅ Implemented |
| `technical_agent_node` (RAG) | SAD § 9.2 | ✅ Implemented |
| `billing_agent_node` (RAG) | SAD § 9.2 | ✅ Implemented |
| `both_specialists` (concurrent) | SAD § 9.2 | ✅ `asyncio.gather` |
| `validation_node` (EGC + Judge) | SAD § 9.2 | ✅ Local heuristic judge |
| `reflection_node` | SAD § 9.2 | ✅ Implemented |
| `escalation_node` | SAD § 9.2 | ✅ Implemented |
| `resolve_node` (PII restore) | SAD § 9.2 | ✅ Implemented |
| `handoff_node` | SAD § 9.2 | ✅ Implemented |

---

### 2.9 🟢 RAG Pipeline — Fully Implemented Per Spec

| Component | Spec | Status |
|---|---|---|
| Embedding model | `all-MiniLM-L6-v2` (SAD § 8.5) | ✅ Matches |
| Vector DB | ChromaDB, collection `kb_support_docs` | ✅ Matches |
| Chunking strategy | 300 tokens, 50 overlap | ✅ Matches |
| Score threshold | 0.30 | ✅ Matches |
| Top-k retrieval | k=4 | ✅ Matches |
| Domain filtering | `where: {domain: "technical"|"billing"}` | ✅ Matches |
| Circuit breaker | `chroma_rag` breaker with open/half-open states | ✅ Implemented |

---

## 3. Summary Table

| # | Change | Severity | Against Spec? | Reason |
|---|---|---|---|---|
| 2.1 | Gemini → local synthesis | 🔴 Major | No — implementation detail | API key auth failure; local is grounded & faster |
| 2.2 | Spring Boot bypassed | 🔴 Major | Prototype simplification only | Avoid JVM dependency for demo |
| 2.3 | Mock fallback removed | 🟡 Medium | Fix aligned with spec | Mock was corrupting the database |
| 2.4 | "My Tickets" drawer | 🟡 Medium | Extension of SRS FR-04 | Better UX, meets spec intent |
| 2.5 | Admin "All Tickets" tab | 🟡 Medium | Extension of SRS FR-07 | Admin visibility requirement |
| 2.6 | Supabase vs local PostgreSQL | 🟢 Minor | Same schema, different host | Easier dev setup for prototype |
| 2.7 | Frontend → sidecar direct | 🟢 Minor | Prototype-only pattern | No Spring Boot running |
| 2.8 | LangGraph state machine | — | ✅ Fully matches spec | — |
| 2.9 | RAG pipeline | — | ✅ Fully matches spec | — |

---

## 4. What Must Be Restored for Production

1. **Re-enable Spring Boot Gateway** as sole entry point (JWT auth, rate limiting, audit logging, IP filtering)
2. **Restore Gemini API** with a valid `AIza…` format key from [Google AI Studio](https://aistudio.google.com)
3. **Replace Supabase** with self-hosted PostgreSQL in Docker Compose (or keep Supabase with server-side service-role key)
4. **Remove direct CORS** on sidecar (all requests must come from Spring Boot's internal Docker network)
5. **Implement optimistic locking** in the agent review UI (SRS FR-09, SAD § 14.3)
6. **Wire Spring Boot async trigger** → `/process_ticket` instead of frontend direct call

---

*Last updated: 2026-08-03 | Author: Ranuga (Group 23)*
