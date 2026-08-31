FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
# Cache mount replaces --no-cache-dir so retries reuse already-downloaded wheels;
# the longer timeout survives slow links on the larger transitive deps.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 10 -r requirements.txt
COPY . .
# faster-whisper decodes containers through the bundled PyAV libraries, so no
# system ffmpeg is required. Model snapshots are cached in a mounted volume.
ENV WHISPER_CACHE_DIR=/models
RUN mkdir -p /models
# Voice To Text Service exposes FastAPI (REST + WebSocket) on port 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
