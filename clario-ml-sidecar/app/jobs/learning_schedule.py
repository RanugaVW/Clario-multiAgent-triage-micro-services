"""Registers the live-feedback learning jobs on the app's scheduler.

Every job is gated by its own env flag and returns immediately when off, so
registering them unconditionally is safe and costs nothing.
"""

from __future__ import annotations


def register_learning_jobs(scheduler, include_kb_gap: bool = True) -> list[str]:
    from app.jobs.sync_agent_edits import sync_agent_edits
    from app.jobs.sync_customer_feedback import sync_customer_feedback

    scheduler.add_job(sync_customer_feedback, "interval", id="sync_customer_feedback", hours=24)
    scheduler.add_job(sync_agent_edits, "interval", id="sync_agent_edits", hours=24)
    ids = ["sync_customer_feedback", "sync_agent_edits"]
    if include_kb_gap:
        from app.jobs.detect_kb_gaps import detect_kb_gaps

        scheduler.add_job(detect_kb_gaps, "interval", id="detect_kb_gaps", days=7)
        ids.append("detect_kb_gaps")
    return ids
