"""Shared types and filters for real-response source fetchers."""

from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?:\+?\d[\d .()-]{7,}\d)")
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class RawExample:
    """One issue+resolution pair fetched from a real-response source."""

    issue_text: str
    resolution_text: str
    source_url: str
    original_id: str
    responder_role: str


def has_pii(*texts: str) -> bool:
    """True if any text looks like it contains an email address or phone number."""
    return any(EMAIL_PATTERN.search(text) or PHONE_PATTERN.search(text) for text in texts)


def strip_html(html: str) -> str:
    """Strip HTML tags and collapse whitespace, for Discourse's `cooked` field."""
    text = _HTML_TAG_PATTERN.sub(" ", html)
    return _WHITESPACE_PATTERN.sub(" ", text).strip()
