"""Label taxonomy the teacher emits and the student is trained on.

Must stay identical to clario-ml-sidecar/app/tools/taxonomy.py: the sidecar
refuses an adapter whose label_maps.json differs from its own lists.
"""

from __future__ import annotations

from typing import Any

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
MAX_CATEGORIES = 3

PRODUCTS: tuple[str, ...] = (
    "Course Marketplace", "Student Web Portal", "Student Mobile App", "Learning Dashboard",
    "Video Classroom", "Assessment Module", "Course Certificate Service", "Payment & Billing",
    "Learning Plan Subscription", "Course Content Library",
)

PRIORITY_DEFINITIONS = {
    "Low": "minor or non-blocking; a question, suggestion or cosmetic problem",
    "Medium": "an ordinary problem that slows the customer down but has a workaround",
    "High": "blocks access, payment, enrolment or an important workflow for this customer",
    "Critical": "explicitly time-critical and serious: an outage for many users, data loss, a "
                "security breach, or an imminent deadline (e.g. an exam starting now) that is blocked",
}
SENTIMENT_DEFINITIONS = {
    "Neutral": "calm and factual, including polite or positive tickets",
    "Negative": "unhappy or disappointed, but not frustrated",
    "Frustrated": "clearly frustrated, angry or exasperated (repeated failures, raised tone, threats to leave)",
}
CATEGORY_DEFINITIONS = {
    "Account Access": "account lockout, suspension, profile, permissions or entitlement to a course",
    "Authentication": "login, password, two-factor codes, SSO or session problems",
    "Billing & Invoicing": "charges, payments, invoices, checkout and transactions",
    "Content & Media": "course content quality or access, video playback, missing lesson material",
    "Data Integrity": "wrong, missing, lost or unsynced data (grades, progress, records)",
    "Feature Request": "asking for new functionality, or how to configure/use something",
    "Performance": "slowness, latency, timeouts, instability or connectivity",
    "Refunds": "asking for money back",
    "Service Outage": "the platform or a service is down or unavailable",
    "Subscription Management": "enrolment, plan changes, renewals and cancellations",
    "Technical Support": "bugs, crashes, errors, integrations, notifications or emails not delivered",
    "UI/UX": "usability, navigation, layout, accessibility or confusing interface",
}


def _canonical(value: Any, labels: tuple[str, ...]) -> str | None:
    if not isinstance(value, str):
        return None
    by_lower = {label.lower(): label for label in labels}
    return by_lower.get(value.strip().lower())


def normalize_labels(raw: Any) -> dict[str, Any] | None:
    """Canonical {"priority", "sentiment", "category"} or None if anything is
    missing or outside the taxonomy. Invalid labels are rejected, never guessed."""
    if not isinstance(raw, dict):
        return None
    priority = _canonical(raw.get("priority"), PRIORITY_LABELS)
    sentiment = _canonical(raw.get("sentiment"), SENTIMENT_LABELS)
    raw_categories = raw.get("category")
    if isinstance(raw_categories, str):
        raw_categories = [raw_categories]
    if not isinstance(raw_categories, list):
        return None

    categories: list[str] = []
    for item in raw_categories:
        canonical = _canonical(item, CATEGORY_LABELS)
        if canonical is None:
            return None
        if canonical not in categories:
            categories.append(canonical)

    if priority is None or sentiment is None or not 1 <= len(categories) <= MAX_CATEGORIES:
        return None
    return {"priority": priority, "sentiment": sentiment, "category": categories}


def labels_of(record: dict[str, Any], field: str) -> list[str]:
    """The labels a record carries for one field, as a list (category is multi-label)."""
    value = record[field]
    return list(value) if isinstance(value, (list, tuple)) else [value]
