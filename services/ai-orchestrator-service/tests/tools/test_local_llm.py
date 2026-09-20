"""Prompt, output-parsing, confidence and fallback coverage for the Llama-3.2 v2 adapter.

classify_ticket_local()'s model call needs the real ~3B-param model on a GPU,
so it is exercised here with _load_model/_generate_verdict stubbed; everything
around the model call - the prompt it is fed, how its raw text is turned into
validated labels, its confidence, and the Gemini fallback - is tested directly.
"""

import json

import pytest
import torch

from app.agents.shared.prompt_templates import build_specialist_prompt
from app.tools import local_llm
from app.tools.local_llm import (
    SYSTEM_PROMPT,
    DraftGenerationError,
    _adapter_base_model,
    _check_adapter_taxonomy,
    _extract_final_json,
    _category_confidence,
    _category_token_probabilities,
    _load_model,
    _parse_specialist_prompt,
    build_classification_prompt,
    classify_ticket_local,
    generate_draft,
)
from app.tools.taxonomy import CATEGORY_LABELS


# ---------------------------------------------------------------- the prompt

# The adapter was fine-tuned on exactly this string (see the training notebook,
# ml_finetuning/notebooks/Llama32_Clario_Finetune.ipynb); any drift changes the
# input distribution the reported accuracy was measured on.
_TRAINING_SYSTEM_PROMPT = (
    "You are Clario, an intelligent IT support ticket triage assistant.\n"
    "Given a product name and issue description, think step by step covering: "
    "user intent, urgency, tone/sentiment, and category. Then output your final answer.\n\n"
    "Respond with your step-by-step reasoning first, then on a new line output ONLY "
    "the final JSON in this exact format (category is a LIST — a ticket may belong "
    "to more than one category):\n"
    '{"priority": "<Low|Medium|High|Critical>", "sentiment": "<Neutral|Negative|Frustrated>", '
    '"category": ["<one or more of: Account Access, Authentication, Billing & Invoicing, '
    'Content & Media, Data Integrity, Feature Request, Performance, Refunds, Service Outage, '
    'Subscription Management, Technical Support, UI/UX>"]}'
)


def test_system_prompt_is_identical_to_the_one_used_for_fine_tuning() -> None:
    assert SYSTEM_PROMPT == _TRAINING_SYSTEM_PROMPT


def test_classification_prompt_matches_the_fine_tuning_chat_layout() -> None:
    assert build_classification_prompt("My card was charged twice", product="Payment & Billing") == (
        "<|begin_of_text|>"
        f"<|start_header_id|>system<|end_header_id|>\n{_TRAINING_SYSTEM_PROMPT}<|eot_id|>"
        "<|start_header_id|>user<|end_header_id|>\nProduct: Payment & Billing\n"
        "Issue: My card was charged twice<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n"
    )


def test_classification_prompt_defaults_to_a_neutral_product_and_skips_the_stock_date_preamble() -> None:
    prompt = build_classification_prompt("Cannot log in")
    assert "Product: General Support\nIssue: Cannot log in" in prompt
    assert "Cutting Knowledge Date" not in prompt


# ------------------------------------------------------------ output parsing

_VERDICT = '{"priority": "High", "sentiment": "Frustrated", "category": ["Refunds", "Billing & Invoicing"]}'
_RESPONSE = "Step 1: The customer wants a refund. Step 2: urgent.\n" + _VERDICT


def test_extract_final_json_takes_the_trailing_verdict_after_the_reasoning() -> None:
    assert _extract_final_json(_RESPONSE) == {
        "priority": "High", "sentiment": "Frustrated", "category": ["Refunds", "Billing & Invoicing"],
    }


@pytest.mark.parametrize("response", [
    "no json here at all",
    "reasoning only {unterminated",
    '{"priority": High}',            # not valid JSON
    "trailing brace only }",
    "[1, 2, 3]",
    "",
])
def test_extract_final_json_returns_none_when_there_is_no_valid_object(response) -> None:
    assert _extract_final_json(response) is None


# -------------------------------------------------------------- confidence

def _pieces(response: str, size: int = 4) -> list[str]:
    return [response[i:i + size] for i in range(0, len(response), size)]


def _probs_with(response: str, pieces: list[str], low_for: set[str], low: float = 0.5, default: float = 0.99) -> list[float]:
    """Probabilities that are `low` for every token overlapping one of the given substrings."""
    spans = [(response.rfind(text), response.rfind(text) + len(text)) for text in low_for]
    probs, offset = [], 0
    for piece in pieces:
        start, end = offset, offset + len(piece)
        offset = end
        probs.append(low if any(start < e and end > s for s, e in spans) else default)
    return probs


def test_category_token_probabilities_only_cover_the_category_labels() -> None:
    pieces = _pieces(_RESPONSE)
    probs = _probs_with(_RESPONSE, pieces, {"Refunds", "Billing & Invoicing"})
    category_probs = _category_token_probabilities(_RESPONSE, pieces, probs)
    assert category_probs and set(category_probs) == {0.5}


def test_category_confidence_is_the_weakest_category_token() -> None:
    pieces = _pieces(_RESPONSE, size=1)
    probs = [1.0] * len(pieces)
    probs[_RESPONSE.rfind("Refunds") + 2] = 0.42  # one uncertain character inside a category label
    assert _category_confidence(_RESPONSE, pieces, probs) == pytest.approx(0.42)


def test_category_confidence_ignores_uncertainty_in_priority_sentiment_and_reasoning() -> None:
    # Measured on 150 held-out tickets, the model's certainty about sentiment and priority says
    # nothing reliable about whether they are right, while its certainty about the category does
    # (AUROC 0.83) - so only the category tokens feed the confidence routing relies on.
    pieces = _pieces(_RESPONSE, size=1)
    probs = _probs_with(_RESPONSE, pieces, {"Step 1", "High", "Frustrated"}, low=0.2, default=1.0)
    assert _category_confidence(_RESPONSE, pieces, probs) == pytest.approx(1.0)


def test_category_confidence_covers_every_label_of_a_multi_label_answer() -> None:
    pieces = _pieces(_RESPONSE, size=1)
    probs = _probs_with(_RESPONSE, pieces, {"Billing & Invoicing"}, low=0.3, default=1.0)
    assert _category_confidence(_RESPONSE, pieces, probs) == pytest.approx(0.3)


def test_category_confidence_is_zero_without_a_verdict() -> None:
    assert _category_confidence("just reasoning", ["just reasoning"], [0.9]) == 0.0


def test_category_confidence_stays_within_zero_and_one() -> None:
    pieces = _pieces(_RESPONSE)
    assert 0.0 <= _category_confidence(_RESPONSE, pieces, [0.7] * len(pieces)) <= 1.0


# ------------------------------------------------------------- model loading

def test_adapter_base_model_is_read_from_the_adapters_own_config(tmp_path) -> None:
    (tmp_path / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "meta-llama/Llama-3.2-3B-Instruct"}))
    assert _adapter_base_model(str(tmp_path)) == "meta-llama/Llama-3.2-3B-Instruct"


def _write_label_maps(directory, **overrides) -> None:
    maps = {
        "categories": list(CATEGORY_LABELS),
        "priorities": ["Low", "Medium", "High", "Critical"],
        "sentiments": ["Neutral", "Negative", "Frustrated"],
    }
    maps.update(overrides)
    (directory / "label_maps.json").write_text(json.dumps(maps))


def test_check_adapter_taxonomy_accepts_an_adapter_trained_on_this_taxonomy(tmp_path) -> None:
    _write_label_maps(tmp_path)
    _check_adapter_taxonomy(str(tmp_path))  # no exception


def test_check_adapter_taxonomy_rejects_an_adapter_without_label_maps(tmp_path) -> None:
    # e.g. the previous adapter, which has no label_maps.json: its prompt and
    # output format are different, so it would answer garbage, silently.
    with pytest.raises(ValueError, match="label_maps.json"):
        _check_adapter_taxonomy(str(tmp_path))


@pytest.mark.parametrize("override", [
    {"categories": ["Billing", "Technical"]},
    {"priorities": ["Low", "Medium", "High", "Urgent"]},
    {"sentiments": ["Positive", "Neutral", "Negative"]},
])
def test_check_adapter_taxonomy_rejects_an_adapter_with_different_labels(tmp_path, override) -> None:
    _write_label_maps(tmp_path, **override)
    with pytest.raises(ValueError, match="taxonomy"):
        _check_adapter_taxonomy(str(tmp_path))


def test_load_model_requires_a_cuda_gpu(monkeypatch) -> None:
    monkeypatch.setattr(local_llm, "_model", None)
    monkeypatch.setattr(local_llm.torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA"):
        _load_model()


def test_load_model_refuses_to_run_a_bare_base_model_when_the_adapter_is_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(local_llm, "_model", None)
    monkeypatch.setattr(local_llm.torch.cuda, "is_available", lambda: True)
    monkeypatch.setenv("LLAMA_ADAPTER_PATH", str(tmp_path / "missing"))
    with pytest.raises(FileNotFoundError):
        _load_model()


# --------------------------------------------- classify_ticket_local wiring

def _stub_local_model(monkeypatch, response: str = _RESPONSE) -> None:
    pieces = _pieces(response)
    monkeypatch.setattr(local_llm, "_load_model", lambda: None)
    monkeypatch.setattr(local_llm, "_generate_verdict", lambda text: (response, pieces, [0.9] * len(pieces)))


def test_classify_ticket_local_returns_validated_labels_and_provenance(monkeypatch) -> None:
    _stub_local_model(monkeypatch)

    result = classify_ticket_local("I want a refund, this is unacceptable")

    assert result["priority"] == "High"
    assert result["sentiment"] == "Frustrated"
    assert result["categories"] == ["Refunds", "Billing & Invoicing"]
    assert result["category"] == "Refunds, Billing & Invoicing"
    assert result["source"] == "llama32_lora_v2"
    assert 0.0 < result["confidence"] <= 1.0


def test_classify_ticket_local_drops_labels_outside_the_taxonomy(monkeypatch) -> None:
    verdict = '{"priority": "Critical", "sentiment": "Negative", "category": ["Security", "Authentication"]}'
    _stub_local_model(monkeypatch, "reasoning\n" + verdict)

    result = classify_ticket_local("account hacked")

    assert result["categories"] == ["Authentication"]


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeGemini:
    def __init__(self, text: str | Exception) -> None:
        self._text = text
        self.models = self

    def generate_content(self, **kwargs):
        if isinstance(self._text, Exception):
            raise self._text
        return _FakeResponse(self._text)


_GEMINI_JSON = '{"priority": "medium", "sentiment": "neutral", "category": ["Technical Support"]}'


def test_classify_ticket_local_falls_back_to_gemini_when_the_model_cannot_load(monkeypatch) -> None:
    def _boom():
        raise RuntimeError("No CUDA GPU available")

    monkeypatch.setattr(local_llm, "_load_model", _boom)
    monkeypatch.setattr(local_llm.genai, "Client", lambda: _FakeGemini(_GEMINI_JSON))

    result = classify_ticket_local("the page is broken")

    assert result["source"] == "gemini_fallback"
    assert (result["priority"], result["sentiment"], result["categories"]) == ("Medium", "Neutral", ["Technical Support"])


def test_classify_ticket_local_falls_back_to_gemini_when_the_model_output_is_unusable(monkeypatch) -> None:
    _stub_local_model(monkeypatch, "I could not decide, sorry.")
    monkeypatch.setattr(local_llm.genai, "Client", lambda: _FakeGemini(_GEMINI_JSON))

    assert classify_ticket_local("something")["source"] == "gemini_fallback"


def test_gemini_fallback_speaks_the_same_taxonomy_as_the_local_model(monkeypatch) -> None:
    monkeypatch.setattr(local_llm.genai, "Client", lambda: _FakeGemini(
        '{"priority": "Urgent", "sentiment": "Positive", "category": ["Login"]}'
    ))
    monkeypatch.setattr(local_llm, "_load_model", lambda: (_ for _ in ()).throw(RuntimeError("no gpu")))

    result = classify_ticket_local("help")

    # Labels from another scheme are rejected, never passed downstream.
    assert result["source"] == "classification_failed"
    assert result["confidence"] == 0.0


def test_classify_ticket_local_reports_failure_when_both_backends_fail(monkeypatch) -> None:
    def _boom():
        raise RuntimeError("no gpu")

    monkeypatch.setattr(local_llm, "_load_model", _boom)
    monkeypatch.setattr(local_llm.genai, "Client", lambda: _FakeGemini(RuntimeError("quota")))

    result = classify_ticket_local("help")

    assert result["source"] == "classification_failed"
    assert result["confidence"] == 0.0
    assert result["categories"] == []


def test_every_taxonomy_label_survives_a_round_trip_through_the_local_path(monkeypatch) -> None:
    for label in CATEGORY_LABELS:
        _stub_local_model(monkeypatch, f'x\n{{"priority": "Low", "sentiment": "Neutral", "category": ["{label}"]}}')
        assert classify_ticket_local("t")["categories"] == [label]


# _parse_specialist_prompt() is what lets generate_draft() see the
# priority/sentiment build_specialist_prompt() now optionally includes -
# tested directly since it's a pure string-parsing function, same reasoning
# as _extract_final_json/_category_confidence above.

def test_parse_specialist_prompt_extracts_priority_and_sentiment_when_present() -> None:
    prompt = build_specialist_prompt(
        "My payment failed", [{"source_file": "billing/payment_failed.md", "text": "Check it."}],
        "billing", priority="High", sentiment="Frustrated",
    )
    ticket_text, context_chunks, priority, sentiment = _parse_specialist_prompt(prompt)
    assert ticket_text == "My payment failed"
    assert priority == "High"
    assert sentiment == "Frustrated"
    assert context_chunks == [{"source": "Source: billing/payment_failed.md", "text": "Check it."}]


def test_parse_specialist_prompt_returns_none_when_absent() -> None:
    prompt = build_specialist_prompt(
        "My payment failed", [{"source_file": "billing/payment_failed.md", "text": "Check it."}], "billing",
    )
    _, _, priority, sentiment = _parse_specialist_prompt(prompt)
    assert priority is None
    assert sentiment is None


# generate_draft() calls the real Gemini API (google.genai), not the heavy
# local model - unlike classify_ticket_local, it's cheap to mock and test.

_PROMPT = build_specialist_prompt(
    "My payment failed",
    [{"source_file": "billing/payment_failed.md", "text": "Check the payment processor."}],
    "billing",
    priority="High",
    sentiment="Frustrated",
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
