"""KB-gap detection: cluster weak tickets, propose (never publish) missing documents."""

from pathlib import Path

import numpy as np
import pytest
from _job_fakes import FakeSupabase

from app.jobs import detect_kb_gaps as job

VECTORS = {
    "refund a1": [1.0, 0.0, 0.0], "refund a2": [0.99, 0.05, 0.0], "refund a3": [0.98, 0.1, 0.0],
    "login b1": [0.0, 1.0, 0.0], "login b2": [0.05, 0.99, 0.0], "login b3": [0.1, 0.98, 0.0],
    "lonely c1": [0.0, 0.0, 1.0],
}


def _ticket(tid, text, *, rag=0.4, grounded=None, rating=None, domain="billing", human_reply=None):
    return {
        "id": tid, "raw_text": text,
        "ticket_drafts": [{"domain": domain, "rag_top_score": rag}],
        "response_evaluations": [{"groundedness_score": grounded}] if grounded is not None else [],
        "customer_feedback": {"score": rating} if rating is not None else None,
        "resolutions": (
            [{"final_response": human_reply, "escalated": False, "resolved_by": "agent-1"}] if human_reply else []
        ),
    }


def _gap_tickets():
    return [
        _ticket("a1", "refund a1", human_reply="Refunds go back to the original card in 5-7 days."),
        _ticket("a2", "refund a2"), _ticket("a3", "refund a3"),
        _ticket("b1", "login b1", domain="technical"), _ticket("b2", "login b2", domain="technical"),
        _ticket("b3", "login b3", domain="technical"),
        _ticket("c1", "lonely c1"),
    ]


@pytest.fixture(autouse=True)
def _enabled(monkeypatch, tmp_path):
    monkeypatch.setenv(job.FLAG, "true")
    monkeypatch.setenv("KB_PROPOSALS_DIR", str(tmp_path / "proposals"))
    monkeypatch.setattr(job, "masked", lambda text: text)
    monkeypatch.setattr(job, "_embed", lambda texts: np.array([VECTORS[t] for t in texts]))


def _wire(monkeypatch, tickets, kb_matches=None):
    monkeypatch.setattr(job, "_get_supabase", lambda: FakeSupabase({"tickets": tickets}))
    monkeypatch.setattr(job, "retrieve_context", lambda query, domain, **_k: kb_matches or [])
    prompts = []

    def fake_llm(prompt):
        prompts.append(prompt)
        return "# Refund timelines\n## Common customer phrasing\n- Where is my refund?\n## Guidance\n[NEEDS CONFIRMATION]"

    monkeypatch.setattr(job, "_llm", fake_llm)
    return prompts


def test_disabled_flag_does_nothing(monkeypatch) -> None:
    monkeypatch.setenv(job.FLAG, "false")
    monkeypatch.setattr(job, "_get_supabase", lambda: (_ for _ in ()).throw(AssertionError("must not fetch")))
    assert job.detect_kb_gaps()["disabled"] is True


def test_two_gap_clusters_become_two_proposals_and_the_outlier_is_ignored(monkeypatch, tmp_path) -> None:
    _wire(monkeypatch, _gap_tickets())

    summary = job.detect_kb_gaps()

    assert summary["candidates"] == 7 and summary["clusters"] == 2 and summary["proposed"] == 2
    files = sorted(p.name for p in (tmp_path / "proposals").glob("*.md"))
    assert len(files) == 2
    assert any(f.startswith("billing-") for f in files) and any(f.startswith("technical-") for f in files)


def test_proposal_file_has_evidence_frontmatter_and_body(monkeypatch, tmp_path) -> None:
    _wire(monkeypatch, _gap_tickets())
    job.detect_kb_gaps()

    billing = next((tmp_path / "proposals").glob("billing-*.md")).read_text()
    assert billing.startswith("---\nstatus: proposed\n")
    assert "cluster_size: 3" in billing and "domain: billing" in billing
    assert "a1" in billing and "a2" in billing and "a3" in billing
    assert "# Refund timelines" in billing


def test_prompt_uses_masked_tickets_and_only_human_written_resolutions(monkeypatch) -> None:
    monkeypatch.setattr(job, "masked", lambda text: f"M[{text}]")
    tickets = _gap_tickets()
    tickets[1]["resolutions"] = [{"final_response": "AI generated answer", "escalated": False, "resolved_by": None}]
    # the embed stub is keyed on the masked text
    monkeypatch.setattr(job, "_embed", lambda texts: np.array([VECTORS[t[2:-1]] for t in texts]))
    prompts = _wire(monkeypatch, tickets)

    job.detect_kb_gaps()

    billing_prompt = next(p for p in prompts if "refund a1" in p)
    assert "M[refund a1]" in billing_prompt
    assert "M[Refunds go back to the original card in 5-7 days.]" in billing_prompt
    assert "AI generated answer" not in billing_prompt  # AI replies are not a trusted source of facts


def test_cluster_the_kb_already_covers_is_not_a_gap(monkeypatch, tmp_path) -> None:
    _wire(monkeypatch, _gap_tickets(), kb_matches=[{"text": "x", "source_file": "billing/refund.md", "score": 0.85}])

    summary = job.detect_kb_gaps()

    assert summary["covered"] == 2 and summary["proposed"] == 0
    assert not (tmp_path / "proposals").exists() or not list((tmp_path / "proposals").glob("*.md"))


def test_tickets_with_no_weak_signal_are_not_candidates(monkeypatch) -> None:
    healthy = [_ticket(f"h{i}", "refund a1", rag=0.9, grounded=5, rating=5) for i in range(5)]
    _wire(monkeypatch, healthy)
    summary = job.detect_kb_gaps()
    assert summary["candidates"] == 0 and summary["proposed"] == 0


@pytest.mark.parametrize("kwargs", [
    {"rag": 0.5},
    {"rag": 0.9, "grounded": 3},
    {"rag": 0.9, "rating": 2},
])
def test_each_weak_signal_alone_makes_a_candidate(monkeypatch, kwargs) -> None:
    _wire(monkeypatch, [_ticket("x1", "refund a1", **kwargs)])
    assert job.detect_kb_gaps()["candidates"] == 1


def test_rerun_does_not_rewrite_or_duplicate_proposals(monkeypatch, tmp_path) -> None:
    _wire(monkeypatch, _gap_tickets())
    job.detect_kb_gaps()
    before = {p.name: p.read_text() for p in (tmp_path / "proposals").glob("*.md")}

    second = job.detect_kb_gaps()

    assert second["proposed"] == 0 and second["skipped"] == 2
    assert {p.name: p.read_text() for p in (tmp_path / "proposals").glob("*.md")} == before


def test_llm_failure_skips_the_cluster_without_writing(monkeypatch, tmp_path) -> None:
    _wire(monkeypatch, _gap_tickets())
    monkeypatch.setattr(job, "_llm", lambda prompt: (_ for _ in ()).throw(RuntimeError("quota")))

    summary = job.detect_kb_gaps()

    assert summary["proposed"] == 0 and summary["skipped"] == 2
    assert not list((tmp_path / "proposals").glob("*.md"))


def test_proposals_can_never_be_written_into_the_live_kb(monkeypatch) -> None:
    kb_dir = Path(job._KB_DOCS_DIR)
    monkeypatch.setenv("KB_PROPOSALS_DIR", str(kb_dir / "sneaky"))
    with pytest.raises(ValueError):
        job._proposals_dir()
    monkeypatch.setenv("KB_PROPOSALS_DIR", str(kb_dir))
    with pytest.raises(ValueError):
        job._proposals_dir()


def test_fetch_failure_returns_the_summary(monkeypatch) -> None:
    monkeypatch.setattr(job, "_get_supabase", lambda: (_ for _ in ()).throw(RuntimeError("no db")))
    assert job.detect_kb_gaps()["candidates"] == 0
