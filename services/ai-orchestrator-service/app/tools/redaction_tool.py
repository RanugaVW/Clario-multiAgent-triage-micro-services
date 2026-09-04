"""PII masking for inbound and outbound ticket text."""

from __future__ import annotations

import re
from functools import lru_cache

import spacy
from faker import Faker

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)")
CARD_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
# Support-ticket self-introductions ("Hi I'm Deshan", "My name is Deshan
# Athukorarala") are the single most common place a real name appears in
# this domain, and spaCy's en_core_web_md was confirmed live to sometimes
# miss real names here entirely (e.g. "Deshan" tagged as nothing at all) -
# found because that exact miss let a customer's real name leak verbatim
# into a cached RAG precedent later served to other customers. This is a
# second, independent detector for the same "person" kind, layered on top
# of NER rather than replacing it: a deterministic pattern match on the
# specific phrasing support tickets actually use, so a name NER's training
# data underrepresents is still caught.
SELF_INTRO_PATTERN = re.compile(
    r"\b(?:I'?m|I\s+am|[Mm]y\s+name\s+is|[Tt]his\s+is)\s+"
    r"([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){0,2})"
)
REGEX_PATTERNS = (("email", EMAIL_PATTERN), ("credit_card", CARD_PATTERN), ("phone", PHONE_PATTERN))
NER_LABELS = {"PERSON", "GPE", "ORG"}

# Types that get a realistic, reversible stand-in (see mask_pii_reversible)
# instead of a bracket token. Limited to what a response might legitimately
# need to address the customer by - there's no legitimate reason for a
# response to ever echo back a phone number or card number.
REVERSIBLE_TYPES = {"person", "email"}


@lru_cache(maxsize=1)
def _nlp() -> spacy.language.Language:
    """Load the required spaCy English NER model once per process.

    Uses the medium model, not the small one: en_core_web_sm misclassifies
    plenty of real names as ORG rather than PERSON (e.g. "Kalana Wijesuriya"),
    which would silently skip both redaction quality and the reversible
    stand-in mask_pii_reversible needs for personalization. `en_core_web_md`
    gets these right. Install with:
        python -m spacy download en_core_web_md
    """
    return spacy.load("en_core_web_md")


def _non_overlapping(spans: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Prefer earlier, longer spans so replacements cannot corrupt offsets."""
    selected: list[tuple[int, int, str]] = []
    for start, end, kind in sorted(spans, key=lambda item: (item[0], -(item[1] - item[0]))):
        if all(end <= old_start or start >= old_end for old_start, old_end, _ in selected):
            selected.append((start, end, kind))
    return sorted(selected)


def _detect_spans(text: str) -> list[tuple[int, int, str]]:
    """Find every PII span (regex + spaCy NER + self-intro name pattern),
    longest-and-earliest-wins on overlap."""
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
    spans.extend(
        (match.start(1), match.end(1), "person")
        for match in SELF_INTRO_PATTERN.finditer(text)
    )
    return _non_overlapping(spans)


def mask_pii(text: str) -> tuple[str, list[dict]]:
    """Mask PII and return only PII type and original offsets, never its value."""
    selected = _detect_spans(text)
    masked_parts: list[str] = []
    cursor = 0
    for start, end, kind in selected:
        masked_parts.extend((text[cursor:start], f"[REDACTED_{kind.upper()}]"))
        cursor = end
    masked_parts.append(text[cursor:])
    pii_found = [{"type": kind, "start_char": start, "end_char": end} for start, end, kind in selected]
    return "".join(masked_parts), pii_found


def mask_pii_reversible(text: str) -> tuple[str, dict[str, str], list[dict]]:
    """Like mask_pii, but PERSON/EMAIL get a realistic Faker stand-in instead
    of a bracket token, so a downstream LLM can address the customer
    naturally without ever seeing their real name or email. Everything else
    (GPE/ORG/PHONE/CREDIT_CARD) is redacted exactly as mask_pii does.

    The same real value always maps to the same stand-in within one call, so
    repeated mentions of a name stay coherent in the generated text.

    Returns (text_with_stand_ins, shadow_map, pii_found). shadow_map is
    {fake_value: real_value}, for resolve_node to restore the real values
    into the final draft once validation/judging - which must never see real
    PII - have already run on the stand-in version.
    """
    selected = _detect_spans(text)
    faker = Faker()
    fake_by_real: dict[str, str] = {}
    shadow_map: dict[str, str] = {}
    masked_parts: list[str] = []
    cursor = 0
    for start, end, kind in selected:
        if kind in REVERSIBLE_TYPES:
            real_value = text[start:end]
            if real_value not in fake_by_real:
                fake_value = faker.name() if kind == "person" else faker.email()
                fake_by_real[real_value] = fake_value
                shadow_map[fake_value] = real_value
            replacement = fake_by_real[real_value]
        else:
            replacement = f"[REDACTED_{kind.upper()}]"
        masked_parts.extend((text[cursor:start], replacement))
        cursor = end
    masked_parts.append(text[cursor:])
    pii_found = [{"type": kind, "start_char": start, "end_char": end} for start, end, kind in selected]
    return "".join(masked_parts), shadow_map, pii_found
