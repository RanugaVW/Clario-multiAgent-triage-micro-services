FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
# Containers get no GPU (no deploy/devices entries in docker-compose.yml), so the
# default CUDA torch wheels from PyPI are ~2.5GB of dead weight. Pin the CPU build
# first; the ==2.13.0 line in requirements.txt is then already satisfied.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 10 \
        --index-url https://download.pytorch.org/whl/cpu \
        --extra-index-url https://pypi.org/simple \
        torch==2.13.0+cpu
# Cache mount replaces --no-cache-dir so retries and sibling services reuse wheels.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 10 -r requirements.txt \
    && python -m spacy download en_core_web_sm
COPY . .
# AI Orchestrator consumes from Redis
CMD ["python", "-m", "app.worker"]
