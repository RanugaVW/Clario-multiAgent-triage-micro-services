# Clario — Multi-Agent Customer Support Triage System
### CS3501 Data Science and Engineering Project | Group 23

> **Clario** is an end-to-end AI-powered support triage platform. It classifies, routes, drafts, validates, and escalates customer support tickets using a **LangGraph multi-agent pipeline**, **ChromaDB RAG**, **SurrogateShield PII redaction**, **Gemma-3 1B LoRA fine-tuned models**, **Qwen2-VL OCR**, a **Spring Boot API Gateway**, and a **Next.js + Supabase** frontend.

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
6. [Architecture Reference](#6-architecture-reference)

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
│   ├── ocr-vision-service/          # Python FastAPI (Hosts Qwen2-VL 2B or Gemini Fallback)
│   └── ai-orchestrator-service/     # Python Background Worker (Consumes Redis, runs LangGraph)
├── docker-compose.yml               # Orchestrates all 6 microservices + Redis Broker
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

To start the backend infrastructure (Gateway, Ticket Core, Agent Review, NLP Classifier, OCR Vision, AI Orchestrator, Redis, and Proxy):

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
[ocr_node] — Calls http://ocr-vision-service:8000 for image extraction
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
| **API Gateway** | Spring Cloud Gateway MVC (Port 8080) |
| **Java Microservices**| Spring Boot 3.x (Ticket Core: 8081, Agent Review: 8082) |
| **Queue Broker** | Redis Alpine (Port 6380) |
| **Python Microservices**| FastAPI + Uvicorn (NLP Classifier: 8000, OCR Vision: 8001) |
| **AI Orchestrator** | Python 3.12 Background Worker consuming Redis via `app.worker` |
| **Local Models** | `Gemma-3-1b-it` (Classification), `Qwen2-VL-2B-Instruct` (OCR), `spaCy` (Redaction) |
| **Cloud Fallback** | Gemini API (`gemini-3.1-flash`) |
| **Database** | Supabase (PostgreSQL + Auth) |

---

*© 2026 Clario — Group 23, CS3501 Data Science and Engineering Project*
