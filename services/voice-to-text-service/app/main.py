"""FastAPI interface for the Voice-to-Text Service (faster-whisper).

Two entry points:

* ``WS /ws/transcribe`` - real-time streaming. The browser pushes raw 16 kHz
  mono PCM (little-endian int16) frames and receives ``partial``/``final``
  transcript messages as they are decoded.
* ``POST /transcribe`` - one-shot decode of a recorded audio file, used as the
  simple fallback path and for server-to-server calls.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import config
from app.transcriber import (
    StreamingSession,
    _load_model_singleton as load_whisper,
    decode_audio_bytes,
    model_is_ready,
    transcribe_audio,
)

logger = logging.getLogger(__name__)

INT16_TO_FLOAT = 1.0 / 32768.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    import threading

    def preload():
        try:
            logger.info("Preloading faster-whisper model...")
            load_whisper()
            logger.info("faster-whisper preloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to preload model: {e}")

    threading.Thread(target=preload, daemon=True).start()
    yield


app = FastAPI(title="Voice To Text Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TranscribeBase64Request(BaseModel):
    audio_base64: str


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": config.WHISPER_MODEL,
        "model_loaded": model_is_ready(),
    }


# --- One-shot transcription ------------------------------------------------


async def _transcribe_bytes(payload: bytes) -> dict:
    if not payload:
        raise HTTPException(status_code=400, detail="Empty audio payload")
    loop = asyncio.get_running_loop()
    try:
        audio = await loop.run_in_executor(None, decode_audio_bytes, payload)
    except Exception as e:
        logger.error(f"Audio decoding failed: {e}")
        raise HTTPException(status_code=400, detail=f"Unsupported audio: {e}")
    return await loop.run_in_executor(None, transcribe_audio, audio)


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    try:
        return await _transcribe_bytes(await file.read())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe/base64")
async def transcribe_base64(request: TranscribeBase64Request):
    try:
        payload = base64.b64decode(request.audio_base64, validate=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio: {e}")
    try:
        return await _transcribe_bytes(payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Real-time streaming ---------------------------------------------------


def _pcm16_to_float32(raw: bytes) -> np.ndarray:
    # Trailing odd byte would misalign the frame; drop it rather than throw.
    if len(raw) % 2:
        raw = raw[:-1]
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) * INT16_TO_FLOAT


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_running_loop()

    session = StreamingSession()
    # Only the executor thread ever touches ``session``; the receive loop hands
    # audio over through this list so the two never race on the numpy buffer.
    pending: list[np.ndarray] = []
    stop = asyncio.Event()

    def buffered_samples() -> int:
        return sum(chunk.size for chunk in pending)

    def drain(into_session: StreamingSession) -> None:
        chunks, pending[:] = pending[:], []
        if chunks:
            into_session.add_pcm(np.concatenate(chunks))

    def drain_and_decode() -> dict | None:
        drain(session)
        return session.decode_step()

    def drain_and_finalize() -> dict:
        drain(session)
        return session.finalize()

    async def decode_loop() -> None:
        threshold = int(config.MIN_CHUNK_SECONDS * config.SAMPLE_RATE)
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=0.15)
                return
            except asyncio.TimeoutError:
                pass
            if buffered_samples() < threshold:
                continue
            try:
                payload = await loop.run_in_executor(None, drain_and_decode)
            except Exception as e:
                logger.error(f"Streaming decode failed: {e}")
                continue
            if payload is not None and not stop.is_set():
                await websocket.send_json(payload)

    decoder = asyncio.create_task(decode_loop())

    try:
        await websocket.send_json(
            {
                "type": "ready",
                "sample_rate": config.SAMPLE_RATE,
                "model": config.WHISPER_MODEL,
            }
        )

        max_samples = int(config.MAX_SESSION_SECONDS * config.SAMPLE_RATE)
        received_samples = 0

        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return

            raw = message.get("bytes")
            if raw is not None:
                pcm = _pcm16_to_float32(raw)
                received_samples += pcm.size
                if received_samples > max_samples:
                    # Quiesce the decoder first - two coroutines must never
                    # write to the socket at the same time.
                    stop.set()
                    await decoder
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Maximum recording length reached.",
                        }
                    )
                    break
                pending.append(pcm)
                continue

            text = message.get("text")
            if text is None:
                continue
            try:
                command = json.loads(text)
            except json.JSONDecodeError:
                continue
            if command.get("type") in ("stop", "eof"):
                break

        # Stop partial decoding before the final pass so the two cannot overlap
        # on the shared session.
        stop.set()
        await decoder

        final = await loop.run_in_executor(None, drain_and_finalize)
        await websocket.send_json(final)

    except WebSocketDisconnect:
        logger.info("Voice websocket disconnected by client.")
    except Exception as e:
        logger.error(f"Voice websocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        stop.set()
        if not decoder.done():
            decoder.cancel()
            try:
                await decoder
            except (asyncio.CancelledError, Exception):
                pass
        try:
            await websocket.close()
        except Exception:
            pass
