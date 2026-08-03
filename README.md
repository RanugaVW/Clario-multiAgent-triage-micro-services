# Clario — Multi-Agent Customer Support Triage System
### CS3501 Data Science and Engineering Project | Group 23

> **Clario** is an end-to-end AI-powered support triage platform. It classifies, routes, drafts, validates, and escalates customer support tickets using a **LangGraph multi-agent pipeline**, **ChromaDB RAG**, **SurrogateShield PII redaction**, and a **Next.js + Supabase** frontend — all running **100% locally** with no cloud AI API required.

---

## Table of Contents
1. [Project Structure](#1-project-structure)
2. [Prerequisites](#2-prerequisites)
3. [Running the System — Step by Step](#3-running-the-system--step-by-step)
   - 3.1 [Supabase Setup](#31-supabase-database-setup)
   - 3.2 [ChromaDB + Knowledge Base](#32-chromadb--knowledge-base-setup)
   - 3.3 [ML Sidecar (Python / LangGraph)](#33-ml-sidecar-python--langgraph)
   - 3.4 [Frontend (Next.js)](#34-frontend-nextjs)
4. [How the Pipeline Works](#4-how-the-pipeline-works)
5. [User Roles & What Each Role Sees](#5-user-roles--what-each-role-sees)
6. [Known Prototype Limitations](#6-known-prototype-limitations)
7. [Architecture Reference](#7-architecture-reference)

---

## 1. Project Structure

```
clario/
├── frontend/                    # Next.js 14 UI (Triage, Admin, Agent pages)
│   └── src/app/
│       ├── page.tsx             # Customer triage page
│       ├── admin/page.tsx       # Admin dashboard (4 tabs)
│       └── agent/page.tsx       # Human agent review workspace
│
├── clario-ml-sidecar/           # Python FastAPI + LangGraph AI brain
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── graph/               # LangGraph nodes (14 nodes)
│   │   └── tools/
│   │       ├── local_llm.py     # Local classification + RAG synthesizer
│   │       ├── rag_tool.py      # ChromaDB retrieval
│   │       ├── llm_client.py    # Draft generation (local)
│   │       └── classification_tool.py  # Ticket classifier
│   └── vector_store/
│       ├── build_index.py       # KB ingestion script
│       └── kb_documents/        # Knowledge base markdown files
│           ├── technical/
│           └── billing/
│
├── clario-app/                  # Spring Boot API Gateway (production only)
├── ml_finetuning/               # QLoRA fine-tuning pipeline
├── docs/                        # Project spec documents
├── PROTOTYPE_CHANGES.md         # ← Deviations from spec (read this)
└── README.md                    # ← This file
```

---

## 2. Prerequisites

Install these before starting:

| Tool | Version | Download |
|---|---|---|
| **Node.js** | 18+ | https://nodejs.org |
| **Python** | 3.11+ | https://python.org |
| **Git** | Any | https://git-scm.com |

You also need a **Supabase project** (free tier is fine):
- Sign up at https://supabase.com
- Create a new project and keep note of your **Project URL** and **anon public key**

> **No Gemini API key needed.** The prototype runs fully locally.

---

## 3. Running the System — Step by Step

### 3.1 Supabase Database Setup

1. Go to your Supabase project → **SQL Editor**
2. Paste and run the following schema SQL (creates all required tables):

```sql
-- Users table (managed by Supabase Auth, extended with role)
create table if not exists public.users (
  id uuid references auth.users on delete cascade primary key,
  email text unique not null,
  role text not null default 'customer' check (role in ('customer', 'admin', 'agent')),
  created_at timestamptz default now()
);

-- Tickets
create table if not exists public.tickets (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.users(id) on delete set null,
  customer_name text,
  customer_email text,
  subject text,
  raw_text text not null,
  redacted_text text,
  status text not null default 'received'
    check (status in ('received','processing','resolved','escalated')),
  version integer not null default 1,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- AI classifications
create table if not exists public.ticket_classifications (
  id uuid default gen_random_uuid() primary key,
  ticket_id uuid references public.tickets(id) on delete cascade,
  category text,
  priority text,
  sentiment text,
  confidence float,
  routing_decision text,
  source text,
  created_at timestamptz default now()
);

-- Final resolutions
create table if not exists public.resolutions (
  id uuid default gen_random_uuid() primary key,
  ticket_id uuid references public.tickets(id) on delete cascade,
  final_response text,
  resolved_by text,
  escalated boolean default false,
  reasoning_summary text,
  created_at timestamptz default now()
);
```

3. Enable Row Level Security (RLS) and add policies in Supabase → **Authentication → Policies** (or disable RLS for local dev on `tickets`, `ticket_classifications`, `resolutions`).

4. In your Supabase project: **Authentication → Users** → create test accounts:
   - A **customer** account (regular email)
   - An **admin** account
   - Then run in SQL editor to set roles:
     ```sql
     update public.users set role = 'admin' where email = 'your-admin@email.com';
     update public.users set role = 'agent' where email = 'your-agent@email.com';
     ```

---

### 3.2 ChromaDB + Knowledge Base Setup

ChromaDB runs as an in-process store (no Docker needed). The knowledge base is a set of Markdown files.

**Step 1 — Set up the Python environment for the sidecar:**

```powershell
cd clario-ml-sidecar
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # Windows
# source .venv/bin/activate       # Mac/Linux

pip install -r requirements.txt
```

> ⚠️ First install will download `sentence-transformers` (~90MB). This only happens once.

**Step 2 — Add Knowledge Base Documents:**

The KB lives in `clario-ml-sidecar/vector_store/kb_documents/`. Add `.md` files to the domain folders:

```
vector_store/kb_documents/
├── technical/
│   ├── service_status.md        # e.g. "If video is unavailable, check status page..."
│   └── browser_support.md       # e.g. "Supported browsers: Chrome, Firefox, Edge..."
└── billing/
    ├── payment_issues.md        # e.g. "Failed payment refunds take 3-5 business days..."
    └── refund_policy.md
```

**Step 3 — Build the ChromaDB index:**

```powershell
# Still inside clario-ml-sidecar/ with .venv active
python vector_store/build_index.py
```

You should see output like:
```
Loaded 4 documents from kb_documents/
Built index: 12 chunks embedded into ChromaDB collection 'kb_support_docs'
```

---

### 3.3 ML Sidecar (Python / LangGraph)

**Step 1 — Create the environment file:**

```powershell
# In clario-ml-sidecar/
copy .env.example .env        # Windows
# cp .env.example .env        # Mac/Linux
```

Edit `.env`:
```env
# Supabase (for writing ticket results back to DB)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key-here

# Gemini API (OPTIONAL — pipeline works fully without this)
# GEMINI_API_KEY=AIza...

# Sidecar settings
CHROMA_PERSIST_DIR=./vector_store/chroma_data
KB_DOCUMENTS_DIR=./vector_store/kb_documents
```

> 💡 **The `GEMINI_API_KEY` is optional.** If not set, the pipeline uses the local keyword classifier and RAG synthesizer automatically.

**Step 2 — Start the sidecar:**

```powershell
# In clario-ml-sidecar/ with .venv active
uvicorn app.main:app --host 0.0.0.0 --port 8600 --reload
```

You should see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8600
```

**Verify it's working:**
```powershell
curl http://localhost:8600/health
# Should return: {"status":"healthy"}
```

---

### 3.4 Frontend (Next.js)

**Step 1 — Install dependencies:**

```powershell
cd frontend
npm install
```

**Step 2 — Create the environment file:**

```powershell
copy .env.local.example .env.local
```

Edit `.env.local`:
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
NEXT_PUBLIC_ML_SIDECAR_URL=http://localhost:8600
```

**Step 3 — Start the dev server:**

```powershell
npm run dev
```

Open **http://localhost:3000** in your browser.

---

### ✅ Everything Running Checklist

| Service | URL | Expected |
|---|---|---|
| ML Sidecar | http://localhost:8600/health | `{"status":"healthy"}` |
| Frontend | http://localhost:3000 | Clario triage page |
| Supabase | Your project dashboard | Tables visible |

---

## 4. How the Pipeline Works

When a customer submits a ticket, this is what happens:

```
Customer submits ticket text
        ↓
[Frontend] Saves raw ticket to Supabase → POST /process_ticket to ML Sidecar
        ↓
[cache_check_node] — Checks if a near-identical ticket was already resolved
        ↓ (cache miss)
[surrogate_node] — SurrogateShield masks all PII (names, emails, phone #s)
        ↓
[analyzer_node] — Semantic distillation: extract key complaint keywords
        ↓
[classification_node] — Classify: category (Technical/Billing/Account), priority, sentiment
        ↓
[routing_node] — Decide: technical_agent / billing_agent / both
        ↓
[specialist_agent] — RAG: query ChromaDB → retrieve top-4 KB chunks → synthesize response
        ↓
[validation_node] — Check: on_topic? grounded? appropriate_tone? policy violations?
        ↓ (if quality/misroute failure)
[reflection_node] → retry specialist (max 1 reroute, max 3 reflections)
        ↓ (if still failing)
[escalation_node] — Mark as escalated → human agent review
        ↓ (if passes validation)
[resolve_node] — Restore real PII from ShadowMap into the response
        ↓
[handoff_node] — Write final_response + classification to Supabase
        ↓
Frontend polls → displays AI response to customer
```

---

## 5. User Roles & What Each Role Sees

### 👤 Customer (`role = 'customer'`)
- **Page:** `http://localhost:3000`
- Submit a support ticket (text + ticket ID)
- See the AI-generated response after processing
- Click **"My Tickets"** button (top-left) → slide-in drawer showing all their tickets with Resolved ✅ / Pending ⏳ status

### 🛡️ Admin (`role = 'admin'`)
- **Page:** `http://localhost:3000/admin`
- **Tab 1 — AI Agents:** Overview of the 4 specialist agents and their capabilities
- **Tab 2 — Pipeline Nodes:** All 14 LangGraph nodes with their roles
- **Tab 3 — Human Review Queue:** All escalated tickets awaiting agent action
- **Tab 4 — All Tickets:** Every ticket ever submitted with raw text, classification chips, and final AI response

### 🧑‍💼 Agent (`role = 'agent'`)
- **Page:** `http://localhost:3000/agent`
- See escalated tickets assigned for human review
- Read the AI draft, RAG sources, and validation result
- Approve / Edit / Reject the draft
- Send the final response to the customer

---

## 6. Known Prototype Limitations

| Limitation | Production Fix |
|---|---|
| Frontend calls ML sidecar directly (no Spring Boot) | Wire Spring Boot gateway as the single entry point |
| Supabase instead of self-hosted PostgreSQL | Docker Compose with `postgres:16` |
| No optimistic locking (concurrent agent editing) | Spring Boot `@Version` JPA entity |
| RAG synthesizer instead of fine-tuned LLM | Valid Gemini API key OR QLoRA fine-tuned model |
| No email notification to customer | SMTP / SendGrid integration in handoff_node |

See **[PROTOTYPE_CHANGES.md](./PROTOTYPE_CHANGES.md)** for the full detailed comparison against the Feasibility Study, SRS, and SAD.

---

## 7. Architecture Reference

| Document | Location |
|---|---|
| Software Architecture Document (SAD) | `docs/SOFTWARE_ARCHITECTURE_DOCUMENT.md` |
| Software Requirements Specification (SRS) | `docs/Clario - Software Requirements Specification (1).pdf` |
| Feasibility Study | `docs/Feasibility Study - Clario Multi-Agent Customer Support Triage System (Group 23) (2).pdf` |
| Prototype Changes Log | `PROTOTYPE_CHANGES.md` |

### Tech Stack Summary

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind (light), Supabase JS SDK |
| Auth & DB | Supabase (PostgreSQL + Auth) |
| AI Orchestration | Python 3.11, FastAPI, LangGraph |
| RAG | ChromaDB, `sentence-transformers/all-MiniLM-L6-v2` |
| Local LLM | RAG template synthesizer (`local_llm.py`) |
| PII Redaction | SurrogateShield (`redaction_tool.py`) |
| Production Gateway | Spring Boot 3.x (`clario-app/`) — not used in prototype |

---

*© 2026 Clario — Group 23, CS3501 Data Science and Engineering Project*
