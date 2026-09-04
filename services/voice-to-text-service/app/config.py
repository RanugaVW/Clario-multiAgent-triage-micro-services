"""Environment-driven configuration for the Voice-to-Text Service."""

from __future__ import annotations

import os

# --- Model ------------------------------------------------------------------

# faster-whisper model size or a path to a converted CTranslate2 model.
# `base` is the default because streaming latency is bounded by how long one
# decode takes, and on CPU that is ~1.4s for base vs ~3.9s for small (measured
# int8, 12 cores, 15s of speech) for the same transcript. Use `tiny` (~0.8s) if
# partials still lag, `small`/`medium` only with a GPU.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
# "cpu" or "cuda". "auto" lets faster-whisper pick.
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
# int8 keeps the CPU footprint in line with the other sidecar services.
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "en")
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
# Where the HuggingFace snapshot is cached. The Dockerfile always overrides
# this to /models (root-owned inside the container image, created via
# `RUN mkdir -p /models`, so writable there). That default doesn't work for
# a local (non-Docker) run: on a bare host /models is root-owned and doesn't
# exist, so the model download fails with PermissionError and the service
# comes up "alive" (uvicorn binds fine) but with model_loaded: false forever
# - every transcription request then fails, with no error visible unless you
# check /health or the startup log. huggingface_hub creates this directory
# (and its parents) itself on first use, so anywhere under the user's own
# home directory works with zero manual setup.
WHISPER_CACHE_DIR = os.getenv(
    "WHISPER_CACHE_DIR", os.path.expanduser("~/.cache/clario/whisper-models")
)
WHISPER_CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "0"))

# --- Streaming --------------------------------------------------------------

SAMPLE_RATE = 16_000
# Minimum amount of fresh audio before a new partial decode is attempted.
MIN_CHUNK_SECONDS = float(os.getenv("VOICE_MIN_CHUNK_SECONDS", "1.0"))
# Hard cap on the rolling window handed to Whisper. Whisper pads every input to
# a 30s mel window, so anything under 30s costs one encoder pass and decode time
# is near-flat in window length; going over 30s would cost a second pass.
MAX_WINDOW_SECONDS = float(os.getenv("VOICE_MAX_WINDOW_SECONDS", "22.0"))
# Guard against unbounded sessions.
MAX_SESSION_SECONDS = float(os.getenv("VOICE_MAX_SESSION_SECONDS", "300.0"))
# Silero VAD aggressiveness passed through to faster-whisper.
VAD_MIN_SILENCE_MS = int(os.getenv("VOICE_VAD_MIN_SILENCE_MS", "500"))
VAD_THRESHOLD = float(os.getenv("VOICE_VAD_THRESHOLD", "0.5"))
# Below this much un-decoded audio, `finalize()` promotes the last partial
# instead of paying for another full decode the user would wait on.
FINALIZE_MIN_NEW_AUDIO_SECONDS = float(
    os.getenv("VOICE_FINALIZE_MIN_NEW_AUDIO_SECONDS", "0.25")
)
# Committed audio is trimmed away after every decode, but this many committed
# words are kept as acoustic context. Counting *words* rather than seconds means
# the window always starts on a word boundary: the next decode re-reports those
# words intact, so the overlap can be matched by text and stripped exactly. A
# fixed time offset cuts mid-word, the re-decode then garbles it, the match
# misses, and the word that followed gets dropped.
WINDOW_CONTEXT_WORDS = int(os.getenv("VOICE_WINDOW_CONTEXT_WORDS", "3"))

# faster-whisper retries a whole decode at each of these temperatures whenever
# the result trips its compression-ratio / logprob checks. The default ladder
# ([0.0, 0.2, 0.4, 0.6, 0.8, 1.0]) turns one 1s decode into six, and short
# mid-sentence streaming windows trip those checks constantly - measured at 17s
# for a 3.7s window. A single temperature caps a decode at one pass; a poor
# partial is corrected by the next decode a second later anyway.
WHISPER_TEMPERATURE = float(os.getenv("WHISPER_TEMPERATURE", "0.0"))
# Mild anti-looping, so a bad window cannot spew repeated tokens to the limit.
WHISPER_REPETITION_PENALTY = float(os.getenv("WHISPER_REPETITION_PENALTY", "1.1"))
