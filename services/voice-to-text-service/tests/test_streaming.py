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


def test_finalize_skips_a_redundant_decode_when_no_new_audio(fake_whisper):
    """Stop should not cost a whole extra decode for audio already decoded."""
    queue, _ = fake_whisper
    session = StreamingSession()

    queue.append(words(("all", 0.0, 0.4), ("done", 0.4, 0.9)))
    session.add_pcm(one_second())
    session.decode_step()

    decodes_before = len(queue)
    final = session.finalize()

    # The queue is untouched: no second call into the model was made.
    assert len(queue) == decodes_before
    # The standing partial was promoted rather than recomputed.
    assert final["transcript"] == "all done"
    assert final["partial"] == ""
    assert final["is_final"] is True


def test_finalize_still_decodes_audio_arriving_after_the_last_decode(fake_whisper):
    queue, _ = fake_whisper
    session = StreamingSession()

    queue.append(words(("first", 0.0, 0.5)))
    session.add_pcm(one_second())
    session.decode_step()

    # A full second of speech landed after that decode - it must not be dropped.
    session.add_pcm(one_second())
    queue.append(words(("first", 0.0, 0.5), ("second", 1.1, 1.6)))
    final = session.finalize()

    assert final["transcript"] == "first second"
    assert queue == []


def test_new_words_survive_a_backward_timestamp_drift():
    """Regression: a later decode placing words earlier must not delete them.

    Observed on real speech as silently missing words ("still taken from my
    bank account" -> "still taken bank account"). A timestamp-first filter
    dropped anything starting before the committed end, and Whisper routinely
    shifts word boundaries earlier once it has more audio.
    """
    session = StreamingSession()
    session._committed = words(("still", 3.6, 4.0), ("taken", 4.0, 4.5))

    # Same two words re-reported, now placed earlier, plus two genuinely new
    # words that both start before the committed end of 4.5.
    hypothesis = words(
        ("still", 3.5, 3.9),
        ("taken", 3.9, 4.2),
        ("from", 4.2, 4.4),
        ("my", 4.4, 4.6),
    )

    kept = session._drop_already_committed(hypothesis)
    assert [w.text for w in kept] == ["from", "my"]


def test_committed_repeats_are_still_stripped():
    session = StreamingSession()
    session._committed = words(("alpha", 1.0, 1.4), ("beta", 1.4, 1.8))

    hypothesis = words(("alpha", 1.0, 1.4), ("beta", 1.4, 1.8), ("gamma", 1.8, 2.2))
    kept = session._drop_already_committed(hypothesis)

    assert [w.text for w in kept] == ["gamma"]


def test_window_is_trimmed_after_every_decode_not_only_at_the_cap(fake_whisper):
    """Short windows keep the re-reported overlap small; decode cost is flat."""
    queue, _ = fake_whisper
    session = StreamingSession()

    queue.append(words(("one", 0.0, 1.0), ("two", 1.0, 2.0)))
    session.add_pcm(one_second())
    session.add_pcm(one_second())
    session.decode_step()

    queue.append(words(("one", 0.0, 1.0), ("two", 1.0, 2.0)))
    session.add_pcm(one_second())
    session.decode_step()  # commits both words

    # Well under MAX_WINDOW_SECONDS, yet trimmed: committed audio is dropped
    # down to the configured context margin.
    # Cut at the onset of the oldest kept context word, not a time offset.
    context = session._committed[-config.WINDOW_CONTEXT_WORDS:]
    assert session._window_origin == pytest.approx(context[0].start)
    assert session._audio.size <= 3 * config.SAMPLE_RATE
