"""Turn the few-shot distilled records into a stratified train/test split (v3).

    python -m src.training.dataset          # from ml_finetuning/

The teacher already answers in the final taxonomy, so labels are only
re-validated here (no keyword mapping, no sentiment rewriting). Tickets used as
few-shot examples are forced into train: the teacher saw their answers, so
grading the student on them would leak.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from src.distillation.fewshot import FIELD_LABELS, FIELDS, load_bank
from src.distillation.taxonomy import CATEGORY_LABELS, PRIORITY_LABELS, SENTIMENT_LABELS, normalize_labels

ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = ROOT / "data" / "distilled" / "fewshot_distilled.jsonl"
BANK_PATH = ROOT / "data" / "fewshot" / "teacher_bank.json"
OUTPUT_DIR = ROOT / "data" / "splits_v3"

TEST_FRACTION = 0.24  # same ratio as v2 (3,184 of 13,184)
RANDOM_STATE = 42
RARE_COMBO_THRESHOLD = 10


def normalized(text: str) -> str:
    return " ".join(str(text).casefold().split())


def load_records(path: Path = RAW_PATH) -> pd.DataFrame:
    rows, seen = [], set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            labels = normalize_labels(record.get("labels"))
            key = normalized(record["input_issue_description"])
            if labels is None or key in seen:
                continue
            seen.add(key)
            rows.append({
                "input_product": record["input_product"],
                "input_issue_description": record["input_issue_description"],
                "reasoning": record["reasoning"],
                **labels,
            })
    return pd.DataFrame(rows)


def build_stratify_key(df: pd.DataFrame, rare_threshold: int = RARE_COMBO_THRESHOLD) -> pd.Series:
    """(category combo, priority, sentiment), coarsened wherever a cell is too
    rare for train_test_split, which needs >= 2 members per class."""
    combo = df["category"].apply("+".join)
    combo = combo.where(combo.map(combo.value_counts()) >= rare_threshold, "RARE_COMBO")
    key = combo + "|" + df["priority"] + "|" + df["sentiment"]
    fallback = df["priority"] + "|" + df["sentiment"]
    key = key.where(key.map(key.value_counts()) >= 2, fallback)
    return key.where(key.map(key.value_counts()) >= 2, df["priority"])


def split_dataset(df: pd.DataFrame, forced_train: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    is_forced = df["input_issue_description"].map(normalized).isin(forced_train)
    pool = df[~is_forced]
    train, test = train_test_split(pool, test_size=TEST_FRACTION, random_state=RANDOM_STATE,
                                   stratify=build_stratify_key(pool))
    train = pd.concat([train, df[is_forced]]).sample(frac=1, random_state=RANDOM_STATE)
    return train.reset_index(drop=True), test.reset_index(drop=True)


def label_counts(df: pd.DataFrame, field: str) -> dict[str, int]:
    values = df[field].explode() if field == "category" else df[field]
    counts = values.value_counts()
    return {label: int(counts.get(label, 0)) for label in FIELD_LABELS[field]}


def distribution_report(full: pd.DataFrame, train: pd.DataFrame, test: pd.DataFrame) -> str:
    lines = ["# Split verification (v3, few-shot teacher): full vs train vs test\n",
             f"Rows: full {len(full)}, train {len(train)}, test {len(test)}\n"]
    for field in FIELDS:
        lines += [f"\n## {field.capitalize()}{' (multi-label presence)' if field == 'category' else ''}\n",
                  "| Label | Full n | Full % | Train % | Test % |", "|---|---|---|---|---|"]
        counts = {name: label_counts(part, field) for name, part in (("full", full), ("train", train), ("test", test))}
        for label in FIELD_LABELS[field]:
            pct = {name: 100 * counts[name][label] / max(len(part), 1)
                   for name, part in (("full", full), ("train", train), ("test", test))}
            lines.append(f"| {label} | {counts['full'][label]} | {pct['full']:.1f} | "
                         f"{pct['train']:.1f} | {pct['test']:.1f} |")
    return "\n".join(lines) + "\n"


def write_split(train: pd.DataFrame, test: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    train_out = train[["input_product", "input_issue_description", "reasoning", "priority", "sentiment"]].copy()
    train_out["category"] = train["category"].apply(json.dumps)
    train_out["source"] = "original"
    train_out.to_csv(output_dir / "train_with_cot.csv", index=False)

    test_out = test[["input_product", "input_issue_description", "priority", "sentiment"]].copy()
    test_out["category"] = test["category"].apply(json.dumps)
    test_out.to_csv(output_dir / "test.csv", index=False)

    (output_dir / "label_maps.json").write_text(json.dumps({
        "categories": list(CATEGORY_LABELS),
        "priorities": list(PRIORITY_LABELS),
        "sentiments": list(SENTIMENT_LABELS),
    }, indent=2), encoding="utf-8")


def main() -> None:
    df = load_records()
    forced = {normalized(example["input_issue_description"]) for example in load_bank(BANK_PATH)}
    train, test = split_dataset(df, forced)
    write_split(train, test, OUTPUT_DIR)
    report = distribution_report(df, train, test)
    (OUTPUT_DIR / "split_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
