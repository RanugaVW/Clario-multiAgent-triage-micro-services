"""Streaming decoder tests. No Whisper model is loaded - `_run_whisper` is
patched so the LocalAgreement commit policy can be exercised deterministically.
"""

from __future__ import annotations

import numpy as np
import pytest

from app import config, transcriber
from app.transcriber import StreamingSession, Word


def words(*specs: tuple[str, float, float]) -> list[Word]:
    return [Word(text, start, end) for text, start, end in specs]


def one_second() -> np.ndarray:
    return np.zeros(config.SAMPLE_RATE, dtype=np.float32)


@pytest.fixture
def fake_whisper(monkeypatch):
    """Queue up the hypotheses `_run_whisper` should return, in order."""
    queue: list[list[Word]] = []
    prompts: list[str | None] = []

    def fake_run(audio, prompt):
        prompts.append(prompt)
        return queue.pop(0) if queue else []

    monkeypatch.setattr(transcriber, "_run_whisper", fake_run)
    return queue, prompts


def test_nothing_is_committed_until_two_runs_agree(fake_whisper):
    queue, _ = fake_whisper
    session = StreamingSession()

    queue.append(words(("payment", 0.0, 0.5), ("failed", 0.5, 1.0)))
    session.add_pcm(one_second())
    first = session.decode_step()

    # First hypothesis has nothing to agree with yet.
    assert first["committed"] == ""
    assert first["partial"] == "payment failed"
    assert first["transcript"] == "payment failed"
    assert first["is_final"] is False


def test_agreeing_prefix_is_committed(fake_whisper):
    queue, _ = fake_whisper
    session = StreamingSession()

    queue.append(words(("payment", 0.0, 0.5), ("failed", 0.5, 1.0)))
    session.add_pcm(one_second())
    session.decode_step()

    # Second run repeats the same two words and adds more.
    queue.append(
        words(
            ("payment", 0.0, 0.5),
            ("failed", 0.5, 1.0),
            ("twice", 1.1, 1.6),
        )
    )
    session.add_pcm(one_second())
    second = session.decode_step()

    assert second["committed"] == "payment failed"
    assert second["partial"] == "twice"
    assert second["transcript"] == "payment failed twice"


def test_revised_tail_is_not_committed(fake_whisper):
    queue, _ = fake_whisper
    session = StreamingSession()

    queue.append(words(("card", 0.0, 0.4), ("declimed", 0.4, 1.0)))
    session.add_pcm(one_second())
    session.decode_step()

    # Whisper corrects the second word once it has more context; only the
    # word both runs agree on may be committed.
    queue.append(words(("card", 0.0, 0.4), ("declined", 0.4, 1.0)))
    session.add_pcm(one_second())
    result = session.decode_step()

    assert result["committed"] == "card"
    assert result["partial"] == "declined"


def test_punctuation_and_case_do_not_block_agreement(fake_whisper):
    queue, _ = fake_whisper
    session = StreamingSession()

    queue.append(words(("Refund", 0.0, 0.5), ("please", 0.5, 1.0)))
    session.add_pcm(one_second())
    session.decode_step()

    queue.append(words(("refund,", 0.0, 0.5), ("please.", 0.5, 1.0)))
    session.add_pcm(one_second())
    result = session.decode_step()

    assert result["committed"] == "refund, please."


def test_committed_text_is_fed_back_as_the_prompt(fake_whisper):
    queue, prompts = fake_whisper
    session = StreamingSession()

    queue.append(words(("hello", 0.0, 0.5)))
    session.add_pcm(one_second())
    session.decode_step()

    queue.append(words(("hello", 0.0, 0.5), ("there", 0.6, 1.0)))
    session.add_pcm(one_second())
    session.decode_step()

    queue.append(words(("hello", 0.0, 0.5), ("there", 0.6, 1.0)))
    session.add_pcm(one_second())
    session.decode_step()

    assert prompts[0] == ""
    assert prompts[-1] == "hello"


def test_finalize_commits_the_pending_tail(fake_whisper):
    queue, _ = fake_whisper
    session = StreamingSession()

    queue.append(words(("login", 0.0, 0.5), ("broken", 0.5, 1.0)))
    session.add_pcm(one_second())
    session.decode_step()

    queue.append(words(("login", 0.0, 0.5), ("broken", 0.5, 1.0)))
    final = session.finalize()

    assert final["is_final"] is True
    assert final["type"] == "final"
    assert final["transcript"] == "login broken"
    assert final["partial"] == ""


def test_finalize_is_idempotent(fake_whisper):
    queue, _ = fake_whisper
    session = StreamingSession()

    queue.append(words(("done", 0.0, 0.4)))
    session.add_pcm(one_second())

    first = session.finalize()
    second = session.finalize()

    assert first["transcript"] == second["transcript"] == "done"
    # No further audio is accepted once the session has been closed.
    session.add_pcm(one_second())
    assert session.total_seconds == pytest.approx(1.0)


def test_words_already_committed_are_not_emitted_twice(fake_whisper):
    queue, _ = fake_whisper
    session = StreamingSession()

    queue.append(words(("alpha", 0.0, 0.5)))
    session.add_pcm(one_second())
    session.decode_step()

    queue.append(words(("alpha", 0.0, 0.5), ("beta", 0.6, 1.0)))
    session.add_pcm(one_second())
    session.decode_step()  # commits "alpha"

    # A later window re-reports "alpha"; it must be filtered out by timestamp.
    queue.append(words(("alpha", 0.0, 0.5), ("beta", 0.6, 1.0), ("gamma", 1.2, 1.6)))
    session.add_pcm(one_second())
    result = session.decode_step()

    assert result["transcript"].count("alpha") == 1


def test_window_is_trimmed_once_it_exceeds_the_cap(fake_whisper, monkeypatch):
    queue, _ = fake_whisper
    monkeypatch.setattr(config, "MAX_WINDOW_SECONDS", 2.0)
    session = StreamingSession()

    queue.append(words(("one", 0.0, 1.0)))
    session.add_pcm(one_second())
    session.decode_step()

    queue.append(words(("one", 0.0, 1.0), ("two", 1.0, 2.0)))
    session.add_pcm(one_second())
    session.add_pcm(one_second())
    session.decode_step()

    # "one" was committed and its audio (1s) dropped from a 3s window.
    assert session._audio.size == 2 * config.SAMPLE_RATE
    assert session._window_origin == pytest.approx(1.0)


def test_decode_step_on_an_empty_buffer_returns_nothing(fake_whisper):
    assert StreamingSession().decode_step() is None


def test_duration_tracks_all_audio_received(fake_whisper):
    queue, _ = fake_whisper
    session = StreamingSession()
    queue.append([])

    session.add_pcm(one_second())
    session.add_pcm(one_second())
    result = session.decode_step()

    assert result["duration"] == pytest.approx(2.0)
