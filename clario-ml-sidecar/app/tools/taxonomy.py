"""Label taxonomy for the Llama-3.2 v2 triage adapter.

One place for the label sets the adapter was fine-tuned on, so the local
model, its Gemini fallback, routing, and the tests all validate against the
same definitions instead of each carrying its own copy.
"""

from __future__ import annotations

import re
from typing import Any

# Order matters only for display; these are the exact strings the adapter was
# trained to emit (see label_maps.json in the adapter directory).
CATEGORY_LABELS: tuple[str, ...] = (
    "Account Access",
    "Authentication",
    "Billing & Invoicing",
    "Content & Media",
    "Data Integrity",
    "Feature Request",
    "Performance",
    "Refunds",
    "Service Outage",
    "Subscription Management",
    "Technical Support",
    "UI/UX",
)
PRIORITY_LABELS: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
SENTIMENT_LABELS: tuple[str, ...] = ("Neutral", "Negative", "Frustrated")

# A ticket carries at most this many category labels (the training data
# tops out at three). Also keeps the joined string inside the
# ticket_classifications.category VARCHAR(100) column.
MAX_CATEGORIES = 3

# Stored in `category` when no valid label survives; routing treats it as
# "no usable category" and falls back to keyword scoring.
UNKNOWN_CATEGORY = "General"

# Which specialist domain each category label points at. Categories left out
# (Feature Request, Content & Media) don't name a domain on their own.
CATEGORY_DOMAIN: dict[str, str] = {
    "Account Access": "technical",
    "Authentication": "technical",
    "Technical Support": "technical",
    "Performance": "technical",
    "Data Integrity": "technical",
    "Service Outage": "technical",
    "UI/UX": "technical",
    "Billing & Invoicing": "billing",
    "Refunds": "billing",
    "Subscription Management": "billing",
}

_CATEGORY_BY_LOWER = {label.lower(): label for label in CATEGORY_LABELS}
_PRIORITY_BY_LOWER = {label.lower(): label for label in PRIORITY_LABELS}
_SENTIMENT_BY_LOWER = {label.lower(): label for label in SENTIMENT_LABELS}
# Split a joined category string on commas/semicolons only: "UI/UX" contains a
# slash, so slashes must not be treated as separators.
_CATEGORY_SEPARATOR = re.compile(r"\s*[,;]\s*")


def normalize_priority(value: Any) -> str | None:
    return _PRIORITY_BY_LOWER.get(value.strip().lower()) if isinstance(value, str) else None


def normalize_sentiment(value: Any) -> str | None:
    return _SENTIMENT_BY_LOWER.get(value.strip().lower()) if isinstance(value, str) else None


def normalize_categories(value: Any) -> list[str]:
    """Canonical, de-duplicated category labels in the order given, at most
    MAX_CATEGORIES. Labels outside the taxonomy are dropped, not guessed at."""
    if isinstance(value, str):
        items = _CATEGORY_SEPARATOR.split(value.strip())
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        return []

    labels: list[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        canonical = _CATEGORY_BY_LOWER.get(item.strip().lower())
        if canonical and canonical not in labels:
            labels.append(canonical)
    return labels[:MAX_CATEGORIES]


def format_category(categories: list[str]) -> str:
    """The single string stored in state/DB and shown in the UI."""
    return ", ".join(categories) if categories else UNKNOWN_CATEGORY


def split_category(category: str | None) -> list[str]:
    """Inverse of format_category(); tolerant of the unknown label and None."""
    return normalize_categories(category) if category else []


def domains_for(categories: list[str]) -> set[str]:
    return {CATEGORY_DOMAIN[c] for c in categories if c in CATEGORY_DOMAIN}


def normalize_classification(raw: Any) -> dict[str, Any] | None:
    """Validate a model's raw priority/sentiment/category output.

    Returns {"priority", "sentiment", "categories"} with every value in the
    taxonomy, or None if any part is missing or outside it. A wrong label is
    never silently replaced with a default: an under-prioritised or
    mis-categorised ticket is worse than one that visibly failed and was
    handed to the fallback.
    """
    if not isinstance(raw, dict):
        return None
    priority = normalize_priority(raw.get("priority"))
    sentiment = normalize_sentiment(raw.get("sentiment"))
    categories = normalize_categories(raw.get("category"))
    if priority is None or sentiment is None or not categories:
        return None
    return {"priority": priority, "sentiment": sentiment, "categories": categories}
