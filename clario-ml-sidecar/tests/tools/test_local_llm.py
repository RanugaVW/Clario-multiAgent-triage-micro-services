"""Classification taxonomy: locks in the categories the adapter was fine-tuned on.

classify_ticket_local() itself isn't exercised here - it requires loading the
real ~1B-param Gemma-3 model. Empirically verified against the live adapter
(gemma3-lms-ticket-adapter-final) that it correctly classifies into every one
of these six categories when the prompt asks for them, rather than the
coarser Technical/Billing/Account/General/Other set it was previously
constrained to.
"""

import pytest

from app.agents.shared.prompt_templates import build_specialist_prompt
from app.tools.local_llm import FINE_GRAINED_CATEGORIES, DraftGenerationError, generate_draft


def test_fine_grained_categories_match_the_adapters_training_taxonomy() -> None:
    assert FINE_GRAINED_CATEGORIES == (
        "Login Issue",
        "Payment Problem",
        "Account Suspension",
        "Bug Report",
        "Refund Request",
        "Subscription Cancellation",
    )


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
