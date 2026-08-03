# Clario ML Sidecar (Agent Orchestration)

This service manages the core AI brain of the Clario platform. It handles the LangGraph state machine, RAG (Retrieval-Augmented Generation) pipeline, and specialist agent execution.

## Architecture

Built with Python and **FastAPI**, orchestrating **LangGraph**. The workflow includes:
- **SurrogateShield:** Masks incoming PII (using regex + spaCy NER).
- **Classifier:** Identifies category, sentiment, and priority.
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

- **API Rate Limits:** If Gemini API fails, check quotas or use the fallback heuristic classifier.
- **Empty RAG Results:** Ensure the ChromaDB index is built (`python vector_store/build_index.py`).
