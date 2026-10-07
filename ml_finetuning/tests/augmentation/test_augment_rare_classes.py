import json
import random

import pandas as pd
import pytest

from src.augmentation import augment_rare_classes as aug
from src.distillation.fewshot import TeacherAnswer

# Real v2 training counts (data/splits/split_report.md, 10,000 rows).
PRIORITY_COUNTS = {"Low": 2490, "Medium": 2500, "High": 4850, "Critical": 160}
CATEGORY_COUNTS = {"Billing & Invoicing": 3590, "Account Access": 1940, "Technical Support": 1720,
                   "Subscription Management": 1560, "Feature Request": 1150, "Authentication": 840,
                   "Performance": 780, "Refunds": 610, "UI/UX": 230, "Data Integrity": 100,
                   "Content & Media": 70, "Service Outage": 70}


class FakePool:
    """Generator returns two tickets; the teacher labels one Critical, one High."""

    def generate_json(self, contents, system_instruction, schema, temperature):
        if schema is aug.GeneratedBatch:
            return json.dumps({"tickets": [
                {"product": "Assessment Module", "issue_description": "Exam starts in 10 minutes and nobody can log in"},
                {"product": "Video Classroom", "issue_description": "The lesson video is a little slow to start today"},
            ]})
        assert schema is TeacherAnswer
        critical = "Exam starts" in contents.split("### Now classify this ticket")[1]
        return json.dumps({"reasoning": "Step 1: x", "priority": "Critical" if critical else "High",
                           "sentiment": "Frustrated", "category": ["Authentication"]})


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(aug, "ACCEPTED_PATH", tmp_path / "accepted.jsonl")
    monkeypatch.setattr(aug, "REJECTED_PATH", tmp_path / "rejected.jsonl")
    return tmp_path


def _train():
    return pd.DataFrame([{"input_product": "Assessment Module", "input_issue_description": f"critical {i}",
                          "reasoning": "r", "priority": "Critical", "sentiment": "Frustrated",
                          "category": ["Authentication"]} for i in range(3)])


def test_only_teacher_confirmed_tickets_are_kept(tmp_cache):
    accepted, rejected = aug.augment_label(FakePool(), "examples", _train(), "priority", "Critical",
                                           needed=1, seen=set(), rng=random.Random(0))
    assert (accepted, rejected) == (1, 1)
    kept = aug.load_jsonl(aug.ACCEPTED_PATH)
    assert kept[0]["labels"]["priority"] == "Critical"
    assert kept[0]["aug_field"] == "priority" and kept[0]["aug_label"] == "Critical"
    assert aug.load_jsonl(aug.REJECTED_PATH)[0]["teacher_labels"]["priority"] == "High"


def test_duplicates_and_pii_are_never_sent_to_the_teacher():
    seen = {aug.normalized("Already in the TEST set, word for word")}
    assert not aug.candidate_ok("already in the test set,  word for word", seen)
    assert not aug.candidate_ok("Please email me at jane.doe@example.com about my refund", set())
    assert not aug.candidate_ok("too short", set())
    assert aug.candidate_ok("My certificate download keeps failing after the exam", set())


def test_augmented_rows_are_tagged_with_their_source(tmp_cache):
    aug.augment_label(FakePool(), "examples", _train(), "priority", "Critical", 1, set(), random.Random(0))
    rows = aug.to_train_rows(aug.load_jsonl(aug.ACCEPTED_PATH))
    assert rows["source"].tolist() == ["augmented:priority=Critical"]
    assert json.loads(rows["category"].iloc[0]) == ["Authentication"]


@pytest.mark.parametrize("counts", [PRIORITY_COUNTS, CATEGORY_COUNTS])
def test_targets_contract(counts):
    targets = aug.compute_augmentation_targets(counts, 10_000)
    majority = max(counts, key=counts.get)

    assert set(targets) == set(counts)
    assert all(isinstance(n, int) and n >= 0 for n in targets.values())
    assert targets[majority] == 0
    # augmentation must never turn a rare label into the most common one
    assert all(counts[label] + n <= counts[majority] for label, n in targets.items())
    # and it has to actually help the rarest label
    assert targets[min(counts, key=counts.get)] > 0
