# Voice To Text Service

Speech-to-text microservice built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
It is the fallback engine behind the microphone button in the Clario dashboard:
Chrome and Edge use the browser's own Google-backed Web Speech API, and every
other browser - or any Chrome where that service fails - streams audio here
instead.

Runs on port **8000** inside the container, published on **8002** on the host.

## Endpoints

| Method | Path                 | Purpose                                                  |
| ------ | -------------------- | -------------------------------------------------------- |
| `GET`  | `/health`            | Liveness plus whether the model finished preloading.      |
| `WS`   | `/ws/transcribe`     | Real-time streaming transcription.                        |
| `POST` | `/transcribe`        | One-shot decode of an uploaded audio file (multipart).    |
| `POST` | `/transcribe/base64` | One-shot decode of base64 audio, matching the OCR service.|

### Streaming protocol

1. Client connects to `/ws/transcribe` and waits for `{"type": "ready"}`.
2. Client sends **binary** frames of raw mono PCM, 16 kHz, little-endian int16.
3. Server replies with JSON as it decodes:

   ```json
   {
     "type": "partial",
     "transcript": "payment failed but the money",
     "committed": "payment failed but the",
     "partial": "money",
     "duration": 3.2,
     "is_final": false
   }
   ```

   `committed` will never change again; `partial` is the moving tail.
4. Client sends `{"type": "stop"}` to finish. The server flushes the tail and
   replies once with `"type": "final"`, then closes.

### How real-time decoding works

Whisper is not a streaming model, so the service re-decodes a rolling window
roughly once a second and uses the **LocalAgreement-2** policy: only the word
prefix that two consecutive decodes agree on is committed. That gives a stable
transcript that grows forward instead of flickering. Committed text is fed back
as the `initial_prompt`, and its audio is trimmed out of the window once the
window exceeds `VOICE_MAX_WINDOW_SECONDS`, which keeps latency flat no matter
how long the recording runs.

Silero VAD (`vad_filter=True`) drops silence before decoding, so pauses do not
produce hallucinated text.

## Configuration

All settings are environment variables with working defaults - see
[`app/config.py`](app/config.py).

| Variable                     | Default | Notes                                              |
| ---------------------------- | ------- | -------------------------------------------------- |
| `WHISPER_MODEL`              | `small` | `tiny`/`base`/`small`/`medium`/`large-v3` or a path.|
| `WHISPER_DEVICE`             | `auto`  | `cpu` or `cuda`.                                    |
| `WHISPER_COMPUTE_TYPE`       | `int8`  | `float16` on GPU.                                   |
| `WHISPER_LANGUAGE`           | `en`    | Empty string enables auto-detection.                |
| `WHISPER_BEAM_SIZE`          | `1`     | Greedy decoding keeps streaming latency low.        |
| `WHISPER_CACHE_DIR`          | `/models` | Where model snapshots are downloaded.             |
| `VOICE_MIN_CHUNK_SECONDS`    | `1.0`   | Fresh audio needed before the next partial decode.  |
| `VOICE_MAX_WINDOW_SECONDS`   | `22.0`  | Rolling-window cap handed to Whisper.               |
| `VOICE_MAX_SESSION_SECONDS`  | `300.0` | Hard limit on a single recording.                   |

`tiny`/`base` are noticeably faster on CPU if partials lag behind speech;
`medium` and up are worth it only with a GPU.

## Running

### Docker (from the repository root)

```bash
docker compose up --build voice-to-text-service
```

The model snapshot is cached in the `whisper-models` volume, so only the first
start pays the download cost.

### Locally

```bash
cd services/voice-to-text-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

This is exactly what the "Voice To Text" tab in `start-all.sh` runs.

Audio containers (webm/ogg/wav) are decoded through the PyAV libraries bundled
with faster-whisper, so no system `ffmpeg` install is required.

## Tests

```bash
pytest tests/
```

The tests patch out the model, so they exercise the streaming commit policy
without downloading Whisper weights.
