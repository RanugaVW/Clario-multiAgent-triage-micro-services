"""Few-shot Gemini teacher: labels a ticket with reasoning, shown solved examples first.

The example bank is chosen so every priority, sentiment and category label
appears at least once; without that, the teacher has never been shown what a
rare label (Critical, Service Outage, ...) looks like.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

from src.distillation.taxonomy import (
    CATEGORY_DEFINITIONS,
    CATEGORY_LABELS,
    MAX_CATEGORIES,
    PRIORITY_DEFINITIONS,
    PRIORITY_LABELS,
    SENTIMENT_DEFINITIONS,
    SENTIMENT_LABELS,
    labels_of,
    normalize_labels,
)

FIELDS = ("priority", "sentiment", "category")
FIELD_LABELS = {"priority": PRIORITY_LABELS, "sentiment": SENTIMENT_LABELS, "category": CATEGORY_LABELS}
TEACHER_TEMPERATURE = 0.2


class TeacherAnswer(BaseModel):
    reasoning: str
    priority: Literal[PRIORITY_LABELS]
    sentiment: Literal[SENTIMENT_LABELS]
    category: list[Literal[CATEGORY_LABELS]] = Field(min_length=1, max_length=MAX_CATEGORIES)


def _definitions(title: str, definitions: dict[str, str]) -> str:
    return f"{title}:\n" + "\n".join(f"- {label}: {meaning}" for label, meaning in definitions.items())


TEACHER_SYSTEM_PROMPT = (
    "You are an expert IT Support Triage Analyst for an online STEM learning platform (LMS). "
    "Classify the customer support ticket from its 'Product' and 'Issue'.\n\n"
    "First write step-by-step reasoning in exactly this shape: "
    "'Step 1: Analyze intent: ... Step 2: Evaluate urgency: ... Step 3: Determine sentiment: ... "
    "Step 4: Assess complexity: ...'. Then give the labels.\n\n"
    f"{_definitions('Priority (pick one)', PRIORITY_DEFINITIONS)}\n\n"
    f"{_definitions('Sentiment (pick one)', SENTIMENT_DEFINITIONS)}\n\n"
    f"{_definitions(f'Category (pick 1 to {MAX_CATEGORIES}, most relevant first)', CATEGORY_DEFINITIONS)}\n\n"
    "Use only these exact label strings. Follow the solved examples for style and calibration."
)


def select_bank(df: pd.DataFrame, min_per_label: int = 1, seed: int = 42) -> list[dict[str, Any]]:
    """Greedy cover: the fewest rows such that every label of every field appears
    at least `min_per_label` times. `df` needs input_product, input_issue_description,
    reasoning, priority, sentiment and category (a list)."""
    rng = random.Random(seed)
    records = df.to_dict("records")
    rng.shuffle(records)
    need = {(field, label): min_per_label for field in FIELDS for label in FIELD_LABELS[field]}
    bank: list[dict[str, Any]] = []
    used: set[int] = set()

    def gain(record: dict[str, Any]) -> int:
        return sum(need.get((field, label), 0) > 0 for field in FIELDS for label in labels_of(record, field))

    while any(n > 0 for n in need.values()):
        best = max((i for i in range(len(records)) if i not in used),
                   key=lambda i: gain(records[i]), default=None)
        if best is None or gain(records[best]) == 0:
            missing = sorted(key for key, n in need.items() if n > 0)
            raise ValueError(f"No examples available for: {missing}")
        used.add(best)
        record = records[best]
        bank.append({key: record[key] for key in
                     ("input_product", "input_issue_description", "reasoning", *FIELDS)})
        for field in FIELDS:
            for label in labels_of(record, field):
                if need.get((field, label), 0) > 0:
                    need[(field, label)] -= 1
    return bank


def save_bank(bank: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bank, indent=2, ensure_ascii=False), encoding="utf-8")


def load_bank(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_examples(bank: list[dict[str, Any]]) -> str:
    blocks = []
    for n, example in enumerate(bank, start=1):
        answer = {
            "reasoning": example["reasoning"],
            "priority": example["priority"],
            "sentiment": example["sentiment"],
            "category": list(example["category"]),
        }
        blocks.append(
            f"### Example {n}\nProduct: {example['input_product']}\n"
            f"Issue: {example['input_issue_description']}\n"
            f"Answer: {json.dumps(answer, ensure_ascii=False)}"
        )
    return "\n\n".join(blocks)


def build_teacher_prompt(examples_text: str, product: str, issue: str) -> str:
    return (
        f"Solved examples:\n\n{examples_text}\n\n"
        f"### Now classify this ticket\nProduct: {product}\nIssue: {issue}\nAnswer:"
    )


def label_ticket(pool: Any, examples_text: str, product: str, issue: str,
                 attempts: int = 2) -> dict[str, Any] | None:
    """One distilled record, or None if the teacher never produced valid labels."""
    prompt = build_teacher_prompt(examples_text, product, issue)
    for _ in range(attempts):
        raw = pool.generate_json(prompt, TEACHER_SYSTEM_PROMPT, TeacherAnswer, TEACHER_TEMPERATURE)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        labels = normalize_labels(parsed)
        reasoning = parsed.get("reasoning", "").strip() if isinstance(parsed, dict) else ""
        if labels and reasoning:
            return {
                "input_product": product,
                "input_issue_description": issue,
                "reasoning": reasoning,
                "labels": labels,
            }
    return None
