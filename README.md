# Clario — Multi-Agent Customer Support Triage System
### CS3501 Data Science and Engineering Project | Group 23

> **Clario** is an end-to-end AI-powered support triage platform. It classifies, routes, drafts, validates, and escalates customer support tickets using a **LangGraph multi-agent pipeline**, **ChromaDB RAG**, **SurrogateShield PII redaction**, **Gemma-3 1B LoRA fine-tuned models**, **Qwen2-VL OCR**, a **Spring Boot API Gateway**, and a **Next.js + Supabase** frontend.

---

## Table of Contents
1. [Project Structure](#1-project-structure)
2. [Prerequisites](#2-prerequisites)
3. [Running the System — Step by Step](#3-running-the-system--step-by-step)
   - 3.1 [Supabase Database Setup](#31-supabase-database-setup)
   - 3.2 [ChromaDB + Knowledge Base](#32-chromadb--knowledge-base-setup)
   - 3.3 [Environment Configuration](#33-environment-configuration)
   - 3.4 [Starting All Services (VS Code or Bash)](#34-starting-all-services-vs-code-or-bash)
4. [How the Pipeline Works](#4-how-the-pipeline-works)
5. [User Roles & What Each Role Sees](#5-user-roles--what-each-role-sees)
6. [Architecture Reference](#6-architecture-reference)

---

## 1. Project Structure

```
clario/
├── frontend/                    # Next.js 14 UI (Triage, Admin, Agent pages)
├── clario-app/                  # Spring Boot API Gateway (Pushes tickets to Redis)
├── clario-ml-sidecar/           # Python ML Worker & FastAPI
│   ├── app/
│   │   ├── worker.py            # Redis Queue Consumer (Triggers LangGraph)
│   │   ├── main.py              # FastAPI entry point (Vector DB operations)
│   │   ├── graph/               # LangGraph nodes (14 nodes)
│   │   └── tools/
│   │       ├── local_llm.py     # Uses Gemma-3 1B LoRA & Gemini API for Drafting
│   │       ├── local_ocr.py     # Uses Qwen2-VL 2B (or Gemini Fallback) for Images
│   │       ├── rag_tool.py      # ChromaDB retrieval
│   │       └── redaction_tool.py # spaCy PII Anonymization
│   └── vector_store/            # RAG Documents and ChromaDB data
├── ml_finetuning/               # QLoRA fine-tuning pipeline
├── start-all.sh                 # GNOME bash script to start all services
├── .vscode/tasks.json           # VS Code native multi-terminal starter
└── docs/                        # Project spec documents
```

---

## 2. Prerequisites

Install these before starting:

| Tool | Version | Download |
|---|---|---|
| **Node.js** | 18+ | https://nodejs.org |
| **Python** | 3.11+ | https://python.org |
| **Java / Maven** | JDK 21+ | https://adoptium.net |
| **Redis** | 6+ | `sudo apt install redis-server` |

You also need a **Supabase project** (free tier is fine):
- Sign up at https://supabase.com
- Create a new project and keep note of your **Project URL** and **anon public key**

---

## 3. Running the System — Step by Step

### 3.1 Supabase Database Setup

1. Go to your Supabase project → **SQL Editor**
2. Run the schema found in `supabase_schema.sql` (at the root of this project).
3. Create test accounts in Supabase Auth (Customer, Admin, Agent) and assign roles manually in the `users` table via the SQL editor.

---

### 3.2 ChromaDB + Knowledge Base Setup

**Step 1 — Set up the Python environment for the ML Sidecar:**

```bash
cd clario-ml-sidecar
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> ⚠️ The first install will download massive local models (`sentence-transformers` for RAG, `Gemma-3-1b-it` for classification, `Qwen2-VL` for OCR). Ensure you have a stable internet connection and sufficient disk space.

**Step 2 — Build the ChromaDB index:**

```bash
python vector_store/build_index.py
```

---

### 3.3 Environment Configuration

You need to configure environment variables across three different folders.

**1. `frontend/.env.local`**
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
NEXT_PUBLIC_API_URL=http://127.0.0.1:8600
```

**2. `clario-app/src/main/resources/application.properties`**
Ensure your Spring Boot backend points to your Redis instance and database.
```properties
spring.data.redis.host=localhost
spring.data.redis.port=6379
```

**3. `clario-ml-sidecar/.env`**
```env
# Supabase Configuration
SUPABASE_PROJECT_URL=https://your-project.supabase.co
SUPABASE_SECRET_API=your-service-role-key-here

# LLM / Gemini Fallback Configuration
GEMINI_API_KEY=your-gemini-key
GEMINI_DRAFT_MODEL=gemini-3.1-flash-lite

# Local Vector Store
CHROMA_PATH=./vector_store/chroma_data
```

---

### 3.4 Starting All Services (VS Code or Bash)

The Clario platform consists of 4 distinct services that must run simultaneously:
1. **Frontend** (Next.js)
2. **Backend API Gateway** (Spring Boot)
3. **ML Worker** (Python script consuming the Redis queue)
4. **ML API** (Python FastAPI for Vector embeddings)

We provide two easy ways to start all 4 services at once:

**Option A: The VS Code Way (Recommended)**
1. Open this repository in VS Code.
2. Press `Ctrl + Shift + B` (or run the task "Start Clario System").
3. VS Code will instantly open 4 separate, dedicated terminal tabs for each service.

**Option B: The GNOME Desktop Script**
If you prefer floating terminal windows outside of your editor:
1. Open a terminal at the root of the project.
2. Run `./start-all.sh`
3. A new terminal will open with 4 neatly labeled tabs.

---

## 4. How the Pipeline Works

When a customer submits a ticket, the multi-agent architecture executes as follows:

```
Customer submits ticket (Text + Optional Image)
        ↓
[Next.js Frontend] sends payload to [Spring Boot Gateway]
        ↓
[Spring Boot] pushes ticket into the Redis `ticket_queue`
        ↓
[ML Worker (Python)] pops ticket from Redis & triggers LangGraph
        ↓
[ocr_node] — Uses Qwen2-VL locally (or Gemini fallback) to extract stack traces from images
        ↓
[cache_check_node] — Checks if a near-identical ticket was already resolved via ChromaDB precedent memory
        ↓
[surrogate_node] — spaCy NLP masks all PII (names, emails, phone #s, credit cards) locally
        ↓
[classification_node] — Local Gemma-3 1B LoRA predicts Category, Priority, and Customer Sentiment
        ↓
[routing_node] — Routes to technical_agent, billing_agent, or both
        ↓
[specialist_agent] — RAG: queries ChromaDB → retrieves internal docs → synthesizes response via API
        ↓
[validation_node] — Python Heuristics Judge checks for technical leaks, overcommitments, and groundedness
        ↓ (if quality/policy failure)
[reflection_node] → Retries specialist with critique (max 3 reflections)
        ↓ (if still failing or requires manual intervention)
[escalation_node] — Marks as escalated → sends to Human Agent Review Queue
        ↓ (if passes validation)
[resolve_node] — Restores real PII into the final response
        ↓
[handoff_node] — Writes final_response, RAG scores, and metadata to Supabase DB
        ↓
Frontend polls Supabase → Displays beautiful AI response to customer
```

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

## 6. Architecture Reference

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14, TypeScript, Tailwind, Supabase JS SDK |
| **API Gateway** | Java Spring Boot 3.x, Spring Data Redis |
| **Queue** | Redis (`ticket_queue`) |
| **AI Orchestration** | Python 3.12, FastAPI, LangGraph |
| **RAG** | ChromaDB, `sentence-transformers/all-MiniLM-L6-v2` |
| **Local Models** | `Gemma-3-1b-it` (Classification), `Qwen2-VL-2B-Instruct` (OCR), `spaCy` (Redaction) |
| **Cloud Fallback** | Gemini API (`gemini-3.1-flash-lite`) |
| **Database** | Supabase (PostgreSQL + Auth) |

---

*© 2026 Clario — Group 23, CS3501 Data Science and Engineering Project*
