"""Agent-edit job: learn generalized, PII-free takeaways from human edits."""

import pytest
from _job_fakes import FakeSupabase

from app.jobs import sync_agent_edits as job


def _review(original="Please clear your cache.", final="Please reset your password via the login page.", rid="r1"):
    return {
        "id": rid, "decision": "edited", "original_draft": original, "final_draft": final,
        "tickets": {
            "id": "t1", "raw_text": "I cannot log in",
            "ticket_classifications": [{"category": "Login Issue", "priority": "High", "sentiment": "Frustrated"}],
            "ticket_drafts": [{"domain": "technical"}],
        },
    }


@pytest.fixture(autouse=True)
def _enabled(monkeypatch):
    monkeypatch.setenv(job.FLAG, "true")
    monkeypatch.setattr(job, "masked", lambda text: f"M[{text}]" if text else "")
    monkeypatch.setattr(job, "contains_pii", lambda text: "@" in text)


def _wire(monkeypatch, reviews, llm_reply='{"edit_type": "factual", "takeaway": "Point customers to the login-page reset."}'):
    monkeypatch.setattr(job, "_get_supabase", lambda: FakeSupabase({"human_reviews": reviews}))
    stored, prompts = [], []
    monkeypatch.setattr(job, "upsert_agent_edit", lambda **kw: stored.append(kw))

    def fake_llm(prompt):
        prompts.append(prompt)
        if isinstance(llm_reply, Exception):
            raise llm_reply
        return llm_reply

    monkeypatch.setattr(job, "_llm", fake_llm)
    return stored, prompts


def test_disabled_flag_does_nothing(monkeypatch) -> None:
    monkeypatch.setenv(job.FLAG, "false")
    monkeypatch.setattr(job, "_get_supabase", lambda: (_ for _ in ()).throw(AssertionError("must not fetch")))
    assert job.sync_agent_edits() == {"considered": 0, "synced": 0, "skipped": 0, "disabled": True}


def test_edited_review_is_stored_as_a_masked_takeaway(monkeypatch) -> None:
    stored, prompts = _wire(monkeypatch, [_review()])

    summary = job.sync_agent_edits()

    assert summary == {"considered": 1, "synced": 1, "skipped": 0}
    call = stored[0]
    assert call["review_id"] == "r1"
    assert call["issue_text"] == "M[I cannot log in]"
    assert call["takeaway"] == "Point customers to the login-page reset."
    assert call["edit_type"] == "factual"
    assert call["domain"] == "technical" and call["category"] == "Login Issue"
    assert call["priority"] == "High" and call["sentiment"] == "Frustrated"
    # The LLM only ever sees masked text.
    assert "M[Please clear your cache.]" in prompts[0]
    assert "M[Please reset your password via the login page.]" in prompts[0]


def test_only_the_customer_section_of_the_original_draft_is_compared(monkeypatch) -> None:
    original = "[INTERNAL TECHNICAL REPORT]\nroot cause\n\n[CUSTOMER RESPONSE]\nHello, please restart."
    stored, prompts = _wire(monkeypatch, [_review(original=original, final="Hello, please restart.")])

    summary = job.sync_agent_edits()

    assert summary["skipped"] == 1 and stored == [] and prompts == []  # identical => no LLM call


def test_style_edits_are_stored_as_style(monkeypatch) -> None:
    stored, _ = _wire(monkeypatch, [_review()], '{"edit_type": "style", "takeaway": "Open with an apology."}')
    job.sync_agent_edits()
    assert stored[0]["edit_type"] == "style"


def test_json_wrapped_in_a_code_fence_is_accepted(monkeypatch) -> None:
    stored, _ = _wire(monkeypatch, [_review()], '```json\n{"edit_type": "style", "takeaway": "Be warmer."}\n```')
    job.sync_agent_edits()
    assert stored[0]["takeaway"] == "Be warmer."


@pytest.mark.parametrize("reply", [
    "not json at all",
    '{"edit_type": "opinion", "takeaway": "x"}',
    '{"edit_type": "factual", "takeaway": ""}',
    '{"edit_type": "factual", "takeaway": "' + "a" * 301 + '"}',
    '{"edit_type": "factual", "takeaway": "Email jane@example.com about it"}',
])
def test_unusable_llm_output_is_skipped_and_never_stored(monkeypatch, reply) -> None:
    stored, _ = _wire(monkeypatch, [_review()], reply)
    summary = job.sync_agent_edits()
    assert summary["skipped"] == 1 and stored == []


def test_llm_failure_is_skipped_not_raised(monkeypatch) -> None:
    stored, _ = _wire(monkeypatch, [_review()], RuntimeError("quota exhausted"))
    assert job.sync_agent_edits()["skipped"] == 1
    assert stored == []


def test_review_without_a_final_draft_is_skipped(monkeypatch) -> None:
    stored, _ = _wire(monkeypatch, [_review(final=None)])
    assert job.sync_agent_edits()["skipped"] == 1
    assert stored == []


def test_fetch_failure_returns_the_summary(monkeypatch) -> None:
    monkeypatch.setattr(job, "_get_supabase", lambda: (_ for _ in ()).throw(RuntimeError("no db")))
    assert job.sync_agent_edits()["considered"] == 0
