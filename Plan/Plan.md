% Clario — Complete A-Z Implementation Plan
% Multi-Agent Customer Support Triage and Response System
% Group 23 — P04 — CS3501 Data Science and Engineering Project

# 0. How To Use This Document

.\.venv\Scripts\Activate.ps1
python -m pip install -r ml_finetuning\requirements.txt

This is the full build guide for Clario, written so that all three of you can open it and know exactly what to do, in what order, using what tool, and what to watch out for. It follows the system flow diagram (frontend → API Gateway → Supervisor Agent → Specialist Agents → Validation → Human Handoff → Closure/Learning) and the offline training pipeline (raw tickets → Gemini knowledge distillation → LoRA fine-tuning → evaluation).

Read it top to bottom once as a team. After that, each member should mainly live inside their own phase sections, but everyone should read Section 2 (tech stack), Section 4 (accounts/setup), and Section 15 (Docker) because those are shared.

Legend used throughout:
- **Do this on:** tells you which tool/website/app to actually open.
- **Watch out:** a concern specific to that step, including real-world production concerns, not just "make it work for the demo."
- **Copilot/Claude prompt:** a ready-to-paste prompt for your AI coding assistant (GitHub Copilot Chat, Claude Code, or Cursor) for that specific step.
- **README task:** what the agent (or you) should write into that component's `README.md` once the step is done.

---

# 1. Project Folder Structure (create this first, all members agree on it)

```
clario/
├── README.md                        <- top-level project overview
├── docker-compose.yml
├── .env.example
├── .gitignore
├── frontend/                        <- Member 3
│   ├── src/
│   │   ├── features/
│   │   │   ├── ticket-submission/
│   │   │   │   ├── types.ts
│   │   │   │   ├── components/
│   │   │   │   ├── hooks/
│   │   │   │   └── api.ts
│   │   │   ├── agent-review/
│   │   │   │   ├── types.ts
│   │   │   │   ├── components/
│   │   │   │   ├── hooks/
│   │   │   │   └── api.ts
│   │   │   └── auth/
│   │   ├── shared/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── package.json
│   └── README.md
├── api_gateway/                     <- Member 3
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   ├── auth/
│   │   ├── models/                  <- Pydantic schemas
│   │   ├── db/                      <- SQLAlchemy models + session
│   │   └── core/                    <- config, logging
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
├── agent_orchestration/             <- Member 2
│   ├── app/
│   │   ├── graph/                   <- LangGraph state graph definitions
│   │   │   ├── state.py
│   │   │   ├── supervisor_node.py
│   │   │   ├── routing_node.py
│   │   │   ├── validation_node.py
│   │   │   └── handoff_node.py
│   │   ├── agents/
│   │   │   ├── technical_agent/
│   │   │   ├── billing_agent/
│   │   │   └── shared/
│   │   ├── tools/
│   │   │   ├── redaction_tool.py
│   │   │   ├── rag_tool.py
│   │   │   └── classification_tool.py
│   │   └── main.py                  <- exposes graph as a callable service
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
├── ml_finetuning/                   <- Member 1
│   ├── data/
│   │   ├── raw/                     <- gitignored, never commit real ticket data
│   │   ├── distilled/
│   │   └── splits/
│   ├── notebooks/
│   │   ├── 01_eda.ipynb
│   │   ├── 02_distillation.ipynb
│   │   ├── 03_finetune_lora.ipynb
│   │   └── 04_evaluation.ipynb
│   ├── src/
│   │   ├── distillation/
│   │   │   ├── gemini_labeler.py
│   │   │   └── types.py
│   │   ├── training/
│   │   │   ├── train_lora.py
│   │   │   ├── dataset.py
│   │   │   └── config.yaml
│   │   ├── evaluation/
│   │   │   └── evaluate.py
│   │   └── inference/
│   │       └── serve.py             <- FastAPI wrapper around fine-tuned model
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
├── vector_store/                    <- Member 2, shared with Member 1's KB build
│   ├── build_index.py
│   ├── kb_documents/
│   └── README.md
├── infra/                           <- Member 3
│   ├── postgres/
│   │   └── init.sql
│   └── nginx/ (optional, if you front the demo with a reverse proxy)
├── scripts/
│   └── seed_demo_data.py
└── docs/
    ├── proposal.pdf                 <- your existing proposal
    ├── architecture_diagram.png     <- your existing flow diagram
    └── evaluation_report.md
```

**Watch out:** Never let `data/raw/` or `.env` get committed to Git. Add both to `.gitignore` on day one. Ticket data may contain real emails/names before redaction — treat it as sensitive even though it is a public Kaggle set, because your own added synthetic tickets (for demo variety) might not be.

**Copilot/Claude prompt to scaffold this:**
```
Create the following folder and empty-file structure exactly as given below, with a one-line placeholder
comment in every code file describing what will go there. Do not implement any logic yet.
[paste the tree above]
Also create a root .gitignore covering: node_modules, __pycache__, .venv, *.pyc, .env, data/raw/**,
*.ipynb_checkpoints, dist/, build/, .DS_Store, *.log, vector_store/kb_documents/**local**
```

---

# 2. Complete Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | React + TypeScript + Vite | Fast dev server, standard for undergrad projects, works cleanly with Docker |
| Frontend styling | Tailwind CSS | Fast to build a clean ticket form + review screen |
| API Gateway | FastAPI (Python) | Matches your proposal, async, auto-generates OpenAPI docs |
| Auth | FastAPI + JWT (python-jose) or Supabase Auth (optional shortcut) | Simple bearer-token auth is enough for an academic demo |
| Orchestration | LangGraph (Python) | Matches your proposal, explicit state graph, supports loops |
| LLM API (reasoning calls: specialist drafting, LLM-as-judge) | One provider: **Anthropic Claude API** or **Google Gemini API** (pick ONE as your "external LLM provider" for anything that is not the fine-tuned model) | Your proposal says "one LLM API for reasoning calls" |
| Knowledge distillation teacher | **Google Gemini API** (Gemini 2.x Flash is cheapest and fastest for bulk labelling 200K rows — you will only label a sampled subset, not all 200K, see Section 8) | You already committed to Gemini in your proposal |
| Fine-tuned student model | Llama-3-8B-Instruct or Mistral-7B-Instruct (open-weight) | Matches your proposal |
| Fine-tuning method | LoRA / QLoRA via HuggingFace PEFT + bitsandbytes | Matches your proposal |
| Fine-tuning compute | Google Colab Pro (A100/L4) or Kaggle Notebooks (free T4/P100 x2) | You are undergrads — free/cheap GPU matters. Kaggle gives 30h/week free GPU |
| Redaction | Python `re` (regex) + spaCy `en_core_web_sm` or `en_core_web_trf` NER | Matches your proposal |
| RAG vector store | ChromaDB (simplest to run in Docker, persists to disk) | Matches your proposal; Chroma has less operational overhead than FAISS for a small KB |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (fast, small) or `text-embedding-3-small` if using an API embedding model | Matches your Closure & Learning step |
| Relational DB | PostgreSQL 16 | Matches your proposal — tickets, logs, resolutions |
| ORM | SQLAlchemy 2.0 + Alembic (migrations) | Standard, avoids hand-written SQL drift |
| Containerization | Docker + Docker Compose | Matches your proposal |
| Experiment tracking (optional but recommended) | Weights & Biases (free academic tier) | Lets you show training curves in your report/demo |
| Tracing (optional, "if time permits" per proposal) | LangSmith free tier | Debug LangGraph runs visually |
| Version control | Git + GitHub (private repo, add mentor/TA as collaborator if asked) | — |
| CI (optional but good practice) | GitHub Actions — lint + basic tests on push | Shows engineering maturity in your report |
| Package/dependency mgmt | `pip` + `requirements.txt` per service (or `poetry` if your team prefers) | Simplicity for a 3-person team |
| Node package manager | `npm` (Vite default) | — |

**Watch out — cost control:** Gemini API calls for labelling 200K tickets would cost real money and take a long time. Do NOT label all 200K rows. Sample 5,000–15,000 tickets stratified by category (Section 8 explains exactly how). This is both cheaper and defensible in your report as "we distilled from a representative sample, not the full corpus, for cost and time reasons."

**Watch out — API keys:** Every API key (Gemini, Claude/OpenAI, W&B, LangSmith) goes into `.env`, never into code, never into a notebook cell that gets committed. Use `python-dotenv` locally and Docker secrets / environment variables in `docker-compose.yml` for deployment.

---

# 3. Team Roles Recap (from your proposal, kept identical)

| Member | Owns |
|---|---|
| **Member 1** (WETTASINGHE V.N.) | Data engineering, PII masking of the dataset, EDA, train/val/held-out split, Gemini knowledge distillation, LoRA/QLoRA fine-tuning, evaluation vs baseline |
| **Member 2** (WEERASEKARA R.V.) | Supervisor Agent + LangGraph orchestration, routing logic, Technical & Billing specialist agents, RAG tool, validation step, human-handoff rules, agent-level evaluation |
| **Member 3** (WICKRAMARATNA S.I.P.) | FastAPI gateway, PostgreSQL logging layer, React frontend (ticket form + agent review screen), Docker Compose, stretch-goal Rysera Stem LMS integration, symposium demo deployment |

Each phase section below is labelled with the responsible member, but Phase 0 (accounts/setup) and Phase 9 (integration) are shared.

---

# 4. Phase 0 — Accounts, Tools, and Local Environment Setup (ALL MEMBERS, Week 1)

Do these once, together, on a call if possible, so all three of you have the same environment.

### 4.1 Accounts to create (websites to visit)

1. **GitHub** — https://github.com — create the team repo `clario` (private), add all 3 members + mentor/TA as collaborators.
2. **Kaggle** — https://www.kaggle.com — needed for (a) downloading the Customer Support Tickets Dataset, (b) free GPU notebooks for fine-tuning.
3. **Google AI Studio** — https://aistudio.google.com — get a **Gemini API key** (free tier is enough for a sampled distillation run). This is Member 1's key mainly, but store it as a shared team `.env.example` placeholder.
4. **Anthropic Console** (if you pick Claude as your "external LLM provider") — https://console.anthropic.com — get a Claude API key. OR **OpenAI Platform** — https://platform.openai.com — if you pick GPT instead. Pick ONE provider only, per your own architecture table.
5. **HuggingFace** — https://huggingface.co — create an account, generate an access token (Settings → Access Tokens) to download Llama-3-8B or Mistral-7B weights (Llama requires accepting Meta's license on the model page first).
6. **Weights & Biases** (optional but recommended) — https://wandb.ai — free academic account for training curves.
7. **LangSmith** (optional) — https://smith.langchain.com — free tier for tracing LangGraph runs.
8. **Docker Hub** — https://hub.docker.com — create an account (needed if you want to push images, optional if you only run locally).
9. **Google Colab** — https://colab.research.google.com — backup GPU option if Kaggle's weekly quota runs out.

### 4.2 Local tools to install (every member's laptop)

- **VS Code** — https://code.visualstudio.com — this is your main coding tool for the whole project (frontend, backend, orchestration code). Install extensions: Python, Pylance, ESLint, Prettier, Docker, GitHub Copilot (or use Claude Code / Cursor if your team prefers — either works, the prompts in this doc work in any of them).
- **Python 3.11** — https://www.python.org/downloads/
- **Node.js 20 LTS** — https://nodejs.org
- **Docker Desktop** — https://www.docker.com/products/docker-desktop — needed for Section 15.
- **Git** — https://git-scm.com
- **Postman** or **Insomnia** (optional, for manually testing the FastAPI endpoints) — https://www.postman.com

### 4.3 Where each member works day to day

- **Member 1**: mostly **Kaggle Notebooks** or **Google Colab** (for GPU access during fine-tuning), then VS Code for the `ml_finetuning/` service code (data loaders, inference server) once training scripts are finalized.
- **Member 2**: VS Code, running the LangGraph app locally with `uvicorn`/plain Python, calling real APIs (Gemini/Claude) against a locally running Chroma instance.
- **Member 3**: VS Code, running `docker compose up` for the full stack once services exist, and the Vite dev server (`npm run dev`) for fast frontend iteration.

### 4.4 `.env.example` (commit this, never commit the real `.env`)

```
# --- LLM providers ---
GEMINI_API_KEY=
LLM_PROVIDER=anthropic          # or "openai"
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# --- HuggingFace ---
HF_TOKEN=

# --- Database ---
POSTGRES_USER=clario
POSTGRES_PASSWORD=changeme
POSTGRES_DB=clario_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://clario:changeme@postgres:5432/clario_db

# --- Vector store ---
CHROMA_HOST=vector_store
CHROMA_PORT=8000

# --- Auth ---
JWT_SECRET=change-this-in-real-deployment
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# --- Observability (optional) ---
WANDB_API_KEY=
LANGCHAIN_API_KEY=
LANGCHAIN_TRACING_V2=false

# --- Service URLs (used by docker-compose network) ---
FINE_TUNED_LLM_URL=http://ml_finetuning:8500
ORCHESTRATION_URL=http://agent_orchestration:8600
API_GATEWAY_URL=http://api_gateway:8000
```

**Watch out:** `JWT_SECRET` and `POSTGRES_PASSWORD` above are placeholders. For your symposium demo you don't need production-grade secrets management, but do NOT reuse a real personal password, and rotate the Gemini/Claude key if it is ever accidentally pushed to GitHub (GitHub will actually auto-revoke many known key patterns if it detects them in a public push — but your repo is private, so it won't, so be extra careful).

---

# 5. Data Flow Recap (from your diagram, so everyone builds to the same contract)

```mermaid
flowchart TD
    A[Customer submits ticket] --> B[Frontend: Ticket Form]
    B -->|HTTPS POST /tickets| C[API Gateway - FastAPI]
    C --> D{Authenticated request?}
    D -->|No| E[Return 401]
    D -->|Yes| F[Write raw ticket to PostgreSQL]
    F --> G[Supervisor Agent - LangGraph]
    G --> H[Redaction Tool: regex + spaCy NER]
    H --> I{PII detected?}
    I -->|Yes| J[Mask PII in ticket text]
    I -->|No| K[Call fine-tuned LLM - inference only]
    J --> K
    K --> L[Category, Priority, Sentiment predicted]
    L --> M{Route decision}
    M -->|Technical| N[Technical Specialist Agent]
    M -->|Billing| O[Billing Specialist Agent]
    M -->|Both, low confidence| P[Dispatch to both]
    N --> Q[RAG retrieval + draft response]
    O --> Q
    P --> Q
    Q --> R[Validation Step: policy checklist + LLM-as-judge]
    R -->|Fails| S[Send back for re-draft/flag]
    R -->|Passes| T{Escalation trigger?}
    T -->|No| U[Auto-send drafted response]
    T -->|Yes| V[Human Handoff package]
    V --> W[Human Agent Review Screen]
    W --> X[Human approves/edits/rejects]
    X --> Y[Send final response to customer]
    U --> Z[Closure and Learning Step]
    Y --> Z
    Z --> AA[Embed resolved case]
    AA --> AB[Store in vector store as precedent memory]
    Z --> AC[Log resolution + metrics to PostgreSQL]
    AC --> AD[Ticket closed]
```

This is the contract every service must respect. If any member changes a field name or a step, update this diagram in `docs/architecture_diagram.png` and tell the other two immediately — this is the #1 real-world failure mode in small teams (silent contract drift between services).

---

# 6. Phase 1 — Data Engineering (Member 1, Weeks 1–2)

### Step 1.1 — Download the dataset

**Do this on:** Kaggle website → search "Customer Support Tickets Dataset 200K" → download, OR use the Kaggle CLI from VS Code terminal:
```bash
pip install kaggle
# place kaggle.json (from Kaggle account settings -> API -> Create New Token) in ~/.kaggle/
kaggle datasets download -d <dataset-owner>/<dataset-slug> -p ml_finetuning/data/raw
unzip ml_finetuning/data/raw/*.zip -d ml_finetuning/data/raw
```
**Watch out:** Confirm the exact Kaggle dataset slug matches the one cited in your proposal (Section 8, reference 7). Different "Customer Support Tickets" datasets exist on Kaggle with different columns — use the same one you cited or your report and dataset link will not match.

### Step 1.2 — Exploratory Data Analysis (EDA)

**Do this on:** Kaggle Notebook or local Jupyter in VS Code (`notebooks/01_eda.ipynb`).
Check: row count, missing values, column types, class balance for category/priority/sentiment (if labels already exist in the raw data) or just ticket-topic keyword distribution if not, text length distribution, duplicate tickets, language distribution (are all tickets English?).

**Copilot/Claude prompt:**
```
I have a pandas DataFrame `df` loaded from a customer support tickets CSV. Write an EDA script that:
1. Prints shape, dtypes, and missing-value counts per column
2. Plots a bar chart of ticket count per existing category/label column if one exists
3. Plots a histogram of ticket text length (in words)
4. Flags exact-duplicate rows and near-duplicate rows (using a simple text hash + optional fuzzy check)
5. Detects likely non-English rows using langdetect, and reports what % of the dataset that is
6. Saves a short markdown summary of all findings to notebooks/eda_summary.md
Keep the script under 200 lines, in a single file src/distillation/eda.py, with clear function boundaries.
```

**Watch out:** If class labels do NOT already exist in the raw Kaggle data (many ticket datasets are just free text + maybe a subject line), your Gemini distillation step (Section 8) is not optional polish — it IS your labelling step, so plan time for it early, not at the end.

### Step 1.3 — PII masking of the raw dataset (before it ever touches disk long-term or gets uploaded anywhere)

This is separate from the runtime Redaction Tool (Section 10) that Member 2 builds — this is a one-time cleaning pass over your training data so you are not fine-tuning a model on, or storing, real customer PII.

**Do this on:** VS Code, `ml_finetuning/src/distillation/pii_clean.py`.

**Copilot/Claude prompt:**
```
Write a Python module that masks PII in a text column of a pandas DataFrame using:
1. Regex patterns for: emails, phone numbers (multiple international formats), credit-card-like
   16-digit sequences, IP addresses
2. spaCy en_core_web_sm NER for PERSON, GPE, ORG entity types, replacing them with placeholder
   tokens like [PERSON], [LOCATION], [ORG]
Replace matches with clear placeholder tokens, not blank strings, so downstream tokenization doesn't
break. Return both the cleaned DataFrame and a report dict counting how many of each PII type were found,
so we can report PII-masking precision/recall later on a manually spot-checked sample. Keep this under
250 lines split into pii_patterns.py (regex) and pii_clean.py (orchestration + spaCy).
```

**README task:** `ml_finetuning/src/distillation/README.md` should explain: what PII types are masked, what placeholder tokens are used, and that this is a ONE-TIME dataset cleaning step, distinct from the live Redaction Tool used at inference time (link to `agent_orchestration/app/tools/redaction_tool.py`'s README so nobody confuses the two).

**Watch out:** spaCy NER is not perfect — it will miss some names and occasionally mask non-PII text (e.g., a product name that looks like a person's name). Don't claim 100% masking in your report; report the manual spot-check precision/recall your proposal already promises (Section 5, "Redaction Tool" row).

### Step 1.4 — Train / Validation / Held-out Test split

**Do this on:** same notebook/script, `ml_finetuning/src/training/config.yaml` holds the split ratios.

**Copilot/Claude prompt:**
```
Write a function split_dataset(df, label_col, train_frac=0.7, val_frac=0.15, test_frac=0.15, seed=42)
that performs a STRATIFIED split on label_col (so class balance is preserved across splits), saves
three parquet files to data/splits/train.parquet, val.parquet, test.parquet, and writes a
data/splits/split_manifest.json recording the row counts, class distribution per split, and the
random seed used, so the split is fully reproducible and auditable.
```

**Watch out — this is the single most important rule in your whole evaluation plan:** once `test.parquet` is written, it is locked. No one — not even to "just peek" — touches it again until final evaluation (Section 9). Put a big warning comment at the top of that file's directory and consider `chmod 444 data/splits/test.parquet` locally to physically prevent accidental overwrites.

---

# 7. Phase 2 — Gemini Knowledge Distillation (Member 1, Weeks 2–3)

This is how you generate category/priority/sentiment labels using Gemini as the "teacher," which your smaller open-weight model then learns to imitate (the "student").

### Step 2.1 — Decide the label schema first, in writing, before calling any API

Example schema (adjust to your dataset):
- `category`: {Technical, Billing, Account, General, Other}
- `priority`: {Low, Medium, High, Urgent}
- `sentiment`: {Positive, Neutral, Negative, Strongly Negative}

**Watch out:** Lock this schema BEFORE running distillation on thousands of rows. Changing the schema after 5,000 Gemini calls means re-running (and re-paying for) all of them.

### Step 2.2 — Sample the dataset for distillation

Do NOT distil all 200K rows. Stratified-sample ~5,000–15,000 rows (balanced across whatever proxy category signal you found in EDA, e.g., product area or subject keywords) so your fine-tuning set has enough examples per class without excessive API cost.

### Step 2.3 — Write the Gemini labelling script

**Do this on:** VS Code, `ml_finetuning/src/distillation/gemini_labeler.py`. Get the API key from **Google AI Studio** (https://aistudio.google.com).

**Copilot/Claude prompt:**
```
Write a Python script using the google-genai SDK that calls Gemini (model: gemini-2.5-flash) to label
customer support tickets. Requirements:
1. Read a sampled parquet file of raw ticket text
2. For each ticket, send a prompt that asks Gemini to return ONLY a JSON object with keys
   "category", "priority", "sentiment", "reasoning" (short justification), using the fixed label
   schema I provide as a system instruction
3. Use structured output / response_schema (JSON mode) so responses are always parseable JSON,
   not free text needing regex extraction
4. Batch requests with async concurrency (max 5 concurrent) and exponential backoff retry on
   rate-limit errors
5. Cache every response to disk (data/distilled/cache/{ticket_id}.json) immediately after each
   successful call, so a crash halfway through does not lose already-labelled data and does not
   re-spend API credits on already-done rows
6. Log a running cost estimate (tokens used * price) to the console every 100 rows
7. At the end, merge all cached JSON files into a single data/distilled/distilled_dataset.parquet
Keep this under 300 lines, split into gemini_client.py (API wrapper) and label_runner.py (orchestration
+ caching + merging).
```

**Watch out — real-world concerns:**
- **Cost:** even Gemini Flash pricing adds up over thousands of calls. Set a hard budget alert in Google AI Studio if available, and test on 20 rows first before running the full sample.
- **Rate limits:** free tier has strict requests-per-minute limits. Concurrency of ~5 with backoff, as in the prompt above, avoids hard failures.
- **Non-determinism:** Gemini may occasionally return malformed JSON even with JSON mode. Always wrap parsing in try/except and log failed rows to `data/distilled/failed_rows.json` for a manual re-run pass, don't let one bad row kill the whole batch.
- **Label quality:** spot-check ~50 Gemini labels yourself as a team before trusting the rest — if Gemini is systematically getting something wrong (e.g., always over-predicting "Urgent"), fix your prompt instructions before labelling thousands more rows.

**README task:** `ml_finetuning/src/distillation/README.md` gets a small diagram:
```mermaid
flowchart LR
    A[Sampled raw tickets] --> B[Gemini API - JSON mode]
    B --> C[Cache per-ticket JSON]
    C --> D[Merge to distilled_dataset.parquet]
    D --> E[Feeds Phase 3: LoRA fine-tuning]
```
Explain the label schema, the sampling strategy, the approximate cost of the run, and where failed rows are logged.

---

# 8. Phase 3 — LoRA/QLoRA Fine-Tuning (Member 1, Weeks 3–5)

### Step 3.1 — Choose base model

Start with **Mistral-7B-Instruct-v0.3** or **Llama-3-8B-Instruct** (Llama requires accepting the license on its HuggingFace model page first, under your HF account). Mistral has no gated-access step, which is simpler if you're short on time.

### Step 3.2 — Prepare the training format

Convert `distilled_dataset.parquet` into instruction-tuning format (prompt/response pairs), where the "response" is the Gemini-generated JSON label. This is the actual "knowledge distillation" — the small model learns to reproduce Gemini's structured judgments.

**Copilot/Claude prompt:**
```
Write a Python module dataset.py that converts a parquet file with columns [ticket_text, category,
priority, sentiment] into HuggingFace Dataset objects formatted as instruction-following examples for
LoRA fine-tuning, using this template:

### Instruction:
Classify the following customer support ticket. Return only JSON with keys category, priority, sentiment.

### Ticket:
{ticket_text}

### Response:
{"category": "...", "priority": "...", "sentiment": "..."}

Split into train/val using the manifest from split_dataset (Section 6.4), tokenize with the target
model's tokenizer, and return DataLoaders. Keep under 200 lines.
```

### Step 3.3 — Write the LoRA training script

**Do this on:** Kaggle Notebook (free GPU) or Colab Pro, then move the finalized script into `ml_finetuning/src/training/train_lora.py` in VS Code for version control.

**Copilot/Claude prompt:**
```
Write a LoRA fine-tuning script using HuggingFace transformers + peft + bitsandbytes for
Mistral-7B-Instruct-v0.3, with:
1. 4-bit quantized loading (QLoRA) via BitsAndBytesConfig for memory efficiency on a single T4/A100
2. LoRA config: r=16, lora_alpha=32, target_modules for the model's attention projections,
   lora_dropout=0.05
3. Trainer setup with gradient accumulation, mixed precision, a cosine LR schedule, and
   checkpointing every N steps to survive Kaggle/Colab session timeouts
4. Weights & Biases logging of train/val loss if WANDB_API_KEY is set, otherwise fall back to
   local CSV logging (do not crash if the key is missing)
5. Save the final LoRA adapter weights (not the full model) to a specified output directory
All config values (r, alpha, learning rate, epochs, batch size) should live in config.yaml, not
hardcoded, so we can re-run experiments by editing one file. Keep the script under 250 lines.
```

**Watch out — real production/training concerns:**
- **Session timeouts:** Kaggle notebooks disconnect after ~9–12 hours and free Colab can disconnect earlier. Checkpoint frequently (every 200–500 steps) so you can resume, not restart from zero.
- **Class imbalance:** if "Urgent" or "Strongly Negative" are rare classes, consider class-weighted loss or oversampling — otherwise your model will just always predict the majority class and still look decent on raw accuracy while failing macro-F1 (which your proposal explicitly promises to measure — good, that's the right metric to catch this).
- **Overfitting on a small distilled sample:** with only ~5–15K distilled examples, watch validation loss carefully; stop training (early stopping) if val loss starts rising while train loss keeps falling.
- **Save adapters, not merged weights,** during experimentation — smaller files, faster iteration, and you can swap adapters without re-downloading the 7–8B base model each time.

**README task:** `ml_finetuning/src/training/README.md`:
```mermaid
flowchart LR
    A[Distilled dataset] --> B[Train/Val split]
    B --> C[QLoRA fine-tuning - Mistral-7B]
    C --> D[LoRA adapter weights saved]
    D --> E[Evaluation vs non-fine-tuned baseline]
```
Document the exact hyperparameters used in the final run, GPU used, training time, and where checkpoints are stored (should be gitignored — too large for GitHub; use HuggingFace Hub private repo or Google Drive for adapter weight backups instead).

### Step 3.4 — Evaluate against the non-fine-tuned baseline

**Do this on:** VS Code / notebook, `ml_finetuning/src/evaluation/evaluate.py`, run ONCE on the locked held-out test set from Section 6.4.

**Copilot/Claude prompt:**
```
Write an evaluation script that:
1. Loads the locked held-out test set (never seen during training)
2. Runs inference with (a) the fine-tuned LoRA model and (b) the same base model with NO adapter
   (zero/few-shot baseline), using an identical prompt template for both
3. Computes accuracy and macro-F1 separately for category, priority, and sentiment for both models
4. Saves a results table as markdown and as a matplotlib bar chart comparing the two models
   side by side per task
5. Also computes a simple JSON-validity rate (did the model even return parseable JSON) for both,
   since that itself is a meaningful metric for a small model doing structured output
Keep under 200 lines.
```

**Watch out:** Run this exactly once per model version you want to report, and log the exact adapter checkpoint used. Do not "peek and retrain" repeatedly against the held-out set — if you need more iteration, iterate against the validation set, and only touch held-out test at the very end.

### Step 3.5 — Serve the fine-tuned model as a callable inference service

**Do this on:** VS Code, `ml_finetuning/src/inference/serve.py`.

**Copilot/Claude prompt:**
```
Write a small FastAPI service that loads the base model + LoRA adapter once at startup (not per
request), exposes a single POST /classify endpoint accepting {"ticket_text": str} and returning
{"category": str, "priority": str, "sentiment": str, "raw_model_output": str}. Include:
1. A Pydantic request/response model in a separate models.py file
2. Basic input validation (reject empty or >4000-character ticket_text with a 422)
3. A model-load health check at GET /health
4. Structured logging of inference latency per request
Keep main.py under 150 lines; put model-loading logic in model_loader.py.
```

**Watch out:** This service must be inference-only in production — never re-triggers training. Keep the training scripts and this serving script in clearly separate files so nobody accidentally wires a training call into the live request path (this is exactly what your diagram is careful to separate — "loaded into" the Supervisor Agent, not "trains inside" it).

---

# 9. Phase 4 — Supervisor Agent & LangGraph Orchestration (Member 2, Weeks 2–4, can run in parallel with Member 1's work using a MOCK classification tool until the real fine-tuned model is ready)

### Step 4.1 — Install and learn LangGraph basics

**Do this on:** VS Code. Read https://langchain-ai.github.io/langgraph/ (official docs) first — specifically the "state graph" and "conditional edges" concepts, since your Supervisor needs branching logic (route to Technical vs Billing vs Both).

```bash
pip install langgraph langchain langchain-anthropic  # or langchain-google-genai
```

### Step 4.2 — Define the shared graph state

**Copilot/Claude prompt:**
```
Define a TypedDict (or Pydantic model) TicketState for a LangGraph state graph representing a
customer support ticket moving through: redaction -> classification -> routing -> specialist
drafting -> validation -> escalation decision -> closure. Fields needed: ticket_id, raw_text,
redacted_text, pii_found (list), category, priority, sentiment, routing_decision
(Literal["technical","billing","both"]), agent_drafts (dict[str,str]), validation_result
(dict with passed: bool, reasons: list[str]), escalation_triggered: bool, final_response,
human_review_notes. Put this in agent_orchestration/app/graph/state.py, under 80 lines, with
docstrings explaining what writes to and reads from each field, since this state dict is the
"shared blackboard" our whole team depends on — do not let any node write to a field it doesn't own.
```

**Watch out:** This is the exact "shared blackboard" concept your proposal cites (Section 4.3, blackboard architecture reference). Treat `state.py` as a contract file — any change here must be communicated to Member 3 (who reads this state to log to Postgres) immediately.

### Step 4.3 — Build the Redaction Tool node

**Do this on:** VS Code, `agent_orchestration/app/tools/redaction_tool.py`.

**Copilot/Claude prompt:**
```
Write a redaction tool function mask_pii(text: str) -> tuple[str, list[dict]] that:
1. Uses regex for emails, phone numbers, credit-card-like numbers
2. Uses spaCy en_core_web_sm NER for PERSON, GPE, ORG
3. Returns the masked text AND a list of dicts describing each match: {type, original_span_length,
   start_char, end_char} — WITHOUT including the actual original PII value in the returned list,
   since that list may end up in logs
Wrap this as a LangGraph-compatible node function redaction_node(state: TicketState) -> TicketState
that updates redacted_text and pii_found, and never mutates raw_text. Keep under 150 lines.
```

**Watch out — real security concern:** the returned "pii_found" metadata must never include the actual PII text, only counts/types/positions, because this metadata often ends up in application logs or the PostgreSQL audit table, which defeats the purpose of redacting in the first place if you log the raw value right next to it.

### Step 4.4 — Wire in the fine-tuned LLM as a classification tool

**Copilot/Claude prompt:**
```
Write a classification_tool.py that calls Member 1's fine-tuned model service over HTTP
(POST {FINE_TUNED_LLM_URL}/classify) using httpx with a 10-second timeout and 2 retries on failure.
If the service is unreachable after retries, fall back to a rule-based heuristic classifier (simple
keyword matching for category, and default priority=Medium, sentiment=Neutral) so the whole pipeline
degrades gracefully instead of crashing when the ML service is down — log a WARNING when the fallback
is used. Wrap as classification_node(state: TicketState) -> TicketState. Under 150 lines.
```

**Watch out — real-world resilience concern:** this fallback matters a lot for your live demo — if the fine-tuned model service crashes mid-demo (GPU memory issue, etc.), you want the rest of the pipeline to keep working in degraded mode rather than the whole ticket flow dying, which looks much worse in front of examiners than a slightly-wrong classification.

### Step 4.5 — Routing decision node

**Copilot/Claude prompt:**
```
Write routing_node(state: TicketState) -> TicketState implementing this decision logic:
- If category == "Technical" -> routing_decision = "technical"
- If category in ("Billing","Account") -> routing_decision = "billing"
- If the fine-tuned model's confidence is low (you'll need to also return a confidence score from
  the classification tool - go back and add a `confidence: float` field to the classify response
  and to TicketState) OR the ticket text contains signals of both technical and billing issues
  (simple heuristic: keyword sets for each domain both present) -> routing_decision = "both"
Add unit tests in tests/test_routing_node.py covering all three branches plus an edge case where
category is missing/None (should default to "both" so ambiguous tickets get maximum coverage rather
than being silently dropped).
```

**Watch out:** Your proposal explicitly calls out multi-issue tickets as the hard case worth solving (Section 2, "a billing error caused by a technical bug"). Make sure this branch is actually tested and demoed, not just theoretically present — this is a headline feature of your project's novelty claim.

---

# 10. Phase 5 — Specialist Agents & RAG (Member 2, Weeks 4–6)

### Step 5.1 — Build the knowledge base content

**Do this on:** Google Docs or plain markdown files first (easier to review/edit as a team), then move into `vector_store/kb_documents/`. Write 20–40 short FAQ/policy snippets covering common technical issues (login errors, sync issues, app crashes) and billing issues (refund policy, invoice explanation, subscription changes). This can be partly self-written, partly adapted from real Zendesk/Freshdesk public help-center style content (paraphrase, don't copy verbatim, cite that it's self-compiled per your proposal's Section 3 table).

### Step 5.2 — Stand up ChromaDB and build the index

**Do this on:** VS Code, `vector_store/build_index.py`.

```bash
pip install chromadb sentence-transformers
```

**Copilot/Claude prompt:**
```
Write a script that loads all .md/.txt files from vector_store/kb_documents/, chunks each document
into ~300-token passages with 50-token overlap, embeds them with
sentence-transformers/all-MiniLM-L6-v2, and upserts them into a persistent ChromaDB collection
called "kb_support_docs" with metadata {source_file, chunk_index, domain: "technical"|"billing"}.
Make the script idempotent — re-running it should update existing chunks rather than duplicate them,
using a deterministic chunk ID derived from source_file + chunk_index. Under 150 lines.
```

**Watch out:** Chroma persistence mode needs a mounted volume in Docker (see Section 15) or you lose your index every container restart — do not discover this the night before the demo.

### Step 5.3 — Build the RAG retrieval tool

**Copilot/Claude prompt:**
```
Write rag_tool.py with a function retrieve_context(query: str, domain: Literal["technical","billing"],
k: int = 4) -> list[dict] that queries the Chroma collection filtered by metadata domain, returns the
top-k chunks with their source_file and similarity score, and logs a WARNING if the top result's
similarity score is below a configurable threshold (default 0.3), since a low-relevance retrieval
should be flagged for the validation step later as a possible hallucination risk. Under 100 lines.
```

### Step 5.4 — Build the two specialist agent nodes

**Copilot/Claude prompt:**
```
Write technical_agent_node(state: TicketState) and billing_agent_node(state: TicketState) as
LangGraph nodes. Each should: call retrieve_context with the appropriate domain, build a prompt
that instructs the LLM to answer ONLY using the retrieved context and to explicitly say
"I don't have enough information to resolve this" if the context doesn't cover the issue (this is
your groundedness/anti-hallucination guard from the proposal's evaluation plan), call the external
LLM provider (Claude or Gemini, whichever LLM_PROVIDER is configured in .env - implement a small
provider-agnostic wrapper llm_client.py so switching providers is a one-line config change, not a
code rewrite), and write the draft into state["agent_drafts"][domain]. If routing_decision == "both",
LangGraph should run both nodes (this is a fan-out you'll wire in the graph builder, not inside the
node functions themselves). Keep each node function under 100 lines; put the shared prompt-building
logic in agents/shared/prompt_templates.py so both agents reuse it instead of duplicating.
```

**README task:** `agent_orchestration/README.md` gets this diagram:
```mermaid
flowchart TD
    A[Ticket state] --> B[Redaction node]
    B --> C[Classification node - fine-tuned LLM]
    C --> D[Routing node]
    D -->|technical| E[Technical Agent + RAG]
    D -->|billing| F[Billing Agent + RAG]
    D -->|both| G[Both agents run]
    E --> H[Validation node]
    F --> H
    G --> H
    H -->|fails| I[Send back for redraft]
    H -->|passes| J[Escalation check]
```

---

# 11. Phase 6 — Validation Step & Human Handoff (Member 2, Week 6)

### Step 6.1 — Policy checklist (rule-based part)

**Copilot/Claude prompt:**
```
Write a rule-based checklist function run_policy_checks(draft: str, retrieved_context: list[dict],
pii_found: list) -> dict returning {"passed": bool, "failed_rules": list[str]}. Rules to check:
1. Draft does not contain any raw PII patterns (re-run the same regex from redaction_tool.py on the
   OUTGOING draft too, not just the incoming ticket - this catches cases where the LLM accidentally
   echoes something sensitive back)
2. Draft is not empty and is under 2000 characters
3. Draft does not contain phrases indicating overcommitment not supported by context, using a simple
   keyword list (e.g., "guaranteed", "I promise", "definitely will" combined with an absence of
   matching guarantee language in retrieved_context)
4. If retrieved_context was empty or all below the similarity threshold, draft must contain the
   "not enough information" fallback phrase, not a fabricated answer
Under 120 lines.
```

### Step 6.2 — LLM-as-judge validation call

**Copilot/Claude prompt:**
```
Write an llm_judge_check(draft: str, ticket_text: str, retrieved_context: list[dict]) function that
makes ONE call to the configured external LLM asking it to rate the draft response on: on_topic
(bool), grounded_in_context (bool), appropriate_tone (bool), and to return a short reasoning string,
using structured JSON output. Combine this with the rule-based results from run_policy_checks into
a final validation_node(state: TicketState) -> TicketState that sets state["validation_result"].
Under 100 lines.
```

**Watch out:** This is a second LLM call per ticket on top of the specialist agent's own drafting call — factor this into your latency and cost evaluation (your proposal explicitly promises to measure "end-to-end latency and approximate per-ticket cost, given the extra LLM calls a multi-agent system requires").

### Step 6.3 — Escalation trigger logic

**Copilot/Claude prompt:**
```
Write escalation_node(state: TicketState) -> TicketState implementing:
escalation_triggered = True if (priority == "Urgent") OR (sentiment == "Strongly Negative")
OR (routing_decision == "both" AND classification confidence < 0.6)
Add this as a pure function decide_escalation(...) separately from the node wrapper, with unit tests
covering each OR branch independently plus a combined case, so we can cite exact test coverage in our
evaluation report.
```

### Step 6.4 — Human Handoff package

**Copilot/Claude prompt:**
```
Write build_handoff_package(state: TicketState) -> dict that assembles everything a human agent needs
to review in one payload: original (redacted) ticket text, predicted category/priority/sentiment,
which specialist(s) ran, their draft response(s), retrieved KB sources used, validation_result, and a
short auto-generated "reasoning summary" string that concatenates why escalation was triggered. This
is what gets sent to the frontend's Agent Review Screen (Member 3's component) - document the exact
JSON shape in a docstring so Member 3 can build the UI against it without guessing.
```

**Watch out:** Coordinate this JSON shape with Member 3 BEFORE either of you build very far — this is the other major cross-team contract point besides `state.py`.

---

# 12. Phase 7 — API Gateway (Member 3, Weeks 2–4, in parallel with Members 1 & 2)

### Step 7.1 — FastAPI project skeleton

```bash
cd api_gateway && python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn[standard] sqlalchemy asyncpg alembic python-jose[cryptography] passlib[bcrypt] python-dotenv httpx
```

**Copilot/Claude prompt:**
```
Scaffold a FastAPI app with: app/main.py (app factory + router registration + CORS middleware),
app/core/config.py (Pydantic Settings reading from .env), app/db/session.py (async SQLAlchemy engine
+ session dependency), app/db/models.py (Ticket, TicketLog, User tables), app/auth/ (JWT creation +
verification + a get_current_user dependency), app/routers/tickets.py (POST /tickets, GET
/tickets/{id}, GET /tickets - list with pagination), app/routers/auth.py (POST /login,
POST /register for demo purposes only). Keep every file under 200 lines - split routers further by
resource if they grow past that. Add a GET /health endpoint with no auth required.
```

### Step 7.2 — Database schema

**Do this on:** VS Code, `infra/postgres/init.sql` or Alembic migrations (`alembic revision --autogenerate`).

Tables needed (from your diagram): `tickets` (raw ticket + redacted text + status), `ticket_classifications` (category/priority/sentiment/confidence), `ticket_drafts` (per-agent drafts), `ticket_validations`, `human_reviews`, `resolutions` (final response + closure timestamp + metrics), `users` (for auth demo).

**Copilot/Claude prompt:**
```
Design SQLAlchemy 2.0 ORM models for the tables above with proper foreign keys to a central
tickets.id, created_at/updated_at timestamps on every table, and an Alembic migration that creates
them. Add appropriate indexes on tickets.status and tickets.created_at since the review screen will
filter/sort by these. Use UUID primary keys, not auto-increment integers, since this mirrors how a
real production system would avoid exposing sequential ticket counts externally.
```

### Step 7.3 — POST /tickets endpoint, and calling the Orchestration service

**Copilot/Claude prompt:**
```
Implement POST /tickets: validate the incoming payload (Pydantic schema: customer_name, customer_email,
subject, message), require a valid JWT, write a raw ticket row to Postgres with status="received",
then make an async HTTP call to {ORCHESTRATION_URL}/process_ticket passing the ticket id and raw text,
using httpx.AsyncClient with a 30-second timeout (agent pipelines with multiple LLM calls are slow -
do NOT block the HTTP response on this; instead, return 202 Accepted immediately with the ticket id,
and process the orchestration call in a FastAPI BackgroundTask, updating the ticket's status in
Postgres as it progresses through the pipeline). Add a GET /tickets/{id}/status endpoint the
frontend can poll to check progress.
```

**Watch out — this is a real production concern, not just academic polish:** LangGraph pipelines with multiple sequential LLM calls (classification, drafting, LLM-judge validation) can easily take 5–20 seconds. If your API blocks synchronously, your frontend will look frozen/broken during the demo. Use background tasks + polling (or, if you have time, WebSockets/SSE for live status updates) — either is fine, but do NOT do a synchronous 20-second HTTP request in front of examiners.

### Step 7.4 — Optimistic locking for the Human Agent Review Screen

This addresses your own note about race conditions — relevant here because two human agents could open the same escalated ticket at once in a real support team.

**Copilot/Claude prompt:**
```
Add an integer `version` column to the tickets table (default 0). Implement PATCH
/tickets/{id}/review that accepts the human agent's edits AND the version number they last read.
On save: run an UPDATE ... WHERE id = :id AND version = :expected_version, incrementing version by 1.
If zero rows were updated, it means someone else saved first - return HTTP 409 Conflict with the
current server-side version of the ticket in the response body, so the frontend can show the human
agent "This ticket was updated by someone else, here's the latest version" instead of silently
overwriting their colleague's edit. Add a unit test simulating two concurrent PATCH calls with the
same starting version, asserting exactly one succeeds and the other gets 409.
```

**Watch out:** This is the exact "keep components modular, handle race conditions with optimistic locking, add conflict resolution so no data is lost when 2 users save at the same time" requirement you asked about — implemented here because the Human Agent Review Screen is the one place in this system where two people (two support agents) could genuinely edit the same record concurrently. It's realistic, not decorative — a real support team has multiple agents online at once, and both could click into the same urgent ticket.

**README task:** `api_gateway/README.md` should include a short sequence explanation of the 409-conflict flow with a tiny diagram:
```mermaid
sequenceDiagram
    participant AgentA as Human Agent A
    participant AgentB as Human Agent B
    participant API as API Gateway
    AgentA->>API: GET ticket (version=3)
    AgentB->>API: GET ticket (version=3)
    AgentA->>API: PATCH review (version=3)
    API-->>AgentA: 200 OK (version=4)
    AgentB->>API: PATCH review (version=3)
    API-->>AgentB: 409 Conflict (current version=4)
    AgentB->>API: Re-fetch, re-apply edit, PATCH (version=4)
    API-->>AgentB: 200 OK (version=5)
```

---

# 13. Phase 8 — Frontend (Member 3, Weeks 4–6)

### Step 8.1 — Scaffold

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npm install tailwindcss @tailwindcss/vite axios react-router-dom @tanstack/react-query zod react-hook-form
```

### Step 8.2 — Ticket Submission feature

**Copilot/Claude prompt:**
```
Build a feature module frontend/src/features/ticket-submission/ with: types.ts (Ticket,
TicketSubmissionForm types matching the API Gateway's Pydantic schema exactly - copy field names
verbatim from api_gateway/app/models/ticket_schemas.py), a TicketForm.tsx component using
react-hook-form + zod validation, an api.ts with a submitTicket function using axios and the shared
API client, and a useSubmitTicket hook wrapping it with @tanstack/react-query's useMutation, including
loading and error states shown in the UI. After submission, show a "Ticket received - processing..."
state that polls GET /tickets/{id}/status every 2 seconds until status is no longer "processing",
then redirects to a confirmation view. Keep each component under 600 lines - if TicketForm.tsx grows
past that, split field groups into subcomponents. Put feature-specific types only in this module's
types.ts, not in a shared global types file, since ticket-submission fields belong to this feature.
```

### Step 8.3 — Agent Review Screen (for human agents)

**Copilot/Claude prompt:**
```
Build features/agent-review/ showing: a list of escalated tickets (GET /tickets?status=escalated),
a detail view rendering the handoff package (redacted ticket text, predicted classification, each
specialist agent's draft with its RAG sources shown as expandable citations, the validation result
with pass/fail reasons), and an edit form letting the human approve as-is, edit the draft text, or
reject and request a redraft. On save, call PATCH /tickets/{id}/review including the `version` field
you fetched with the ticket. If the API returns 409, show a clear inline banner: "This ticket was
just updated by another agent - showing you the latest version" and reload the latest draft into the
edit form WITHOUT discarding the human's typed edits until they confirm, by keeping their in-progress
edit in a separate draftBuffer state so a conflict doesn't silently erase their work. Keep
components under 600 lines, split into ReviewList.tsx, ReviewDetail.tsx, DraftEditor.tsx,
ConflictBanner.tsx.
```

**Watch out:** the "don't silently erase their work on conflict" detail matters — this is the actual conflict-resolution UX, not just the backend 409. A backend that returns 409 but a frontend that discards the human's typed edit on error is still a real data-loss bug from the user's point of view.

### Step 8.4 — Shared API client & auth

**Copilot/Claude prompt:**
```
Build frontend/src/shared/api/client.ts: an axios instance with baseURL from an environment variable
VITE_API_BASE_URL, a request interceptor attaching the JWT from a simple auth context (React Context
+ localStorage for this academic demo - note in a comment that a real production app would use an
httpOnly cookie instead, but that requires backend session support we're not building for this
project), and a response interceptor that redirects to /login on any 401. Under 120 lines.
```

**Watch out — be honest about this tradeoff in your report:** storing JWTs in localStorage is vulnerable to XSS in a real production app. It's a reasonable simplification for an academic symposium demo, but say so explicitly in your report/README rather than presenting it as best practice — examiners in a security-aware course will notice either way, and it looks much better coming from you first.

---

# 14. Phase 9 — Cross-Team Integration (ALL MEMBERS, Week 6–7)

This is where the three services actually get wired together and tested end-to-end for the first time. Do this together, ideally in person or on a call, not asynchronously.

### Step 9.1 — Contract review

Before wiring anything, sit together and confirm:
1. `TicketState` field names (Member 2) match what Member 3's Pydantic schemas expect from the orchestration service's response.
2. The handoff package JSON shape (Section 11, Step 6.4) matches what Member 3's `ReviewDetail.tsx` actually renders.
3. All three `.env` files reference the same service hostnames as defined in `docker-compose.yml` (Section 15), not `localhost`, once running inside Docker.

### Step 9.2 — Orchestration service HTTP wrapper

Member 2's LangGraph graph currently runs as Python function calls — Member 3's API Gateway needs to call it over HTTP.

**Copilot/Claude prompt:**
```
Write agent_orchestration/app/main.py exposing the LangGraph app as a FastAPI service with a single
POST /process_ticket endpoint accepting {ticket_id: str, raw_text: str}, invoking the compiled
LangGraph graph with an initial TicketState, and returning the final state as JSON. Add a
GET /health endpoint. Wrap the graph invocation in a try/except that catches any node failure,
logs the full state at time of failure for debugging, and returns a 500 with a generic error message
(never leak internal exception details or stack traces in the HTTP response body - log them
server-side only). Under 150 lines.
```

**Watch out — real security concern:** never return raw Python tracebacks or internal exception messages in API responses — this is a common real-world vulnerability (information disclosure) and also just looks unprofessional in a demo if something breaks live.

### Step 9.3 — End-to-end manual test

**Do this on:** Postman/Insomnia, or a quick script, hitting the running (Docker Compose, Section 15) stack:
1. POST a test ticket with an email address and phone number in the body → confirm it gets redacted before reaching any LLM (check logs, not just the final response).
2. Confirm classification comes back and routing matches expectations for an obviously-technical, an obviously-billing, and a deliberately-ambiguous test ticket.
3. Confirm an "Urgent"-worded ticket actually triggers escalation and shows up in the Agent Review Screen.
4. Confirm the optimistic-locking 409 flow (Section 12, Step 7.4) by opening the same escalated ticket in two browser tabs and saving both.

---

# 15. Phase 10 — Docker & Deployment (Member 3, ongoing from Week 3, finalized Week 7)

### Step 10.1 — Per-service Dockerfiles

**`frontend/Dockerfile`:**
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**`api_gateway/Dockerfile`** (same pattern for `agent_orchestration/Dockerfile`):
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`ml_finetuning/Dockerfile`** (needs GPU base image if you deploy inference with GPU; CPU-only is fine for a demo if latency is acceptable):
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8500
CMD ["uvicorn", "src.inference.serve:app", "--host", "0.0.0.0", "--port", "8500"]
```

**Watch out:** the fine-tuned model service is the heaviest container (loads a 7–8B model into memory). If your demo machine doesn't have enough RAM/VRAM, consider quantizing further (4-bit) purely for the demo, and note in your report that a production deployment would use a dedicated GPU inference server (e.g., vLLM or TGI) rather than a plain FastAPI + transformers process.

### Step 10.2 — `docker-compose.yml` (full)

**Copilot/Claude prompt:**
```
Write a docker-compose.yml with services: frontend (build ./frontend, port 5173:80), api_gateway
(build ./api_gateway, port 8000:8000, depends_on postgres), agent_orchestration (build
./agent_orchestration, port 8600:8600, depends_on vector_store and ml_finetuning), ml_finetuning
(build ./ml_finetuning, port 8500:8500), vector_store (image chromadb/chroma, port 8000:8000 internal
- careful, this port number will collide with api_gateway, use 8001:8000 for chroma's host mapping),
postgres (image postgres:16, port 5432:5432, volume for data persistence, env_from .env), and a named
volume for chroma's persistent data directory too. All services on a shared bridge network
clario_net. Every service reads its config from the root .env file. Add healthchecks for postgres
and vector_store so dependent services wait for them to be actually ready, not just "container
started" (use depends_on with condition: service_healthy).
```

**Watch out — the port collision above is a real, common mistake:** Chroma's default internal port is 8000, same as a naive FastAPI default — always map host ports explicitly and double check nothing collides before your team wastes an hour debugging "connection refused."

### Step 10.3 — PostgreSQL init and persistence

`infra/postgres/init.sql` should run automatically via the compose volume mount `./infra/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql` — this only runs on first container creation with an empty data volume, so if you change the schema later, you need Alembic migrations (Section 12, Step 7.2), not edits to `init.sql`.

### Step 10.4 — Full local run

```bash
docker compose --env-file .env up --build
```

**Watch out — resource usage:** running Postgres + Chroma + API Gateway + Orchestration + a loaded 7–8B parameter model, all at once on a laptop, can be genuinely heavy. Test this on the actual laptop you'll demo on, at least a week before the symposium, not the night before.

**README task:** root `README.md` documents the exact `docker compose up` command, all required `.env` variables with one-line descriptions, and a "Troubleshooting" section listing the port-collision issue above and any others you actually hit.

---

# 16. Phase 11 — Evaluation (ALL MEMBERS, Week 7–8)

Run these once your held-out test set (Section 6.4) is truly locked and the full pipeline (Section 14) works end-to-end.

| Metric | Owner | How |
|---|---|---|
| Fine-tuned model accuracy/macro-F1 vs baseline | Member 1 | Section 8, Step 3.4 script, on held-out test |
| Redaction precision/recall | Member 1 (dataset) + Member 2 (live tool) | Manual spot-check of ~100 tickets, compare masked spans against a human-labelled ground truth |
| RAG groundedness/hallucination rate | Member 2 | Manual review of ~50 specialist responses: does every factual claim trace back to a retrieved chunk? |
| Routing accuracy | Member 2 | Manually label ~100 held-out tickets' "correct" specialist, compare to actual routing_decision |
| Automation rate | Member 2 + Member 3 (data from Postgres) | % of a held-out ticket sample resolved without escalation |
| Escalation precision/recall | Member 2 | Manually label which of the sample "should" have escalated, compare to actual |
| End-to-end latency & per-ticket cost | Member 3 | Log timestamps at each pipeline stage (already in Postgres via `ticket_logs`), sum LLM token costs per ticket |
| Single-LLM ablation | Whole team | Prompt one general LLM call to do the entire triage+draft job directly on the same held-out sample, compare outcomes to the full multi-agent pipeline |

**Copilot/Claude prompt for the ablation:**
```
Write scripts/ablation_single_llm.py that takes the same held-out ticket sample used for
routing/escalation evaluation, sends each ticket in a single prompt to the same external LLM
provider asking it to directly classify, decide routing, and draft a response all at once, then
saves results in the same format as the multi-agent pipeline's outputs so evaluate.py can compare
them side by side on the same metrics (routing accuracy proxy, groundedness, latency, cost).
```

**Watch out:** be honest in your report if the single-LLM ablation performs comparably on some metrics — your proposal's own Section 5 already commits to testing "whether the added agentic complexity is actually justified," so a mixed result is a valid, publishable finding, not a failure of your project.

---

# 17. Phase 12 — Stretch Goal: Rysera Stem LMS Integration (Member 3, Week 8+, only if core system is fully working and evaluated first)

1. Confirm what integration surface Rysera Stem LMS actually exposes (webhook? REST API? plugin system?) — visit Rysera's own documentation/admin panel first; do not assume a generic REST API exists without checking.
2. If a webhook is available: build a small adapter endpoint `POST /integrations/rysera/webhook` in the API Gateway that maps Rysera's ticket/support-request payload shape into your internal ticket schema, then calls the same internal ticket-creation logic as the normal frontend path (do not duplicate business logic — route through the same service function).
3. If no clean integration surface exists, document this honestly as a stretch goal that was scoped but not completed due to integration-access constraints — this is a completely acceptable outcome for a stretch goal and better than forcing a fragile hack.

**Watch out:** do not start this until Sections 6–16 are solid — a partially-working core system with a half-built LMS integration will score worse than a fully-working core system with the integration honestly marked as future work.

---

# 18. General Coding Standards To Apply Everywhere (give this to your AI assistant as a standing instruction at the start of every coding session)

```
Standing project rules for this codebase:
1. Keep each file under 600 lines. If a file grows past that, split it into smaller modules along
   clear responsibility lines (e.g., separate the HTTP layer from business logic from data access),
   and update imports accordingly.
2. Maintain a modular, feature-based file structure. Do not create a single giant "utils.py" or
   "helpers.ts" that becomes a dumping ground.
3. For the frontend, put feature-specific TypeScript types inside that feature's own types.ts file
   (e.g., features/ticket-submission/types.ts), not in a global shared types file, unless a type is
   genuinely used by 2+ features, in which case move it to shared/types.ts and say so in a comment.
4. Any endpoint or database write that could be triggered by two concurrent users/requests touching
   the same record must use optimistic locking (a version column, checked and incremented on update)
   and must return a clear conflict response (HTTP 409) rather than silently overwriting data.
   The calling frontend code must handle that 409 by re-fetching and re-prompting the user, never by
   silently discarding one side's changes.
5. Never log raw PII or raw API keys, even at DEBUG level.
6. Every new service/module gets a README.md explaining what it does, its inputs/outputs, and any
   gotchas, written as if for a teammate who has never seen this code before.
7. Prefer explicit, narrow exception handling over bare except: blocks; log full details server-side,
   return sanitized error messages to any external caller.
8. Any function that calls an external API (LLM providers, HuggingFace) must have a timeout and a
   retry policy, and must fail gracefully (a documented fallback behavior), not crash the whole
   request.
```

---

# 19. README.md Template (use this shape for every service's README, have your AI assistant fill it in per component)

```markdown
# <Service Name>

## What this does
One paragraph, plain English.

## How it fits into Clario
Short paragraph + a mermaid diagram showing this service's inputs and outputs relative to its
neighbors in the pipeline.

## Key files
- `path/to/file.py` — what it's responsible for
- ...

## Environment variables used
| Variable | Purpose | Required |
|---|---|---|

## Running locally
Exact commands.

## Known limitations / things to watch out for
Bullet list — be honest here, this is for your teammates and your future selves during the report
write-up, not a marketing page.

## Tests
How to run them, what they cover.
```

---

# 20. Suggested Timeline (8 weeks, adjust to your actual deadline)

| Week | Member 1 | Member 2 | Member 3 |
|---|---|---|---|
| 1 | Dataset download, EDA | LangGraph learning, state design | Repo/Docker skeleton, FastAPI skeleton |
| 2 | PII cleaning, train/val/test split | Redaction tool, classification tool (mocked) | DB schema, auth, POST /tickets |
| 3 | Gemini distillation run | Routing node + tests | Frontend scaffold, ticket form |
| 4 | LoRA fine-tuning v1 | KB content + Chroma index, RAG tool | Agent review screen scaffold |
| 5 | Fine-tuning iteration, W&B tracking | Specialist agents | Optimistic locking + 409 flow |
| 6 | Held-out evaluation | Validation step + escalation + handoff | Docker Compose full integration |
| 7 | Support integration debugging (all) | Support integration debugging (all) | Support integration debugging (all) |
| 8 | Evaluation report writing, ablation | Agent-level metrics writing | Deployment polish, demo rehearsal, stretch goal if time allows |

---

# 21. Final Pre-Symposium Checklist

- [ ] Held-out test set was touched exactly once, at the very end, for final numbers.
- [ ] `.env` is not committed anywhere in Git history (`git log -p -- .env` should return nothing).
- [ ] `docker compose up --build` works from a clean clone on a machine that isn't your main dev laptop, if possible.
- [ ] A PII-containing test ticket has been manually verified to be masked before it reaches any external LLM call, checked in actual logs, not just assumed.
- [ ] The two-tab optimistic-locking conflict has been demoed and works.
- [ ] The single-LLM ablation numbers are in the report, whatever they show.
- [ ] Every README.md exists and is accurate, not a leftover template.
- [ ] Fallback behavior (fine-tuned model service down) has been tested at least once, not just coded.
- [ ] Rysera integration status is honestly stated as done / partially done / descoped.