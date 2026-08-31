"""faster-whisper model handling plus the incremental streaming decoder.

The streaming decoder uses the LocalAgreement-2 policy: every time a fresh
slice of audio arrives we re-decode the rolling window and only *commit* the
words that two consecutive hypotheses agree on. Committed words never change
again, which is what lets the browser render a stable transcript while the
tail keeps moving.
"""

from __future__ import annotations

import io
import logging
import re
import threading
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from app import config

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()

# Only one decode may touch the model at a time; serialising keeps CPU
# contention predictable when several browser tabs record at once.
_decode_lock = threading.Lock()

_PUNCT_RE = re.compile(r"[^\w']+", re.UNICODE)


def _load_model_singleton():
    """Load (and cache) the faster-whisper model. Safe to call concurrently."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel

            logger.info(
                "Loading faster-whisper model=%s device=%s compute_type=%s",
                config.WHISPER_MODEL,
                config.WHISPER_DEVICE,
                config.WHISPER_COMPUTE_TYPE,
            )
            _model = WhisperModel(
                config.WHISPER_MODEL,
                device=config.WHISPER_DEVICE,
                compute_type=config.WHISPER_COMPUTE_TYPE,
                download_root=config.WHISPER_CACHE_DIR,
                cpu_threads=config.WHISPER_CPU_THREADS,
            )
    return _model


def model_is_ready() -> bool:
    return _model is not None


def decode_audio_bytes(payload: bytes) -> np.ndarray:
    """Decode any container PyAV understands (webm/ogg/wav/mp3) to 16 kHz mono."""
    from faster_whisper.audio import decode_audio

    return decode_audio(io.BytesIO(payload), sampling_rate=config.SAMPLE_RATE)


def _normalise(word: str) -> str:
    """Compare words ignoring punctuation and case, which Whisper revises freely."""
    stripped = _PUNCT_RE.sub("", word).lower()
    # Punctuation-only tokens would all collapse to "" and compare equal.
    return stripped or word.lower()


@dataclass
class Word:
    text: str
    start: float
    end: float


def _run_whisper(audio: np.ndarray, prompt: str | None) -> list[Word]:
    """Decode a window and return word-level results with window-relative times."""
    model = _load_model_singleton()
    language = config.WHISPER_LANGUAGE or None

    with _decode_lock:
        segments, _info = model.transcribe(
            audio,
            language=language,
            beam_size=config.WHISPER_BEAM_SIZE,
            word_timestamps=True,
            # Committed text is fed back as a prompt instead, so previous-text
            # conditioning would double up and encourage repetition loops.
            condition_on_previous_text=False,
            initial_prompt=prompt or None,
            vad_filter=True,
            vad_parameters={
                "threshold": config.VAD_THRESHOLD,
                "min_silence_duration_ms": config.VAD_MIN_SILENCE_MS,
            },
        )

        words: list[Word] = []
        for segment in segments:
            for word in segment.words or []:
                text = word.word.strip()
                if text:
                    words.append(Word(text=text, start=word.start, end=word.end))
    return words


def _join(words: Iterable[Word]) -> str:
    return " ".join(w.text for w in words).strip()


class StreamingSession:
    """Accumulates PCM and produces committed/partial transcripts incrementally.

    All methods are synchronous and CPU bound; the FastAPI layer drives them
    from a worker thread so the event loop stays free to keep reading audio.
    """

    def __init__(self) -> None:
        self.sample_rate = config.SAMPLE_RATE
        self._audio = np.empty(0, dtype=np.float32)
        # Absolute time (seconds) of sample 0 of ``self._audio``.
        self._window_origin = 0.0
        self._total_seconds = 0.0
        self._seconds_since_decode = 0.0
        self._committed: list[Word] = []
        self._pending: list[Word] = []
        self._closed = False

    # --- Input --------------------------------------------------------------

    def add_pcm(self, pcm: np.ndarray) -> None:
        if self._closed or pcm.size == 0:
            return
        self._audio = np.concatenate((self._audio, pcm.astype(np.float32, copy=False)))
        duration = pcm.size / self.sample_rate
        self._total_seconds += duration
        self._seconds_since_decode += duration

    @property
    def total_seconds(self) -> float:
        return self._total_seconds

    def should_decode(self) -> bool:
        return (
            not self._closed
            and self._seconds_since_decode >= config.MIN_CHUNK_SECONDS
            and self._audio.size > 0
        )

    # --- Decoding -----------------------------------------------------------

    def _prompt(self) -> str:
        # Whisper truncates the prompt anyway; trailing context is what matters.
        return _join(self._committed[-40:])

    def _shift(self, words: list[Word]) -> list[Word]:
        """Move window-relative timestamps onto the absolute session timeline."""
        return [
            Word(w.text, w.start + self._window_origin, w.end + self._window_origin)
            for w in words
        ]

    def _drop_already_committed(self, hypothesis: list[Word]) -> list[Word]:
        """Strip the part of a hypothesis that repeats already-committed words.

        Each decode sees the whole rolling window, so Whisper re-reports words
        we have already committed. Timestamps catch most of them; the n-gram
        check catches the rest, since word boundaries drift between decodes.
        """
        if not self._committed:
            return hypothesis

        floor = self._committed[-1].end - 0.1
        hypothesis = [w for w in hypothesis if w.start > floor]

        overlap = min(len(self._committed), len(hypothesis), 5)
        for n in range(overlap, 0, -1):
            tail = [_normalise(w.text) for w in self._committed[-n:]]
            head = [_normalise(w.text) for w in hypothesis[:n]]
            if tail == head:
                return hypothesis[n:]
        return hypothesis

    def _commit_agreed_prefix(self, hypothesis: list[Word]) -> None:
        """LocalAgreement-2: commit the prefix shared with the previous run."""
        agreed: list[Word] = []
        for previous, current in zip(self._pending, hypothesis):
            if _normalise(previous.text) != _normalise(current.text):
                break
            agreed.append(current)
        self._committed.extend(agreed)
        self._pending = hypothesis[len(agreed):]

    def _trim_window(self) -> None:
        """Drop audio that is fully covered by committed words."""
        window_seconds = self._audio.size / self.sample_rate
        if window_seconds <= config.MAX_WINDOW_SECONDS or not self._committed:
            return

        cut_at = self._committed[-1].end
        if cut_at <= self._window_origin:
            # Nothing committed inside the current window - drop the oldest half
            # so the window cannot grow without bound on unintelligible audio.
            cut_at = self._window_origin + window_seconds / 2

        offset_samples = int((cut_at - self._window_origin) * self.sample_rate)
        offset_samples = max(0, min(offset_samples, self._audio.size))
        self._audio = self._audio[offset_samples:]
        self._window_origin += offset_samples / self.sample_rate

    def decode_step(self) -> dict | None:
        """Decode the rolling window once and return a partial transcript."""
        if self._audio.size == 0:
            return None
        self._seconds_since_decode = 0.0

        hypothesis = self._drop_already_committed(
            self._shift(_run_whisper(self._audio, self._prompt()))
        )
        self._commit_agreed_prefix(hypothesis)
        self._trim_window()
        return self.snapshot(is_final=False)

    def finalize(self) -> dict:
        """Flush the tail: everything still in the window becomes committed."""
        if self._closed:
            return self.snapshot(is_final=True)
        self._closed = True

        if self._audio.size > 0:
            hypothesis = self._drop_already_committed(
                self._shift(_run_whisper(self._audio, self._prompt()))
            )
            self._committed.extend(hypothesis)
            self._pending = []
            self._audio = np.empty(0, dtype=np.float32)

        return self.snapshot(is_final=True)

    # --- Output -------------------------------------------------------------

    def snapshot(self, is_final: bool) -> dict:
        committed = _join(self._committed)
        partial = _join(self._pending)
        return {
            "type": "final" if is_final else "partial",
            "transcript": (committed + " " + partial).strip(),
            "committed": committed,
            "partial": partial,
            "duration": round(self._total_seconds, 2),
            "is_final": is_final,
        }


def transcribe_audio(audio: np.ndarray) -> dict:
    """One-shot decode of a complete recording (non-streaming path)."""
    words = _run_whisper(audio, None)
    return {
        "text": _join(words),
        "language": config.WHISPER_LANGUAGE,
        "duration": round(audio.size / config.SAMPLE_RATE, 2),
    }
