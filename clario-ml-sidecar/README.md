# Clario ML Sidecar (Agent Orchestration)

This service manages the core AI brain of the Clario platform. It handles the LangGraph state machine, RAG (Retrieval-Augmented Generation) pipeline, and specialist agent execution.

## Architecture

Built with Python and **FastAPI**, orchestrating **LangGraph**. The workflow includes:
- **SurrogateShield:** Masks incoming PII (using regex + spaCy NER).
- **Classifier:** Fine-tuned Llama-3.2 3B LoRA adapter (Gemini fallback) that assigns one or more categories, a sentiment, and a priority.
- **Router:** Routes to the Technical Agent, Billing Agent, or both.
- **RAG & Agents:** Fetches context from **ChromaDB** and generates a response.
- **Judge (Validation):** Evaluates the response for quality and tone.
- **Escalation/Handoff:** Prepares a handoff package for a human reviewer if needed.

## Setup and Prerequisites

- Python 3.11
- Virtual environment (`python -m venv .venv`)

## Configuration (.env)

Create a `.env` file from the root `.env.example`. Required keys:
- `GEMINI_API_KEY` (or `ANTHROPIC_API_KEY`)
- `CHROMA_HOST` and `CHROMA_PORT`

### Live-feedback learning (optional, all off by default)

Set to `true` to enable. See `MLOPS.md` section 8.

| Flag | Job / effect |
|---|---|
| `CUSTOMER_FEEDBACK_LEARNING_ENABLED` | Daily: high customer ratings become exemplars; judge-vs-customer disagreements logged |
| `AGENT_EDIT_LEARNING_ENABLED` | Daily: learns from human edits; specialists read `agent_edit_refs` |
| `KB_GAP_DETECTION_ENABLED` | Weekly (sidecar only): proposes missing KB documents to `vector_store/kb_proposals/` |

Tunables: `CUSTOMER_FEEDBACK_POSITIVE_MIN` (4), `CUSTOMER_FEEDBACK_NEGATIVE_MAX` (2),
`CUSTOMER_FEEDBACK_JUDGE_HIGH` (4), `FEEDBACK_DISAGREEMENTS_PATH`, `AGENT_EDIT_MIN_SIMILARITY` (0.5),
`KB_GAP_MIN_CLUSTER_SIZE` (3), `KB_GAP_DISTANCE_THRESHOLD` (0.45), `KB_GAP_GROUNDEDNESS_MAX` (3),
`KB_GAP_CUSTOMER_MAX` (2), `KB_GAP_MAX_TICKETS` (1000), `KB_PROPOSALS_DIR`.

## Commands

- Install dependencies: `pip install -r requirements.txt`
- Run the server locally: `uvicorn app.main:app --host 0.0.0.0 --port 8600 --reload`
- Run tests: `pytest tests/`

## Testing

Uses `pytest` to run tests across nodes, tools, and cross-team contracts. Automated tests run on PRs via GitHub Actions.

## CI/CD and Deployment

- Tested automatically via `.github/workflows/ci.yml`.
- Deployed as a containerized service within the `clario_net` private virtual network (e.g., Render or AWS ECS).

## Troubleshooting

- **API Rate Limits:** If Gemini API fails, check quotas. Classification uses the local Llama-3.2 adapter when a CUDA GPU is available and falls back to Gemini otherwise.
- **Empty RAG Results:** Ensure the ChromaDB index is built (`python vector_store/build_index.py`).
