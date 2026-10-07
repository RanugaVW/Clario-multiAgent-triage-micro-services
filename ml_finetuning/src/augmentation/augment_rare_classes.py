"""Add Gemini-written tickets for rare labels to the TRAINING split only.

    python -m src.augmentation.augment_rare_classes        # from ml_finetuning/
    (run after src.distill_with_gemini and src.training.dataset)

Two Gemini roles, kept separate on purpose:
  1. generator - shown real training tickets that carry the rare label
     (few-shot), writes new ones in that style;
  2. teacher   - the same few-shot labeller used for distillation, labels each
     new ticket blind. It is kept only if the teacher independently gives it
     the rare label, so the generator's intent never becomes a training label.

The test split is never augmented and its texts are excluded as duplicates,
so reported test metrics stay on the real label distribution.
Safe to stop and rerun: accepted tickets are cached and counted on restart.
"""

from __future__ import annotations

import json
import logging
import math
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel

from src.curation.sources.common import has_pii
from src.distillation.fewshot import FIELD_LABELS, FIELDS, format_examples, label_ticket, load_bank
from src.distillation.gemini_pool import GeminiPool
from src.distillation.taxonomy import (
    CATEGORY_DEFINITIONS,
    PRIORITY_DEFINITIONS,
    PRODUCTS,
    SENTIMENT_DEFINITIONS,
    labels_of,
)
from src.training.dataset import BANK_PATH, OUTPUT_DIR, label_counts, normalized

AUG_DIR = OUTPUT_DIR.parent / "augmentation"
ACCEPTED_PATH = AUG_DIR / "accepted.jsonl"
REJECTED_PATH = AUG_DIR / "rejected.jsonl"

BATCH_SIZE = 20
STYLE_EXAMPLES = 6
MAX_BATCH_MULTIPLIER = 4  # give up on a label after 4x the batches it should need
GENERATOR_TEMPERATURE = 0.9
SEED = 42

DEFINITIONS = {"priority": PRIORITY_DEFINITIONS, "sentiment": SENTIMENT_DEFINITIONS,
               "category": CATEGORY_DEFINITIONS}

logger = logging.getLogger(__name__)


class GeneratedTicket(BaseModel):
    product: Literal[PRODUCTS]
    issue_description: str


class GeneratedBatch(BaseModel):
    tickets: list[GeneratedTicket]


GENERATOR_SYSTEM_PROMPT = (
    "You write realistic English customer-support tickets for Rysera STEM LMS, an online learning "
    "platform where students buy courses, watch lessons, take assessments and manage subscriptions. "
    "Write as real customers do: varied length, formality and detail, the occasional typo. Never "
    "include names, emails, phone numbers, account or card numbers, or URLs."
)


def compute_augmentation_targets(counts: dict[str, int], n_rows: int) -> dict[str, int]:
    """How many synthetic tickets to add for each label of one field.

    counts: training-set count per label (for category, tickets carrying it).
    n_rows: number of original training tickets.
    Returns {label: tickets_to_add} for every label; 0 where nothing is needed.
    """
    # TODO(human)
    raise NotImplementedError


def build_generator_prompt(field: str, label: str, style_rows: list[dict[str, Any]], count: int) -> str:
    examples = "\n".join(f"- Product: {row['input_product']} | Issue: {row['input_issue_description']}"
                         for row in style_rows)
    return (
        f"Real tickets whose {field} is '{label}' ({DEFINITIONS[field][label]}):\n{examples}\n\n"
        f"Write {count} NEW, distinct tickets whose correct {field} is clearly '{label}'. "
        f"Do not copy or lightly reword the examples. Vary the product and everything other than "
        f"the {field}, so the only thing they share is that they are clearly '{label}'."
    )


def candidate_ok(issue: str, seen: set[str]) -> bool:
    return len(issue.strip()) >= 20 and normalized(issue) not in seen and not has_pii(issue)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def augment_label(pool: GeminiPool, examples_text: str, train: pd.DataFrame, field: str, label: str,
                  needed: int, seen: set[str], rng: random.Random) -> tuple[int, int]:
    """Generate, teacher-verify and cache tickets until `needed` are accepted.
    Returns (accepted, rejected) for this session."""
    carriers = train[train.apply(lambda row: label in labels_of(row, field), axis=1)].to_dict("records")
    accepted = rejected = 0
    max_batches = math.ceil(needed / BATCH_SIZE) * MAX_BATCH_MULTIPLIER
    for _ in range(max_batches):
        if accepted >= needed:
            break
        style = rng.sample(carriers, min(STYLE_EXAMPLES, len(carriers)))
        prompt = build_generator_prompt(field, label, style, min(BATCH_SIZE, needed - accepted))
        raw = pool.generate_json(prompt, GENERATOR_SYSTEM_PROMPT, GeneratedBatch, GENERATOR_TEMPERATURE)
        try:
            candidates = GeneratedBatch.model_validate_json(raw).tickets
        except ValueError:
            continue
        fresh = []
        for ticket in candidates:
            if candidate_ok(ticket.issue_description, seen):
                seen.add(normalized(ticket.issue_description))
                fresh.append(ticket)

        with ThreadPoolExecutor(3) as executor:
            records = list(executor.map(
                lambda t: label_ticket(pool, examples_text, t.product, t.issue_description), fresh))
        for ticket, record in zip(fresh, records):
            if record is not None and label in labels_of(record["labels"], field):
                append_jsonl(ACCEPTED_PATH, {**record, "aug_field": field, "aug_label": label})
                accepted += 1
            else:
                append_jsonl(REJECTED_PATH, {"aug_field": field, "aug_label": label,
                                             "input_issue_description": ticket.issue_description,
                                             "teacher_labels": record["labels"] if record else None})
                rejected += 1
    if accepted < needed:
        logger.warning("%s=%s: only %d/%d accepted after %d batches", field, label, accepted, needed, max_batches)
    return accepted, rejected


def to_train_rows(records: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([{
        "input_product": r["input_product"],
        "input_issue_description": r["input_issue_description"],
        "reasoning": r["reasoning"],
        "priority": r["labels"]["priority"],
        "sentiment": r["labels"]["sentiment"],
        "category": json.dumps(r["labels"]["category"]),
        "source": f"augmented:{r['aug_field']}={r['aug_label']}",
    } for r in records])


def augmentation_report(before: pd.DataFrame, after: pd.DataFrame, targets: dict[str, dict[str, int]]) -> str:
    rejected = Counter((r["aug_field"], r["aug_label"]) for r in load_jsonl(REJECTED_PATH))
    accepted = Counter((r["aug_field"], r["aug_label"]) for r in load_jsonl(ACCEPTED_PATH))
    lines = ["# Augmentation report (training split only)\n",
             f"Training rows: {len(before)} original + {len(after) - len(before)} augmented = {len(after)}\n",
             "Acceptance = share of generated tickets the blind teacher also gave the target label.\n"]
    for field in FIELDS:
        b, a = label_counts(before, field), label_counts(after, field)
        lines += [f"\n## {field.capitalize()}\n",
                  "| Label | Before | Target added | After | Before % | After % | Acceptance |",
                  "|---|---|---|---|---|---|---|"]
        for label in FIELD_LABELS[field]:
            tried = accepted[(field, label)] + rejected[(field, label)]
            rate = f"{100 * accepted[(field, label)] / tried:.0f}%" if tried else "-"
            lines.append(f"| {label} | {b[label]} | {targets[field][label]} | {a[label]} | "
                         f"{100 * b[label] / len(before):.1f} | {100 * a[label] / len(after):.1f} | {rate} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    train = pd.read_csv(OUTPUT_DIR / "train_with_cot.csv")
    test = pd.read_csv(OUTPUT_DIR / "test.csv")
    train["category"] = train["category"].apply(json.loads)

    # Targets come from the original split alone, so a rerun asks for the same numbers.
    targets = {field: compute_augmentation_targets(label_counts(train, field), len(train)) for field in FIELDS}
    cached = load_jsonl(ACCEPTED_PATH)
    done = Counter((r["aug_field"], r["aug_label"]) for r in cached)
    seen = {normalized(t) for t in pd.concat([train["input_issue_description"], test["input_issue_description"]])}
    seen |= {normalized(r["input_issue_description"]) for r in cached + load_jsonl(REJECTED_PATH)}

    pool = GeminiPool()
    examples_text = format_examples(load_bank(BANK_PATH))
    rng = random.Random(SEED)
    for field in FIELDS:
        for label, wanted in targets[field].items():
            needed = wanted - done[(field, label)]
            if needed > 0:
                logger.info("%s=%s: generating %d", field, label, needed)
                augment_label(pool, examples_text, train, field, label, needed, seen, rng)

    original = pd.read_csv(OUTPUT_DIR / "train_with_cot.csv")
    augmented = pd.concat([original, to_train_rows(load_jsonl(ACCEPTED_PATH))], ignore_index=True)
    augmented = augmented.sample(frac=1, random_state=SEED).reset_index(drop=True)
    augmented.to_csv(OUTPUT_DIR / "train_augmented_with_cot.csv", index=False)

    before = original.assign(category=original["category"].apply(json.loads))
    after = augmented.assign(category=augmented["category"].apply(json.loads))
    report = augmentation_report(before, after, targets)
    (OUTPUT_DIR / "augmentation_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
