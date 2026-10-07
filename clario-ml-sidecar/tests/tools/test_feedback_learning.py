"""Shared helpers for the live-feedback learning jobs."""

import pytest

from app.tools import feedback_learning as fl


@pytest.mark.parametrize("value,expected", [
    ("true", True), ("1", True), ("YES", True), (" on ", True),
    ("false", False), ("0", False), ("", False), ("nope", False),
])
def test_feature_enabled_reads_truthy_values(monkeypatch, value, expected) -> None:
    monkeypatch.setenv("SOME_FLAG", value)
    assert fl.feature_enabled("SOME_FLAG") is expected


def test_feature_enabled_defaults_to_off(monkeypatch) -> None:
    monkeypatch.delenv("SOME_FLAG", raising=False)
    assert fl.feature_enabled("SOME_FLAG") is False


def test_normalize_ws_collapses_and_trims() -> None:
    assert fl.normalize_ws("  a \n b\t c  ") == "a b c"
    assert fl.normalize_ws(None) == ""


def test_customer_section_returns_text_after_marker() -> None:
    draft = "[INTERNAL TECHNICAL REPORT]\nroot cause\n\n[CUSTOMER RESPONSE]\nHello there."
    assert fl.customer_section(draft) == "Hello there."


def test_customer_section_returns_whole_draft_without_marker() -> None:
    assert fl.customer_section("  Just a reply  ") == "Just a reply"
    assert fl.customer_section(None) == ""


def test_issue_text_drops_ocr_attachment_text() -> None:
    raw = "Cannot log in\n[OCR EXTRACTED TEXT FROM ATTACHMENT]\nJane Doe 555-0100"
    assert fl.issue_text(raw) == "Cannot log in"


def test_masked_uses_mask_pii_and_handles_empty(monkeypatch) -> None:
    monkeypatch.setattr(fl, "mask_pii", lambda text: (f"M[{text}]", ["x"]))
    assert fl.masked("hello") == "M[hello]"
    assert fl.masked("") == ""
    assert fl.masked(None) == ""


def test_masked_really_removes_a_greeting_name() -> None:
    # Real bug found in this project: "Hi <Name>," slipped past NER (MLflow.md, bug 3).
    assert "Deshan" not in fl.masked("Hi Deshan, please restart the app.")


def test_contains_pii_detects_an_email_but_not_plain_text() -> None:
    assert fl.contains_pii("contact me at jane@example.com") is True
    assert fl.contains_pii("Restart the app and try again.") is False
    assert fl.contains_pii("") is False


def test_deterministic_id_is_stable() -> None:
    assert fl.deterministic_id("edit", "abc") == "edit_abc"


def test_as_list_and_first_row_normalize_postgrest_shapes() -> None:
    assert fl.as_list(None) == []
    assert fl.as_list({"a": 1}) == [{"a": 1}]
    assert fl.as_list([{"a": 1}, {"a": 2}]) == [{"a": 1}, {"a": 2}]
    assert fl.first_row([{"a": 1}, {"a": 2}]) == {"a": 1}
    assert fl.first_row({"a": 1}) == {"a": 1}
    assert fl.first_row(None) == {}
    assert fl.first_row([]) == {}


def test_get_supabase_is_lazy_and_cached(monkeypatch) -> None:
    created = []
    monkeypatch.setattr(fl, "_supabase", None)
    monkeypatch.setattr(fl, "create_client", lambda url, key: created.append((url, key)) or object())
    monkeypatch.setenv("SUPABASE_PROJECT_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_API", "secret")

    first = fl.get_supabase()
    second = fl.get_supabase()

    assert first is second
    assert created == [("https://x.supabase.co", "secret")]
