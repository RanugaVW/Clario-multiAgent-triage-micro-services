"""Thread-safe round-robin pool over every GEMINI_API_KEY* in ml_finetuning/.env."""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

MODEL = "gemini-3.1-flash-lite"
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
_KEY_NAMES = ("GEMINI_API_KEY",) + tuple(f"GEMINI_API_KEY{i}" for i in range(2, 10))

logger = logging.getLogger(__name__)


class AllKeysExhausted(RuntimeError):
    """Every key hit its daily quota; rerun tomorrow and the scripts resume."""


class GeminiPool:
    def __init__(self, clients: list[Any] | None = None, model: str = MODEL) -> None:
        if clients is None:
            load_dotenv(ENV_PATH)
            clients = [genai.Client(api_key=key) for name in _KEY_NAMES if (key := os.getenv(name))]
        if not clients:
            raise RuntimeError(f"No GEMINI_API_KEY* found in {ENV_PATH}")
        self._clients = clients
        self._model = model
        self._lock = threading.Lock()
        self._next = 0
        self._exhausted: set[int] = set()
        logger.info("Gemini pool: %d key(s)", len(clients))

    def _take(self) -> tuple[int, Any]:
        with self._lock:
            for _ in range(len(self._clients)):
                idx = self._next
                self._next = (self._next + 1) % len(self._clients)
                if idx not in self._exhausted:
                    return idx, self._clients[idx]
        raise AllKeysExhausted("All Gemini API keys hit their daily quota.")

    def _mark_exhausted(self, idx: int) -> None:
        with self._lock:
            self._exhausted.add(idx)
            logger.warning("Key %d exhausted for today (%d/%d left)", idx + 1,
                           len(self._clients) - len(self._exhausted), len(self._clients))

    def generate_json(self, contents: str, system_instruction: str, schema: Any,
                      temperature: float, max_attempts: int = 10) -> str:
        """Raw JSON text of one structured-output call, rotating keys on quota errors."""
        last_error: Exception | None = None
        for attempt in range(max_attempts):
            idx, client = self._take()
            try:
                response = client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=temperature,
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                )
                return response.text
            except Exception as error:  # the SDK raises several unrelated types
                last_error = error
                message = str(error)
                # Per-minute limits are also 429s; only the per-day metric retires a key.
                if "PerDay" in message:
                    self._mark_exhausted(idx)
                elif "429" in message or "RESOURCE_EXHAUSTED" in message:
                    time.sleep(65)
                else:
                    time.sleep(min(2 ** attempt, 30))
        raise RuntimeError(f"Gemini call failed after {max_attempts} attempts: {last_error}")
