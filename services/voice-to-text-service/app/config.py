"""Environment-driven configuration for the Voice-to-Text Service."""

from __future__ import annotations

import os

# ─── Model ──────────────────────────────────────────────────────────────────

# faster-whisper model size or a path to a converted CTranslate2 model.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
# "cpu" or "cuda". "auto" lets faster-whisper pick.
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
# int8 keeps the CPU footprint in line with the other sidecar services.
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "en")
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
# Where the HuggingFace snapshot is cached inside the container.
WHISPER_CACHE_DIR = os.getenv("WHISPER_CACHE_DIR", "/models")
WHISPER_CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "0"))

# ─── Streaming ──────────────────────────────────────────────────────────────

SAMPLE_RATE = 16_000
# Minimum amount of fresh audio before a new partial decode is attempted.
MIN_CHUNK_SECONDS = float(os.getenv("VOICE_MIN_CHUNK_SECONDS", "1.0"))
# Hard cap on the rolling window handed to Whisper, keeps latency bounded.
MAX_WINDOW_SECONDS = float(os.getenv("VOICE_MAX_WINDOW_SECONDS", "22.0"))
# Guard against unbounded sessions.
MAX_SESSION_SECONDS = float(os.getenv("VOICE_MAX_SESSION_SECONDS", "300.0"))
# Silero VAD aggressiveness passed through to faster-whisper.
VAD_MIN_SILENCE_MS = int(os.getenv("VOICE_VAD_MIN_SILENCE_MS", "500"))
VAD_THRESHOLD = float(os.getenv("VOICE_VAD_THRESHOLD", "0.5"))
