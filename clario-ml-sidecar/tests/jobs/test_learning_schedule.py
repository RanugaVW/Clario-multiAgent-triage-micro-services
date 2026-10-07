"""The learning jobs are registered on the scheduler with the intended cadence."""

import pytest

from app.jobs.learning_schedule import register_learning_jobs


class _FakeScheduler:
    def __init__(self):
        self.jobs = {}

    def add_job(self, func, trigger, id, **kwargs):
        self.jobs[id] = (func.__name__, trigger, kwargs)


def test_sync_jobs_run_daily_and_kb_gap_weekly() -> None:
    pytest.importorskip("app.jobs.detect_kb_gaps")
    scheduler = _FakeScheduler()

    ids = register_learning_jobs(scheduler)

    assert ids == ["sync_customer_feedback", "sync_agent_edits", "detect_kb_gaps"]
    assert scheduler.jobs["sync_customer_feedback"] == ("sync_customer_feedback", "interval", {"hours": 24})
    assert scheduler.jobs["sync_agent_edits"] == ("sync_agent_edits", "interval", {"hours": 24})
    assert scheduler.jobs["detect_kb_gaps"] == ("detect_kb_gaps", "interval", {"days": 7})


def test_kb_gap_job_can_be_left_out() -> None:
    scheduler = _FakeScheduler()
    ids = register_learning_jobs(scheduler, include_kb_gap=False)
    assert ids == ["sync_customer_feedback", "sync_agent_edits"]
    assert "detect_kb_gaps" not in scheduler.jobs
