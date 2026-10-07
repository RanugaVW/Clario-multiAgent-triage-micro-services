import json

import pandas as pd
import pytest

from src.distillation.fewshot import (
    FIELD_LABELS,
    TeacherAnswer,
    build_teacher_prompt,
    format_examples,
    label_ticket,
    select_bank,
)
from src.distillation.taxonomy import CATEGORY_LABELS, PRIORITY_LABELS, SENTIMENT_LABELS, normalize_labels


def _rows() -> pd.DataFrame:
    rows = []
    for i, category in enumerate(CATEGORY_LABELS):
        rows.append({
            "input_product": "Video Classroom",
            "input_issue_description": f"issue {i}",
            "reasoning": "Step 1: ...",
            "priority": PRIORITY_LABELS[i % 4],
            "sentiment": SENTIMENT_LABELS[i % 3],
            "category": [category],
        })
    return pd.DataFrame(rows * 3)


class FakePool:
    def __init__(self, answers: list[str]) -> None:
        self.answers = answers
        self.prompts: list[str] = []

    def generate_json(self, contents, system_instruction, schema, temperature):
        assert schema is TeacherAnswer
        self.prompts.append(contents)
        return self.answers.pop(0)


def _answer(**overrides) -> str:
    answer = {"reasoning": "Step 1: x", "priority": "High", "sentiment": "Frustrated", "category": ["Refunds"]}
    return json.dumps({**answer, **overrides})


def test_normalize_labels_canonicalises_case_and_dedupes():
    raw = {"priority": "high", "sentiment": "NEUTRAL", "category": ["refunds", "Refunds", "UI/UX"]}
    assert normalize_labels(raw) == {"priority": "High", "sentiment": "Neutral", "category": ["Refunds", "UI/UX"]}


@pytest.mark.parametrize("raw", [
    {"priority": "Urgent", "sentiment": "Neutral", "category": ["Refunds"]},
    {"priority": "High", "sentiment": "Positive", "category": ["Refunds"]},
    {"priority": "High", "sentiment": "Neutral", "category": ["Refunds", "Billing"]},
    {"priority": "High", "sentiment": "Neutral", "category": []},
    {"priority": "High", "sentiment": "Neutral", "category": list(CATEGORY_LABELS[:4])},
])
def test_normalize_labels_rejects_anything_outside_the_taxonomy(raw):
    assert normalize_labels(raw) is None


def test_bank_covers_every_label_of_every_field():
    bank = select_bank(_rows())
    for field, labels in FIELD_LABELS.items():
        present = {label for example in bank
                   for label in (example[field] if field == "category" else [example[field]])}
        assert present == set(labels)
    assert len(bank) <= len(CATEGORY_LABELS)


def test_bank_fails_loudly_when_a_label_has_no_example():
    rows = _rows()
    rows = rows[rows["priority"] != "Critical"]
    with pytest.raises(ValueError, match="Critical"):
        select_bank(rows)


def test_prompt_contains_the_examples_and_the_ticket():
    text = format_examples(select_bank(_rows()))
    prompt = build_teacher_prompt(text, "Payment & Billing", "charged twice")
    assert "### Example 1" in prompt and prompt.endswith("Issue: charged twice\nAnswer:")


def test_label_ticket_returns_a_distilled_record():
    record = label_ticket(FakePool([_answer()]), "examples", "Payment & Billing", "refund me")
    assert record == {
        "input_product": "Payment & Billing",
        "input_issue_description": "refund me",
        "reasoning": "Step 1: x",
        "labels": {"priority": "High", "sentiment": "Frustrated", "category": ["Refunds"]},
    }


def test_label_ticket_retries_once_then_gives_up():
    pool = FakePool([_answer(priority="Urgent"), "not json"])
    assert label_ticket(pool, "examples", "Payment & Billing", "refund me") is None
    assert len(pool.prompts) == 2
