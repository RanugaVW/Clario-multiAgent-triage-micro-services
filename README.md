# Clario — Multi-Agent Customer Support Triage System
### CS3501 Data Science and Engineering Project | Group 23

> **Clario** is an end-to-end AI-powered support triage platform. It classifies, routes, drafts, validates, and escalates customer support tickets using a **LangGraph multi-agent pipeline**, **ChromaDB RAG**, **SurrogateShield PII redaction**, **Gemma-3 1B LoRA fine-tuned models**, **Gemini-powered OCR**, a **Spring Boot API Gateway**, and a **Next.js + Supabase** frontend.

---

## Table of Contents
1. [Project Structure (Microservices)](#1-project-structure-microservices)
2. [Prerequisites](#2-prerequisites)
3. [Running the System — Step by Step](#3-running-the-system--step-by-step)
   - 3.1 [Supabase Database Setup](#31-supabase-database-setup)
   - 3.2 [Environment Configuration](#32-environment-configuration)
   - 3.3 [Starting the Dockerized Backend Cluster](#33-starting-the-dockerized-backend-cluster)
   - 3.4 [Starting the Frontend](#34-starting-the-frontend)
4. [How the Pipeline Works](#4-how-the-pipeline-works)
5. [User Roles & What Each Role Sees](#5-user-roles--what-each-role-sees)
6. [Ticket Pipeline Tracer (Learning & Debugging Tool)](#6-ticket-pipeline-tracer-learning--debugging-tool)
7. [Architecture Reference](#7-architecture-reference)

---

## 🚀 Quick Start for Teammates

Welcome to the new Microservices architecture! To get the project running locally:

1. **Clone this new repository:**
   ```bash
   git clone https://github.com/RanugaVW/Clario-multiAgent-triage-micro-services.git
   cd Clario-multiAgent-triage-micro-services
   ```
2. **Configure your Environment Variables:** Follow **Section 3.2** below to create your `.env` files.
3. **Start the Backend Microservices (Java + Python + Redis):**
   ```bash
   docker compose up --build
   ```
4. **Start the Next.js Frontend (In a new terminal):**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

---

## 1. Project Structure (Microservices)

We have fully transitioned to an isolated **Enterprise Microservice Architecture** managed by Docker Compose.

```
clario/
├── frontend/                        # Next.js 14 UI (Triage, Admin, Agent pages)
├── services/
│   ├── api-gateway/                 # Spring Cloud Gateway MVC (Routes to internal Java services)
│   ├── ticket-core-service/         # Spring Boot (Handles Ticket DB + pushes to Redis)
│   ├── agent-review-service/        # Spring Boot (Handles Human Agent Review queues)
│   ├── nlp-classifier-service/      # Python FastAPI (Hosts Gemma-3-1b-it LoRA model)
│   └── ai-orchestrator-service/     # Python Background Worker (Consumes Redis, runs LangGraph; OCR via Gemini)
├── docker-compose.yml               # Orchestrates all 5 microservices + Redis Broker
└── supabase_schema.sql              # Supabase DB Schema
```

---

## 2. Prerequisites

Install these before starting:

| Tool | Version | Download |
|---|---|---|
| **Docker & Docker Compose** | Latest | https://docs.docker.com/get-docker/ |
| **Node.js** | 18+ | https://nodejs.org |

You also need a **Supabase project** (free tier is fine):
- Sign up at https://supabase.com
- Create a new project and keep note of your **Project URL** and **anon public key**.

---

## 3. Running the System — Step by Step

### 3.1 Supabase Database Setup

1. Go to your Supabase project → **SQL Editor**
2. Run the schema found in `supabase_schema.sql` (at the root of this project).
3. Create test accounts in Supabase Auth (Customer, Admin, Agent) and assign roles manually in the `users` table via the SQL editor.

---

### 3.2 Environment Configuration

You need to configure environment variables across three different locations.

**1. `frontend/.env.local`**
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
NEXT_PUBLIC_API_URL=http://localhost:8080
```

**2. `clario-app/.env`** (Used by the Java Microservices in Docker)
```env
DB_PASSWORD=your-supabase-db-password
JWT_SECRET=your-supabase-jwt-secret
SUPABASE_PROJECT_URL=https://your-project.supabase.co
```

**3. `clario-ml-sidecar/.env`** (Used by the Python Microservices in Docker)
```env
# Supabase Configuration
SUPABASE_PROJECT_URL=https://your-project.supabase.co
SUPABASE_SECRET_API=your-service-role-key-here

# LLM / Gemini Fallback Configuration
GEMINI_API_KEY=your-gemini-key
GEMINI_DRAFT_MODEL=gemini-3.1-flash-lite

# Local Vector Store (RAG)
CHROMA_PATH=./vector_store/chroma_data
```

---

### 3.3 Starting the Proxy and Dockerized Backend Cluster

The entire backend is orchestrated into 6 isolated Docker containers. Due to Docker networking limitations with IPv6-only Supabase databases, we run a transparent TCP proxy on the host machine to bridge the connection.

To start the backend infrastructure (Gateway, Ticket Core, Agent Review, NLP Classifier, AI Orchestrator, Redis, and Proxy):

1. Open a terminal at the root of the project.
2. Start the proxy script in the background:
```bash
kill -9 $(lsof -t -i:5433) 2>/dev/null; nohup python3 -u supabase_proxy.py > proxy_5433.log 2>&1 &
```
3. Build and launch the cluster:
```bash
docker compose up --build
```

*(Note: The AI models gracefully fall back to the Gemini API if they detect a lack of GPU VRAM on your system.)*

---

### 3.4 Starting the Frontend

The Next.js user interface runs natively on your machine (outside of Docker) so you can easily modify the UI.

Open a **new terminal tab**, navigate to the frontend directory, and start the server:

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to access the Clario platform!

---

## 4. How the Pipeline Works

When a customer submits a ticket, the microservice architecture executes as follows:

```
Customer submits ticket (Text + Optional Image)
        ↓
[Next.js Frontend] sends payload to [API Gateway (8080)]
        ↓
[API Gateway] proxies to [Ticket Core Service (8081)]
        ↓
[Ticket Core] pushes ticket into the [Redis Broker (6380)]
        ↓
[AI Orchestrator] pops ticket from Redis & triggers LangGraph
        ↓
[ocr_node] — Calls the Gemini API directly for image extraction
        ↓
[cache_check_node] — Checks ChromaDB precedent memory
        ↓
[surrogate_node] — spaCy NLP masks all PII locally
        ↓
[classification_node] — Calls http://nlp-classifier-service:8000 to predict Category/Priority
        ↓
[routing_node] — Routes to technical_agent, billing_agent, or both
        ↓
[specialist_agent] — RAG: queries ChromaDB → synthesizes response via API
        ↓
[validation_node] — Python Heuristics Judge checks for technical leaks
        ↓ (if passes validation)
[resolve_node] — Restores real PII into the final response
        ↓
[handoff_node] — Writes final_response to Supabase DB
```

Every node in that list emits a `started`/`finished` trace event when the **Ticket Pipeline Tracer** (Section 6) is switched on — that's the tool to reach for when you want to *see* this pipeline execute on a real ticket instead of only reading it as a diagram.

---

## 5. User Roles & What Each Role Sees

### 👤 Customer (`role = 'customer'`)
- Submit a support ticket.
- See the AI-generated response after processing with a beautiful split UI (Internal Technical Details vs. Customer Facing Output).

### 🛡️ Admin (`role = 'admin'`)
- View AI Agents and their capabilities.
- View all LangGraph Nodes and pipeline metrics.
- Access the Human Review Queue for all escalated tickets.

### 🧑‍💼 Agent (`role = 'agent'`)
- Manage escalated tickets assigned for human review.
- Read the AI draft, RAG sources, and validation result, and ultimately approve/reject the draft.

---

## 6. Ticket Pipeline Tracer (Learning & Debugging Tool)

A standalone visualizer, separate from the product, that answers one question in real time: **"where does *this* ticket actually go, right now, through the real system?"** It's built for learners and reviewers who want to watch the pipeline in Section 4 execute step-by-step against a live ticket, instead of only reading it as a diagram.

### 6.1 What It Is (and Isn't)

- **It lives outside the product**, in [`Visualizer/`](Visualizer/) — a small FastAPI relay ([`Visualizer/relay/`](Visualizer/relay/)) plus a static HTML viewer ([`Visualizer/viewer/index.html`](Visualizer/viewer/index.html)). Neither ships in `docker-compose.yml` or any production build.
- **It watches real tickets**, not synthetic ones — the 4 real services (frontend, `api-gateway`, `ticket-core-service`, `ai-orchestrator-service`) each fire a small HTTP event ("this step started/finished") at the relay as a real ticket passes through them.
- **It has a kill switch, and defaults to off.** Every emitting service reads its trace env var once at startup. When unset, tracing code paths are never even constructed (no HTTP client, no background tasks) — true zero overhead, not just "quiet." Toggling it requires restarting the service; there's no live on/off switch by design.
- **It never carries PII.** No raw ticket text, draft, or resolution ever reaches the relay — only structured summaries per step (category, priority, cache hit, RAG score, validation pass/fail, etc.). The one PII-adjacent step, `surrogate`, only ever reports the *fake* stand-in names it generated — never the customer's real values (see 6.4).

### 6.2 How a Trace Is Assembled

```
[Frontend] generates a correlationId, sends it on
POST /api/tickets as header: X-Trace-Correlation-Id
        │
        ├─► [Frontend]            fires "submit"              (keyed by correlationId)
        ├─► [API Gateway]         fires "received"             (keyed by correlationId)
        ├─► [Ticket Core Service] fires "persisted", "enqueued"
        │        (this is the one place both the correlationId AND the
        │         real ticket_id are known — the relay uses this event
        │         to fold the correlationId timeline into the real one)
        └─► [AI Orchestrator]     fires "started"/"finished" for every
                                   LangGraph node (see table below),
                                   then "visible_to_user" when done
```

All events for one ticket land in the relay keyed first by `correlationId`, then merged onto the real `ticket_id` the moment `ticket-core-service` persists the row — so the viewer shows one continuous timeline per ticket, from the instant it's submitted to the instant the response is visible to the customer.

### 6.3 What Each Step Reports

| Step | Detail shown |
|---|---|
| `cache_check` | whether ChromaDB precedent memory produced a cache hit |
| `surrogate` | PII **types** found (e.g. `person`), and the **fake** stand-in names generated — never the real ones |
| `classification` | predicted category, priority, sentiment, confidence |
| `routing` | `technical_agent` / `billing_agent` / both |
| `technical_agent` / `billing_agent` / `both_specialists` | RAG top score, low-relevance flag, reflection count per domain |
| `validation` | pass/fail, failure type |
| `reflection` | which retry attempt this is |
| `response_judge` | groundedness / overall score per domain |
| `escalation` | whether escalation triggered, and why |
| `handoff` | escalation + failure-type snapshot at handoff |
| `resolve` | whether the final response was produced, and **`pii_restored_count`** — how many fake stand-ins got swapped back for real customer values, proving the restoration half of the PII round-trip actually ran (again, never the values themselves) |

### 6.4 The PII Round-Trip, Made Visible

`surrogate_node` masks real names with fake stand-ins **before** anything reaches an LLM; `resolve_node` swaps them back **after** generation, right before the response reaches the customer. The tracer shows both halves without ever leaking a real value into the trace itself:

- `surrogate`'s `fake_stand_ins` proves masking happened (and shows what the LLM actually saw).
- `resolve`'s `pii_restored_count` proves restoration happened (and how many names were swapped back) — without repeating either the real or fake value a second time.

### 6.5 Running the Tracer — Full Command Reference

Tracing needs the relay + viewer running, plus each of the 4 real services restarted with its own trace env vars set. All ports below match the defaults already used elsewhere in this README.

**1. Start the relay** (new terminal, from the repo root):

```bash
cd Visualizer/relay
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8700
```

**2. Open the viewer** — it's a static page, no build step. Just open it directly in a browser:

```bash
open Visualizer/viewer/index.html        # macOS
xdg-open Visualizer/viewer/index.html    # Linux
```

(Or serve it, if your browser blocks `file://` fetches: `cd Visualizer/viewer && python3 -m http.server 8800`, then visit `http://localhost:8800`.)

**3. Turn tracing on in each real service, then restart it.** Nothing below is read live — each service only picks these up at startup.

- **Frontend** — add to `frontend/.env.local`:
  ```env
  NEXT_PUBLIC_TRACE_ENABLED=true
  NEXT_PUBLIC_TRACE_RELAY_URL=http://localhost:8700
  ```
  then restart: `cd frontend && npm run dev`

- **AI Orchestrator** (`clario-ml-sidecar` / `services/ai-orchestrator-service`) — add to its `.env`:
  ```env
  TICKET_TRACE_ENABLED=true
  TICKET_TRACE_RELAY_URL=http://localhost:8700
  ```
  then restart both its API process and its worker (`python -m app.worker`).

- **API Gateway** and **Ticket Core Service** — these read Spring properties `clario.tracing.enabled` / `clario.tracing.relay-url` (defaulted to `false` / `http://localhost:8700` in `application.properties`), overridable via env vars:
  ```env
  CLARIO_TRACING_ENABLED=true
  CLARIO_TRACING_RELAY_URL=http://localhost:8700
  ```
  Set these in each service's `.env` (or export them before launching), then restart both services.

**4. Submit a ticket** from the frontend as a customer, as usual (Section 3.4).

**5. Watch it live** in the viewer — the ticket appears in the list (initially under its correlation id, then merged into its real ticket id), click it, and its timeline fills in step-by-step as it moves through the pipeline in real time, ending at `visible_to_user`.

**To turn tracing back off:** unset the env vars above (or delete them from the `.env` files) and restart the 4 services. The relay and viewer can be left running or stopped independently — they only ever consume events, and produce nothing the real pipeline depends on.

---

## 7. Architecture Reference

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14, TypeScript, Tailwind, Supabase JS SDK |
| **API Gateway** | Spring Cloud Gateway MVC (Port 8080) |
| **Java Microservices**| Spring Boot 3.x (Ticket Core: 8081, Agent Review: 8082) |
| **Queue Broker** | Redis Alpine (Port 6380) |
| **Python Microservices**| FastAPI + Uvicorn (NLP Classifier: 8000) |
| **AI Orchestrator** | Python 3.12 Background Worker consuming Redis via `app.worker` |
| **Local Models** | `Gemma-3-1b-it` (Classification), `spaCy` (Redaction) |
| **Cloud Fallback** | Gemini API (`gemini-3.1-flash`) |
| **Database** | Supabase (PostgreSQL + Auth) |

---

*© 2026 Clario — Group 23, CS3501 Data Science and Engineering Project*
