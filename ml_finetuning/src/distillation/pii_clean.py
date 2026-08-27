# One-time training-data PII masking workflow; not the live runtime redaction tool.
"""Mask structured and named-entity PII in a pandas DataFrame text column."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

import pandas as pd

from .pii_patterns import mask_regex_pii

ENTITY_PLACEHOLDERS = {"PERSON": "[PERSON]", "GPE": "[LOCATION]", "ORG": "[ORG]"}
REPORT_KEYS = ("email", "phone", "credit_card", "ip_address", "person", "location", "org")


def load_ner_model():
    """Load the English spaCy model with an actionable error if it is unavailable."""
    try:
        import spacy

        return spacy.load("en_core_web_sm")
    except OSError as error:
        raise RuntimeError(
            "spaCy model 'en_core_web_sm' is required. Run: python -m spacy download en_core_web_sm"
        ) from error


def mask_entities(text: str, entities: Iterable[object]) -> tuple[str, Counter[str]]:
    """Replace selected spaCy entities from right to left to retain character offsets."""
    counts: Counter[str] = Counter()
    replacements = []
    for entity in entities:
        label = getattr(entity, "label_", "")
        if label in ENTITY_PLACEHOLDERS:
            replacements.append((entity.start_char, entity.end_char, label))
    for start, end, label in reversed(replacements):
        text = text[:start] + ENTITY_PLACEHOLDERS[label] + text[end:]
        counts[{"PERSON": "person", "GPE": "location", "ORG": "org"}[label]] += 1
    return text, counts


def mask_pii_dataframe(
    df: pd.DataFrame, text_column: str, nlp=None, batch_size: int = 128
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return a copied DataFrame with PII placeholders and a per-type occurrence report.

    Missing values are preserved. The input DataFrame is never modified in place.
    """
    if text_column not in df.columns:
        raise KeyError(f"Text column '{text_column}' was not found in the DataFrame.")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    cleaned = df.copy()
    report: Counter[str] = Counter({key: 0 for key in REPORT_KEYS})
    values = cleaned[text_column].tolist()
    text_positions = [index for index, value in enumerate(values) if pd.notna(value)]
    regex_masked: dict[int, str] = {}
    for index in text_positions:
        regex_masked[index], counts = mask_regex_pii(str(values[index]))
        report.update(counts)

    model = nlp or load_ner_model()
    documents = model.pipe((regex_masked[index] for index in text_positions), batch_size=batch_size)
    for index, document in zip(text_positions, documents, strict=True):
        regex_masked[index], counts = mask_entities(regex_masked[index], document.ents)
        report.update(counts)
    for index, text in regex_masked.items():
        values[index] = text
    cleaned[text_column] = values
    return cleaned, dict(report)
