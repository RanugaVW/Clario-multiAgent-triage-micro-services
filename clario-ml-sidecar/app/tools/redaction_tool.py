"""PII masking for inbound and outbound ticket text."""

from __future__ import annotations

import re
from functools import lru_cache

import spacy

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)")
CARD_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
REGEX_PATTERNS = (("email", EMAIL_PATTERN), ("credit_card", CARD_PATTERN), ("phone", PHONE_PATTERN))
NER_LABELS = {"PERSON", "GPE", "ORG"}


@lru_cache(maxsize=1)
def _nlp() -> spacy.language.Language:
    """Load the required spaCy English NER model once per process."""
    return spacy.load("en_core_web_sm")


def _non_overlapping(spans: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Prefer earlier, longer spans so replacements cannot corrupt offsets."""
    selected: list[tuple[int, int, str]] = []
    for start, end, kind in sorted(spans, key=lambda item: (item[0], -(item[1] - item[0]))):
        if all(end <= old_start or start >= old_end for old_start, old_end, _ in selected):
            selected.append((start, end, kind))
    return sorted(selected)


def mask_pii(text: str) -> tuple[str, list[dict]]:
    """Mask PII and return only PII type and original offsets, never its value."""
    spans = [
        (match.start(), match.end(), kind)
        for kind, pattern in REGEX_PATTERNS
        for match in pattern.finditer(text)
    ]
    spans.extend(
        (entity.start_char, entity.end_char, entity.label_.lower())
        for entity in _nlp()(text).ents
        if entity.label_ in NER_LABELS
    )
    selected = _non_overlapping(spans)
    masked_parts: list[str] = []
    cursor = 0
    for start, end, kind in selected:
        masked_parts.extend((text[cursor:start], f"[REDACTED_{kind.upper()}]"))
        cursor = end
    masked_parts.append(text[cursor:])
    pii_found = [{"type": kind, "start_char": start, "end_char": end} for start, end, kind in selected]
    return "".join(masked_parts), pii_found
