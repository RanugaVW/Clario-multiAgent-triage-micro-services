"""Regex patterns and replacement helpers for structured PII."""

from __future__ import annotations

import re
from collections import Counter

EMAIL = "[EMAIL]"
PHONE = "[PHONE]"
CREDIT_CARD = "[CREDIT_CARD]"
IP_ADDRESS = "[IP_ADDRESS]"

EMAIL_PATTERN = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?![\w.+-])")
CREDIT_CARD_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){15}\d(?!\d)")
IP_ADDRESS_PATTERN = re.compile(
    r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}(?![\d.])"
)
PHONE_PATTERN = re.compile(
    r"(?<!\w)(?!(?:19|20)\d{2}-\d{2}-\d{2}(?!\d))"
    r"(?:(?:\+|00)\d{1,3}[ .-]?)?(?:\(\d{1,4}\)[ .-]?)?\d{2,4}(?:[ .-]?\d{2,4}){2,3}(?!\w)"
)
PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("email", EMAIL_PATTERN, EMAIL),
    ("credit_card", CREDIT_CARD_PATTERN, CREDIT_CARD),
    ("ip_address", IP_ADDRESS_PATTERN, IP_ADDRESS),
    ("phone", PHONE_PATTERN, PHONE),
)


def mask_regex_pii(text: str) -> tuple[str, Counter[str]]:
    """Replace structured PII and return its occurrence counts by type."""
    counts: Counter[str] = Counter()
    for pii_type, pattern, placeholder in PATTERNS:
        text, replacements = pattern.subn(placeholder, text)
        counts[pii_type] += replacements
    return text, counts
