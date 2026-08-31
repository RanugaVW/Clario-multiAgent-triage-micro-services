FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# faster-whisper decodes containers through the bundled PyAV libraries, so no
# system ffmpeg is required. Model snapshots are cached in a mounted volume.
ENV WHISPER_CACHE_DIR=/models
RUN mkdir -p /models
# Voice To Text Service exposes FastAPI (REST + WebSocket) on port 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
