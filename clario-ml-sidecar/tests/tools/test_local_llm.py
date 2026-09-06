"""Classification taxonomy and JSON-repair coverage for the Llama-3.2 adapter.

classify_ticket_local() itself isn't exercised here - it requires loading the
real ~3B-param Llama-3.2 model on a GPU. PRIORITY_LABELS/SENTIMENT_LABELS and
_repair_json_quoting() were both derived from probing the live adapter
directly against real ticket text (see app/tools/local_llm.py's comments):
its trained sentiment scale tops out at "Negative" (confirmed live - even
when explicitly offered "Strongly Negative" as an option, it produced
malformed output rather than a correct "Strongly Negative" classification),
and it reliably emits bare/partially-quoted JSON string values often enough
that _repair_json_quoting() is load-bearing, not defensive.
"""

import pytest
import torch

from app.agents.shared.prompt_templates import build_specialist_prompt
from app.tools.local_llm import (
    PRIORITY_LABELS,
    SENTIMENT_LABELS,
    DraftGenerationError,
    _repair_json_quoting,
    _sequence_confidence,
    generate_draft,
)


def test_priority_and_sentiment_labels_match_the_adapters_training_taxonomy() -> None:
    assert PRIORITY_LABELS == ("Low", "Medium", "High", "Critical")
    assert SENTIMENT_LABELS == ("Positive", "Neutral", "Negative")


@pytest.mark.parametrize(("raw", "expected"), [
    # Fully unquoted values - the most common real failure mode.
    (
        '{"priority": High, "sentiment": Negative, "category": Login}',
        '{"priority": "High", "sentiment": "Negative", "category": "Login"}',
    ),
    # A stray trailing quote with no leading one, on a multi-word value.
    (
        '{"priority": "High", "sentiment": Negative, "category": General Support"}',
        '{"priority": "High", "sentiment": "Negative", "category": "General Support"}',
    ),
    # Already fully valid - must be a no-op (idempotent).
    (
        '{"priority": "Medium", "sentiment": "Neutral", "category": "Refund Request"}',
        '{"priority": "Medium", "sentiment": "Neutral", "category": "Refund Request"}',
    ),
])
def test_repair_json_quoting_fixes_the_adapters_real_output_shapes(raw: str, expected: str) -> None:
    assert _repair_json_quoting(raw) == expected


# _sequence_confidence() replaces classify_ticket_local()'s old hardcoded
# 0.85/0.0 confidence with a real per-response measure derived from the
# model's own greedy-decoding logits. These tests pin down its required
# BEHAVIOR (bounds, monotonicity, degenerate cases) without pinning down
# which folding formula is used - any reasonable implementation (geometric
# mean, arithmetic mean, min-probability, ...) must satisfy all of them.

def test_sequence_confidence_returns_zero_for_empty_generation() -> None:
    assert _sequence_confidence((), torch.tensor([], dtype=torch.long)) == 0.0


def test_sequence_confidence_is_one_when_every_step_is_fully_certain() -> None:
    # Step 1: token 0 has all the probability mass. Step 2: token 1 does.
    scores = (
        torch.tensor([[50.0, -50.0]]),
        torch.tensor([[-50.0, 50.0]]),
    )
    generated_ids = torch.tensor([0, 1])
    assert _sequence_confidence(scores, generated_ids) == pytest.approx(1.0, abs=1e-3)


def test_sequence_confidence_is_lower_when_the_chosen_token_was_less_certain() -> None:
    certain_scores = (torch.tensor([[10.0, 0.0]]),)  # chosen token's prob ~1.0
    uncertain_scores = (torch.tensor([[0.0, 0.0]]),)  # chosen token's prob = 0.5

    certain = _sequence_confidence(certain_scores, torch.tensor([0]))
    uncertain = _sequence_confidence(uncertain_scores, torch.tensor([0]))

    assert uncertain < certain


def test_sequence_confidence_stays_within_zero_and_one() -> None:
    scores = (
        torch.tensor([[3.0, -1.0, 0.5]]),
        torch.tensor([[-2.0, 4.0, 0.0]]),
        torch.tensor([[1.0, 1.0, 1.0]]),
    )
    generated_ids = torch.tensor([0, 1, 2])
    confidence = _sequence_confidence(scores, generated_ids)
    assert 0.0 <= confidence <= 1.0


# generate_draft() calls the real Gemini API (google.genai), not the heavy
# local model - unlike classify_ticket_local, it's cheap to mock and test.

_PROMPT = build_specialist_prompt(
    "My payment failed",
    [{"source_file": "billing/payment_failed.md", "text": "Check the payment processor."}],
    "billing",
)


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)  # each item: a JSON str, or an Exception to raise

    def generate_content(self, **kwargs):
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakeResponse(item)


class _FakeClient:
    """generate_draft() calls genai.Client() fresh inside every retry
    iteration - each fake client must share the same underlying response
    queue so attempts consume it in order, rather than each getting its own
    fresh copy."""

    def __init__(self, models: _FakeModels) -> None:
        self.models = models


def _client_factory(monkeypatch, *responses) -> None:
    shared_models = _FakeModels(list(responses))
    monkeypatch.setattr("app.tools.local_llm.genai.Client", lambda: _FakeClient(shared_models))


_VALID_JSON = '{"technical_report": "Root cause identified.", "user_solution": "Here is the fix."}'


def test_generate_draft_returns_text_and_attempt_count_on_first_try(monkeypatch) -> None:
    _client_factory(monkeypatch, _VALID_JSON)

    text, attempts = generate_draft(_PROMPT)

    assert "Here is the fix." in text
    assert attempts == 1


def test_generate_draft_retries_and_reports_the_real_attempt_count(monkeypatch) -> None:
    _client_factory(monkeypatch, RuntimeError("503 unavailable"), _VALID_JSON)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    text, attempts = generate_draft(_PROMPT)

    assert "Here is the fix." in text
    assert attempts == 2


def test_generate_draft_raises_after_every_retry_instead_of_faking_a_draft(monkeypatch) -> None:
    """A real failure must never come back disguised as a real customer-facing draft."""
    _client_factory(monkeypatch, RuntimeError("503"), RuntimeError("503"), RuntimeError("503"))
    monkeypatch.setattr("time.sleep", lambda *_: None)

    with pytest.raises(DraftGenerationError) as exc_info:
        generate_draft(_PROMPT)

    assert exc_info.value.attempts == 3


def test_generate_draft_makes_no_api_call_when_context_is_missing() -> None:
    text, attempts = generate_draft("Ticket:\nHello\n\nRetrieved context:\n")

    assert "don't have enough information" in text
    assert attempts == 0
