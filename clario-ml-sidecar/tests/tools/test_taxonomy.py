"""Label taxonomy shared by the classifier, its Gemini fallback, and routing."""

import json
from pathlib import Path

import pytest

from app.tools.taxonomy import (
    CATEGORY_LABELS,
    MAX_CATEGORIES,
    PRIORITY_LABELS,
    SENTIMENT_LABELS,
    UNKNOWN_CATEGORY,
    domains_for,
    format_category,
    normalize_categories,
    normalize_classification,
    normalize_priority,
    normalize_sentiment,
    split_category,
)


def test_label_sets_match_the_adapters_training_taxonomy() -> None:
    assert PRIORITY_LABELS == ("Low", "Medium", "High", "Critical")
    assert SENTIMENT_LABELS == ("Neutral", "Negative", "Frustrated")
    assert len(CATEGORY_LABELS) == 12
    assert "Billing & Invoicing" in CATEGORY_LABELS


def _find_adapter_label_maps() -> Path | None:
    # Walk up rather than assuming a depth: this file is mirrored into
    # clario-ml-sidecar/, where the repo root is one level closer.
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "Fine Tuned Llama-3.2 v2 (3B)" / "label_maps.json"
        if candidate.exists():
            return candidate
    return None


def test_label_sets_match_the_adapter_label_maps_when_the_adapter_is_present() -> None:
    adapter = _find_adapter_label_maps()
    if adapter is None:
        pytest.skip("local-only adapter weights are not checked out on this machine")
    maps = json.loads(adapter.read_text())
    assert tuple(maps["categories"]) == CATEGORY_LABELS
    assert tuple(maps["priorities"]) == PRIORITY_LABELS
    assert tuple(maps["sentiments"]) == SENTIMENT_LABELS


@pytest.mark.parametrize(("raw", "expected"), [
    ("High", "High"), ("high", "High"), (" CRITICAL ", "Critical"), ("Medium", "Medium"),
    ("Urgent", None), ("", None), (None, None), (3, None),
])
def test_normalize_priority(raw, expected) -> None:
    assert normalize_priority(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ("Frustrated", "Frustrated"), ("frustrated", "Frustrated"), ("Negative", "Negative"),
    # Labels from the previous adapter's scale are NOT part of this taxonomy.
    ("Positive", None), ("Strongly Negative", None), (None, None),
])
def test_normalize_sentiment(raw, expected) -> None:
    assert normalize_sentiment(raw) == expected


def test_normalize_categories_accepts_a_list_and_keeps_model_order() -> None:
    assert normalize_categories(["Refunds", "Billing & Invoicing"]) == ["Refunds", "Billing & Invoicing"]


def test_normalize_categories_is_case_insensitive_and_dedupes() -> None:
    assert normalize_categories(["billing & invoicing", "Billing & Invoicing", "ui/ux"]) == [
        "Billing & Invoicing", "UI/UX",
    ]


def test_normalize_categories_drops_labels_outside_the_taxonomy() -> None:
    assert normalize_categories(["Security", "Refunds", "Documentation"]) == ["Refunds"]


def test_normalize_categories_accepts_a_comma_joined_string() -> None:
    assert normalize_categories("Account Access, Billing & Invoicing") == ["Account Access", "Billing & Invoicing"]


def test_normalize_categories_does_not_split_labels_that_contain_a_slash() -> None:
    assert normalize_categories("UI/UX") == ["UI/UX"]


def test_normalize_categories_caps_the_number_of_labels() -> None:
    every_label = list(CATEGORY_LABELS)
    assert len(normalize_categories(every_label)) == MAX_CATEGORIES


@pytest.mark.parametrize("raw", [None, [], "", "Security", 5, {"a": 1}])
def test_normalize_categories_returns_empty_when_nothing_valid(raw) -> None:
    assert normalize_categories(raw) == []


def test_format_category_joins_with_comma_space() -> None:
    assert format_category(["Account Access", "Billing & Invoicing"]) == "Account Access, Billing & Invoicing"


def test_format_category_uses_the_unknown_label_when_empty() -> None:
    assert format_category([]) == UNKNOWN_CATEGORY


def test_the_longest_possible_category_string_fits_the_database_column() -> None:
    # ticket_classifications.category is VARCHAR(100).
    longest = sorted(CATEGORY_LABELS, key=len, reverse=True)[:MAX_CATEGORIES]
    assert len(format_category(longest)) <= 100


def test_split_category_round_trips_format_category() -> None:
    labels = ["Billing & Invoicing", "Technical Support"]
    assert split_category(format_category(labels)) == labels


def test_split_category_returns_empty_for_the_unknown_label_and_none() -> None:
    assert split_category(UNKNOWN_CATEGORY) == []
    assert split_category(None) == []


def test_domains_for_maps_categories_to_specialist_domains() -> None:
    assert domains_for(["Billing & Invoicing"]) == {"billing"}
    assert domains_for(["Authentication"]) == {"technical"}
    assert domains_for(["Refunds", "Technical Support"]) == {"billing", "technical"}


def test_domains_for_ignores_categories_with_no_clear_domain() -> None:
    assert domains_for(["Feature Request"]) == set()
    assert domains_for([]) == set()


def test_normalize_classification_returns_a_clean_result() -> None:
    result = normalize_classification({
        "priority": "high", "sentiment": "Frustrated", "category": ["Refunds", "Billing & Invoicing", "Security"],
    })
    assert result == {
        "priority": "High", "sentiment": "Frustrated", "categories": ["Refunds", "Billing & Invoicing"],
    }


@pytest.mark.parametrize("raw", [
    {"priority": "Urgent", "sentiment": "Neutral", "category": ["Refunds"]},      # priority outside taxonomy
    {"priority": "High", "sentiment": "Positive", "category": ["Refunds"]},       # sentiment outside taxonomy
    {"priority": "High", "sentiment": "Neutral", "category": ["Security"]},       # no valid category left
    {"priority": "High", "sentiment": "Neutral"},                                  # category missing
    {},
    None,
])
def test_normalize_classification_rejects_invalid_output_instead_of_guessing(raw) -> None:
    assert normalize_classification(raw) is None
