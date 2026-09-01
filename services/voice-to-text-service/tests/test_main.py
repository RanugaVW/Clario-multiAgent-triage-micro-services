"""HTTP and WebSocket surface tests. The Whisper model is never loaded - the
decode function is patched, so these run without downloading model weights.
"""

from __future__ import annotations

import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import config, transcriber
from app.main import app
from app.transcriber import Word


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fake_whisper(monkeypatch):
    """Make every decode return the same two words."""
    calls: list[np.ndarray] = []

    def fake_run(audio, prompt):
        calls.append(audio)
        return [Word("hello", 0.0, 0.5), Word("world", 0.5, 1.0)]

    monkeypatch.setattr(transcriber, "_run_whisper", fake_run)
    return calls


def pcm_bytes(seconds: float) -> bytes:
    samples = int(seconds * config.SAMPLE_RATE)
    # A quiet sine keeps the payload realistic; the decode is patched anyway.
    t = np.arange(samples) / config.SAMPLE_RATE
    wave = (np.sin(2 * np.pi * 220 * t) * 8000).astype("<i2")
    return wave.tobytes()


def test_health_reports_the_configured_model(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model"] == config.WHISPER_MODEL
    assert body["model_loaded"] is False


def test_transcribe_rejects_an_empty_upload(client):
    response = client.post("/transcribe", files={"file": ("empty.wav", b"", "audio/wav")})
    assert response.status_code == 400


def test_transcribe_rejects_undecodable_audio(client):
    response = client.post(
        "/transcribe", files={"file": ("junk.wav", b"not audio at all", "audio/wav")}
    )
    assert response.status_code == 400


def test_transcribe_base64_rejects_invalid_payloads(client):
    response = client.post("/transcribe/base64", json={"audio_base64": "!!!not base64!!!"})
    assert response.status_code == 400


def test_transcribe_returns_text_for_decodable_audio(client, monkeypatch, fake_whisper):
    import app.main as main

    monkeypatch.setattr(
        main, "decode_audio_bytes", lambda payload: np.zeros(config.SAMPLE_RATE, dtype=np.float32)
    )
    response = client.post(
        "/transcribe", files={"file": ("clip.wav", pcm_bytes(1.0), "audio/wav")}
    )

    assert response.status_code == 200
    assert response.json()["text"] == "hello world"


def test_websocket_announces_readiness(client, fake_whisper):
    with client.websocket_connect("/ws/transcribe") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert ready["sample_rate"] == config.SAMPLE_RATE
        ws.send_json({"type": "stop"})


def test_websocket_streams_a_partial_then_a_final(client, fake_whisper):
    with client.websocket_connect("/ws/transcribe") as ws:
        assert ws.receive_json()["type"] == "ready"

        ws.send_bytes(pcm_bytes(1.5))
        # Let the decode loop pick the buffered audio up before we stop.
        time.sleep(0.8)
        ws.send_json({"type": "stop"})

        seen = []
        for _ in range(10):
            message = ws.receive_json()
            seen.append(message)
            if message["is_final"]:
                break

    assert seen[-1]["type"] == "final"
    assert seen[-1]["transcript"] == "hello world"
    assert seen[-1]["partial"] == ""
    assert any(m["type"] == "partial" for m in seen), "expected a live partial"


def test_websocket_finalizes_even_without_a_partial(client, fake_whisper):
    with client.websocket_connect("/ws/transcribe") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_bytes(pcm_bytes(0.5))
        ws.send_json({"type": "stop"})
        final = ws.receive_json()

    assert final["type"] == "final"
    assert final["transcript"] == "hello world"


def test_websocket_ignores_malformed_control_frames(client, fake_whisper):
    with client.websocket_connect("/ws/transcribe") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_text("this is not json")
        ws.send_json({"type": "keepalive"})
        ws.send_bytes(pcm_bytes(0.3))
        ws.send_json({"type": "stop"})
        final = ws.receive_json()

    assert final["type"] == "final"


def test_websocket_stops_a_session_that_runs_too_long(client, fake_whisper, monkeypatch):
    monkeypatch.setattr(config, "MAX_SESSION_SECONDS", 1.0)

    with client.websocket_connect("/ws/transcribe") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_bytes(pcm_bytes(2.0))
        message = ws.receive_json()

    assert message["type"] == "error"
    assert "Maximum recording length" in message["message"]


def test_odd_length_frames_do_not_break_pcm_conversion():
    from app.main import _pcm16_to_float32

    # A frame split mid-sample must be tolerated, not raise.
    pcm = _pcm16_to_float32(pcm_bytes(0.01) + b"\x00")
    assert pcm.dtype == np.float32
    assert np.all(np.abs(pcm) <= 1.0)


def test_a_failing_decode_reports_an_error_once_and_stops(client, monkeypatch):
    """A broken model must fail fast, not retry on every audio chunk."""
    attempts = []

    def exploding_run(audio, prompt):
        attempts.append(audio)
        raise ModuleNotFoundError("No module named 'requests'")

    monkeypatch.setattr(transcriber, "_run_whisper", exploding_run)

    with client.websocket_connect("/ws/transcribe") as ws:
        assert ws.receive_json()["type"] == "ready"
        # Several chunks worth of audio; only the first should reach the model.
        for _ in range(4):
            ws.send_bytes(pcm_bytes(1.2))
            time.sleep(0.3)
        message = ws.receive_json()

    assert message["type"] == "error"
    assert "requests" in message["message"]
    assert len(attempts) == 1, f"decode retried {len(attempts)} times"
