import json

import pandas as pd

from src.distillation.taxonomy import PRIORITY_LABELS, SENTIMENT_LABELS
from src.training import dataset


def _write_records(path, n=200):
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            f.write(json.dumps({
                "input_product": "Video Classroom",
                "input_issue_description": f"Ticket number {i} about video",
                "reasoning": "Step 1: x",
                "labels": {"priority": PRIORITY_LABELS[i % 4], "sentiment": SENTIMENT_LABELS[i % 3],
                           "category": ["Content & Media"]},
            }) + "\n")
        # duplicate (different case/spacing) and an invalid label: both dropped
        f.write(json.dumps({"input_product": "x", "input_issue_description": "TICKET number 0  about video",
                            "reasoning": "r", "labels": {"priority": "Low", "sentiment": "Neutral",
                                                        "category": ["Refunds"]}}) + "\n")
        f.write(json.dumps({"input_product": "x", "input_issue_description": "bad one",
                            "reasoning": "r", "labels": {"priority": "Urgent", "sentiment": "Neutral",
                                                        "category": ["Refunds"]}}) + "\n")


def test_load_records_validates_and_dedupes(tmp_path):
    path = tmp_path / "raw.jsonl"
    _write_records(path)
    df = dataset.load_records(path)
    assert len(df) == 200
    assert df["category"].iloc[0] == ["Content & Media"]


def test_split_is_disjoint_and_keeps_fewshot_examples_out_of_test(tmp_path):
    path = tmp_path / "raw.jsonl"
    _write_records(path)
    df = dataset.load_records(path)
    forced = {dataset.normalized(f"Ticket number {i} about video") for i in range(5)}

    train, test = dataset.split_dataset(df, forced)

    train_keys = set(train["input_issue_description"].map(dataset.normalized))
    test_keys = set(test["input_issue_description"].map(dataset.normalized))
    assert not train_keys & test_keys
    assert forced <= train_keys
    assert len(train) + len(test) == len(df)


def test_write_split_marks_rows_original_and_keeps_reasoning_out_of_test(tmp_path):
    path = tmp_path / "raw.jsonl"
    _write_records(path)
    train, test = dataset.split_dataset(dataset.load_records(path), set())
    dataset.write_split(train, test, tmp_path / "out")

    train_csv = pd.read_csv(tmp_path / "out" / "train_with_cot.csv")
    test_csv = pd.read_csv(tmp_path / "out" / "test.csv")
    assert set(train_csv["source"]) == {"original"}
    assert "reasoning" not in test_csv.columns
    assert json.loads(test_csv["category"].iloc[0]) == ["Content & Media"]
