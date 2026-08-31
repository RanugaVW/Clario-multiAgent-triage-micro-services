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
window exceeds `VOICE_MAX_WINDOW_SECONDS` - that bound exists to keep the window
inside Whisper's single 30s encoder pass, not to make decoding faster (see
[Latency](#latency)).

Pressing stop does not always cost another decode: if no meaningful audio has
arrived since the last one, the standing partial is promoted straight to final.

Silero VAD (`vad_filter=True`) drops silence before decoding, so pauses do not
produce hallucinated text.

## Configuration

All settings are environment variables with working defaults - see
[`app/config.py`](app/config.py).

| Variable                     | Default | Notes                                              |
| ---------------------------- | ------- | -------------------------------------------------- |
| `WHISPER_MODEL`              | `base`  | `tiny`/`base`/`small`/`medium`/`large-v3` or a path.|
| `WHISPER_DEVICE`             | `auto`  | `cpu` or `cuda`.                                    |
| `WHISPER_COMPUTE_TYPE`       | `int8`  | `float16` on GPU.                                   |
| `WHISPER_LANGUAGE`           | `en`    | Empty string enables auto-detection.                |
| `WHISPER_BEAM_SIZE`          | `1`     | Greedy decoding keeps streaming latency low.        |
| `WHISPER_CACHE_DIR`          | `/models` | Where model snapshots are downloaded.             |
| `WHISPER_TEMPERATURE`        | `0.0`   | Single temperature - see below, this one matters.   |
| `WHISPER_REPETITION_PENALTY` | `1.1`   | Mild anti-looping on hard windows.                  |
| `VOICE_MIN_CHUNK_SECONDS`    | `1.0`   | Fresh audio needed before the next partial decode.  |
| `VOICE_MAX_WINDOW_SECONDS`   | `22.0`  | Rolling-window cap handed to Whisper.               |
| `VOICE_WINDOW_CONTEXT_WORDS` | `3`     | Committed words kept as context after trimming.     |
| `VOICE_MAX_SESSION_SECONDS`  | `300.0` | Hard limit on a single recording.                   |

See [Latency](#latency) for how to choose the model size.

## Latency

Streaming latency is bounded by **how long a single decode takes**, because a
partial can only be emitted once a decode finishes. Two properties drive this:

* Whisper pads every input to a **30 second** mel window, so decode time is
  near-flat in window length - decoding 5s costs about the same as decoding 15s.
  Trimming the rolling window therefore does *not* buy speed; it only keeps the
  window under 30s so one encoder pass is enough.
* That makes **model size the dominant lever.**

Measured in this container (int8, CPU, 12 cores, 15s of real speech; all three
sizes produced an identical, correct transcript):

| Model   | Decode per window | Partial lag behind speech |
| ------- | ----------------- | ------------------------- |
| `tiny`  | ~0.8s             | under a second            |
| `base`  | ~1.4s             | ~1.5s (default)           |
| `small` | ~3.9s             | ~4s - noticeably behind    |

If dictation feels slow, set `WHISPER_MODEL=tiny` first. Go above `base` only
with a GPU (`WHISPER_DEVICE=cuda`, `WHISPER_COMPUTE_TYPE=float16`), where the
larger models are worth their accuracy.

### Why `WHISPER_TEMPERATURE` is a single value

faster-whisper's default is a *ladder* - `[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]`. When
a decode trips its compression-ratio or logprob checks the whole decode is
retried at the next temperature, up to six times. Short mid-sentence windows
trip those checks routinely, and the retries are invisible: a 3.7s window was
measured taking **17.0s**, stalling the stream for the length of the clip.

Pinning a single temperature caps a decode at one pass. Streaming re-decodes
every second anyway, so a weak partial is corrected on the next pass rather than
by an expensive retry the user waits through. Restore the ladder only for the
one-shot `/transcribe` endpoint's accuracy, never for streaming.

The service logs `decode window=... elapsed=...` at WARNING whenever a decode
takes longer than the audio it covers, which is the signal that the transcript
is falling behind the speaker.

`small` also holds ~1.4GB resident, which matters when the whole compose stack
shares one Docker memory budget - it is easy to get the container OOM-killed
(exit 137) alongside the other ML services.

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

The tests patch out the model, so they exercise the streaming commit policy and
the full WebSocket protocol without downloading Whisper weights.
