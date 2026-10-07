"""Customer-rating feedback job: high ratings become exemplars, low ones never do."""

import json

import pytest
from _job_fakes import FakeSupabase

from app.jobs import sync_customer_feedback as job


def _row(score, *, comment=None, judge=None, resolutions=None, ticket_id="t1"):
    return {
        "id": f"fb-{ticket_id}",
        "ticket_id": ticket_id,
        "score": score,
        "comment": comment,
        "tickets": {
            "id": ticket_id,
            "raw_text": "I cannot log in. [OCR EXTRACTED TEXT FROM ATTACHMENT] Jane 555",
            "ticket_classifications": [{"category": "Login Issue", "priority": "High", "sentiment": "Frustrated"}],
            "ticket_drafts": [{"domain": "technical"}],
            "resolutions": resolutions if resolutions is not None else [
                {"final_response": "Reset your password from the login page.", "escalated": False, "resolved_at": "2026-09-19T10:00:00Z"},
            ],
            "response_evaluations": [{"overall_score": judge}] if judge is not None else [],
        },
    }


@pytest.fixture(autouse=True)
def _enabled(monkeypatch, tmp_path):
    monkeypatch.setenv(job.FLAG, "true")
    monkeypatch.setenv("FEEDBACK_DISAGREEMENTS_PATH", str(tmp_path / "disagreements.jsonl"))
    monkeypatch.setattr(job, "masked", lambda text: f"M[{text}]" if text else "")


def _wire(monkeypatch, rows):
    monkeypatch.setattr(job, "_get_supabase", lambda: FakeSupabase({"customer_feedback": rows}))
    calls = []
    monkeypatch.setattr(job, "upsert_reference", lambda **kw: calls.append(kw))
    return calls


def test_disabled_flag_does_nothing(monkeypatch) -> None:
    monkeypatch.setenv(job.FLAG, "false")
    monkeypatch.setattr(job, "_get_supabase", lambda: (_ for _ in ()).throw(AssertionError("must not fetch")))
    assert job.sync_customer_feedback() == {
        "considered": 0, "synced": 0, "disagreements": 0, "skipped": 0, "disabled": True,
    }


def test_high_rating_becomes_a_masked_exemplar_with_metadata(monkeypatch) -> None:
    calls = _wire(monkeypatch, [_row(5)])

    summary = job.sync_customer_feedback()

    assert summary == {"considered": 1, "synced": 1, "disagreements": 0, "skipped": 0}
    call = calls[0]
    assert call["doc_id"] == "customer_feedback_t1"
    assert call["issue_text"] == "M[I cannot log in.]"  # OCR attachment text dropped, then masked
    assert call["resolution_text"] == "M[Reset your password from the login page.]"
    assert call["domain"] == "technical" and call["priority"] == "High" and call["category"] == "Login Issue"
    assert call["source"] == "customer_feedback"
    assert call["extra_metadata"] == {"sentiment": "Frustrated", "customer_score": 5}


def test_uses_the_latest_non_escalated_resolution(monkeypatch) -> None:
    calls = _wire(monkeypatch, [_row(4, resolutions=[
        {"final_response": "old", "escalated": False, "resolved_at": "2026-09-18T10:00:00Z"},
        {"final_response": "escalation marker", "escalated": True, "resolved_at": "2026-09-20T10:00:00Z"},
        {"final_response": "newest human answer", "escalated": False, "resolved_at": "2026-09-19T10:00:00Z"},
    ])])
    job.sync_customer_feedback()
    assert calls[0]["resolution_text"] == "M[newest human answer]"


def test_rating_on_a_ticket_with_only_an_escalation_marker_is_skipped(monkeypatch) -> None:
    calls = _wire(monkeypatch, [_row(5, resolutions=[{"final_response": "x", "escalated": True, "resolved_at": "t"}])])
    assert job.sync_customer_feedback()["skipped"] == 1
    assert calls == []


def test_middle_rating_is_ignored(monkeypatch) -> None:
    calls = _wire(monkeypatch, [_row(3)])
    assert job.sync_customer_feedback()["skipped"] == 1
    assert calls == []


def test_low_rating_is_never_embedded_and_is_logged_when_the_judge_disagreed(monkeypatch, tmp_path) -> None:
    calls = _wire(monkeypatch, [_row(1, comment="Did not help, my email a@b.com", judge=5)])

    summary = job.sync_customer_feedback()

    assert summary["disagreements"] == 1 and summary["synced"] == 0
    assert calls == []  # the pool stays all-positive
    record = json.loads((tmp_path / "disagreements.jsonl").read_text().splitlines()[0])
    assert record["ticket_id"] == "t1"
    assert record["customer_score"] == 1 and record["judge_overall"] == 5
    assert record["issue"] == "M[I cannot log in.]"
    assert record["comment"] == "M[Did not help, my email a@b.com]"
    assert record["category"] == "Login Issue" and record["sentiment"] == "Frustrated"


def test_low_rating_where_the_judge_also_scored_low_is_not_a_disagreement(monkeypatch, tmp_path) -> None:
    _wire(monkeypatch, [_row(2, judge=2)])
    summary = job.sync_customer_feedback()
    assert summary["disagreements"] == 0 and summary["skipped"] == 1
    assert not (tmp_path / "disagreements.jsonl").exists()


def test_disagreement_logging_is_idempotent(monkeypatch, tmp_path) -> None:
    _wire(monkeypatch, [_row(1, judge=5)])
    job.sync_customer_feedback()
    second = job.sync_customer_feedback()
    assert second["disagreements"] == 0 and second["skipped"] == 1
    assert len((tmp_path / "disagreements.jsonl").read_text().splitlines()) == 1


def test_a_failing_row_is_skipped_not_raised(monkeypatch) -> None:
    _wire(monkeypatch, [_row(5), _row(5, ticket_id="t2")])

    def boom(**kw):
        if kw["ticket_id"] == "t1":
            raise RuntimeError("chroma down")

    monkeypatch.setattr(job, "upsert_reference", boom)
    summary = job.sync_customer_feedback()
    assert summary["synced"] == 1 and summary["skipped"] == 1


def test_fetch_failure_returns_the_summary(monkeypatch) -> None:
    monkeypatch.setattr(job, "_get_supabase", lambda: (_ for _ in ()).throw(RuntimeError("no db")))
    assert job.sync_customer_feedback()["considered"] == 0
