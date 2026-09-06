"""Admin-correction feedback job: only upward overrides feed validation_refs."""

from app.jobs import sync_judge_references as sjr


class _FakeResult:
    def __init__(self, data: list[dict]) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, data: list[dict]) -> None:
        self._data = data

    def select(self, *_a, **_k) -> "_FakeQuery":
        return self

    def gte(self, *_a, **_k) -> "_FakeQuery":
        return self

    def execute(self) -> _FakeResult:
        return _FakeResult(self._data)


class _FakeClient:
    def __init__(self, data: list[dict]) -> None:
        self._data = data

    def table(self, _name: str) -> _FakeQuery:
        return _FakeQuery(self._data)


def _override(overall_score, previous_overall, **evaluation_overrides) -> dict:
    evaluation = {
        "domain": "technical",
        "priority_at_evaluation": "High",
        "category_at_evaluation": "Technical",
        "ticket_drafts": {"draft_text": "Please clear your cache and cookies."},
        "tickets": {"id": "ticket-1", "raw_text": "I cannot login, my email is a@b.com"},
        **evaluation_overrides,
    }
    return {
        "id": "override-1",
        "overall_score": overall_score,
        "previous_scores": {"overall_score": previous_overall},
        "response_evaluations": evaluation,
    }


def _stub_client(monkeypatch, overrides: list[dict]) -> None:
    monkeypatch.setattr(sjr, "_get_supabase", lambda: _FakeClient(overrides))


def test_syncs_an_upward_override_as_a_new_reference(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(sjr, "upsert_reference", lambda **kw: calls.append(kw))
    monkeypatch.setattr(sjr, "mask_pii", lambda text: (f"[REDACTED] {text[-10:]}", []))
    _stub_client(monkeypatch, [_override(overall_score=4, previous_overall=2)])

    summary = sjr.sync_judge_references()

    assert summary == {"considered": 1, "synced": 1, "skipped": 0}
    assert len(calls) == 1
    assert calls[0]["ticket_id"] == "ticket-1"
    assert calls[0]["domain"] == "technical"
    assert calls[0]["priority"] == "High"
    assert calls[0]["category"] == "Technical"
    assert calls[0]["doc_id"] == "admin_override_override-1"
    # The raw ticket text must never reach the reference pool unredacted.
    assert calls[0]["issue_text"].startswith("[REDACTED]")
    # Real bug, found live: only the issue side used to be redacted here.
    # draft_text is an admin-approved response to ONE customer and can carry
    # that customer's real name - select_few_shots() then hands it, unmasked,
    # straight into the judge LLM's prompt for every OTHER customer's ticket
    # it happens to match. Same failure mode as the cache/RAG precedent leak,
    # different pipeline - the resolution side must be redacted too.
    assert calls[0]["resolution_text"].startswith("[REDACTED]")


def test_resolution_text_pii_never_reaches_the_reference_pool_unmasked(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(sjr, "upsert_reference", lambda **kw: calls.append(kw))
    override = _override(
        overall_score=5,
        previous_overall=2,
        ticket_drafts={"draft_text": "Hi Deshan, I've refunded your payment to jane.doe@example.com."},
    )
    _stub_client(monkeypatch, [override])

    sjr.sync_judge_references()

    assert len(calls) == 1
    assert "Deshan" not in calls[0]["resolution_text"]
    assert "jane.doe@example.com" not in calls[0]["resolution_text"]


def test_skips_a_downward_override(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(sjr, "upsert_reference", lambda **kw: calls.append(kw))
    _stub_client(monkeypatch, [_override(overall_score=2, previous_overall=4)])

    summary = sjr.sync_judge_references()

    assert summary == {"considered": 1, "synced": 0, "skipped": 1}
    assert not calls


def test_skips_an_unchanged_override(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(sjr, "upsert_reference", lambda **kw: calls.append(kw))
    _stub_client(monkeypatch, [_override(overall_score=3, previous_overall=3)])

    summary = sjr.sync_judge_references()

    assert summary["synced"] == 0
    assert not calls


def test_skips_when_draft_or_ticket_data_is_missing(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(sjr, "upsert_reference", lambda **kw: calls.append(kw))
    override = _override(overall_score=5, previous_overall=1, ticket_drafts=None)
    _stub_client(monkeypatch, [override])

    summary = sjr.sync_judge_references()

    assert summary == {"considered": 1, "synced": 0, "skipped": 1}
    assert not calls


def test_one_bad_override_does_not_stop_the_batch(monkeypatch) -> None:
    calls = []

    def flaky_upsert(**kw):
        if len(calls) == 0:
            calls.append(kw)
            raise RuntimeError("chroma unavailable")
        calls.append(kw)

    monkeypatch.setattr(sjr, "upsert_reference", flaky_upsert)
    monkeypatch.setattr(sjr, "mask_pii", lambda text: (text, []))
    overrides = [
        _override(overall_score=4, previous_overall=1),
        _override(overall_score=5, previous_overall=2),
    ]
    overrides[0]["id"] = "override-1"
    overrides[1]["id"] = "override-2"
    _stub_client(monkeypatch, overrides)

    summary = sjr.sync_judge_references()

    assert summary == {"considered": 2, "synced": 1, "skipped": 1}
    assert len(calls) == 2


def test_fetch_failure_returns_empty_summary_without_raising(monkeypatch) -> None:
    def boom():
        raise RuntimeError("supabase unreachable")

    monkeypatch.setattr(sjr, "_get_supabase", boom)

    summary = sjr.sync_judge_references()

    assert summary == {"considered": 0, "synced": 0, "skipped": 0}
