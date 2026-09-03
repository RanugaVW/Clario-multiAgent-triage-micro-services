import argparse
import asyncio

from scripts import run_pairwise_evaluation as rpe


def _args(**overrides):
    defaults = {"csv": "unused.csv", "ticket_col": "ticket_text", "source_col": "source", "response_col": "response"}
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class _FakeGraph:
    def __init__(self, final_state):
        self._final_state = final_state

    async def ainvoke(self, initial_state):
        self.received_state = initial_state
        return self._final_state


class _FakeJudge:
    def __init__(self, verdict):
        self._verdict = verdict
        self.calls = []

    async def compare_draft_to_reference(self, **kwargs):
        self.calls.append(kwargs)
        return self._verdict


class _FakeTable:
    def __init__(self):
        self.inserted = []

    def insert(self, payload):
        self.inserted.append(payload)
        return self

    def execute(self):
        return None


class _FakeSupabase:
    def __init__(self):
        self.pairwise_table = _FakeTable()

    def table(self, name):
        assert name == "pairwise_evaluations"
        return self.pairwise_table


class _Verdict:
    winner_pass1 = "draft"
    winner_pass2 = "draft"
    reasoning_pass1 = "Better."
    reasoning_pass2 = "Still better."
    final_winner = "draft"
    judge_model = "gemini-flash-latest"
    evaluation_latency_ms = 1200


def test_build_initial_state_matches_process_ticket_shape():
    state = rpe._build_initial_state("row-1", "I cannot log in")

    assert state == {
        "ticket_id": "row-1",
        "raw_text": "I cannot log in",
        "reflection_count": 0,
        "reflection_critiques": [],
        "reroute_attempted": False,
        "needs_reroute": False,
        "agent_drafts": {},
        "retrieved_context": {},
        "rag_top_score": {},
        "low_relevance_flags": {},
        "validation_result": {},
    }


def test_evaluate_one_ticket_inserts_a_row_per_domain(monkeypatch):
    final_state = {
        "agent_drafts": {"technical": "Try resetting your password."},
        "redacted_text": "I cannot log in",
        "category": "Login Issue",
        "priority": "Medium",
        "judge_evaluations": {"technical": {"overall_score": 4}},
    }
    graph = _FakeGraph(final_state)
    judge = _FakeJudge(_Verdict())
    supabase = _FakeSupabase()

    monkeypatch.setattr(rpe, "mask_pii", lambda text: (f"REDACTED[{text}]", []))

    row = {"ticket_text": "I cannot log in", "source": "https://example.com/t/1", "response": "Clear your cache."}
    asyncio.run(rpe._evaluate_one_ticket(graph, judge, supabase, "run-1", {**row, "_source_doc_id": "rysera_row_0"}, _args()))

    assert len(supabase.pairwise_table.inserted) == 1
    payload = supabase.pairwise_table.inserted[0]
    assert payload["eval_run_id"] == "run-1"
    assert payload["source_doc_id"] == "rysera_row_0"
    assert payload["domain"] == "technical"
    assert payload["generated_draft"] == "Try resetting your password."
    assert payload["reference_response"] == "REDACTED[Clear your cache.]"
    assert payload["final_winner"] == "draft"
    assert payload["absolute_overall_score"] == 4
    assert len(judge.calls) == 1
    assert judge.calls[0]["draft"] == "Try resetting your password."
    assert judge.calls[0]["reference"] == "REDACTED[Clear your cache.]"


def test_evaluate_one_ticket_skips_when_no_draft_produced(monkeypatch):
    final_state = {"agent_drafts": {}, "redacted_text": "x", "category": "Bug Report", "priority": "Low", "judge_evaluations": {}}
    graph = _FakeGraph(final_state)
    judge = _FakeJudge(_Verdict())
    supabase = _FakeSupabase()
    monkeypatch.setattr(rpe, "mask_pii", lambda text: (text, []))

    row = {"ticket_text": "x", "source": "s", "response": "r", "_source_doc_id": "rysera_row_0"}
    asyncio.run(rpe._evaluate_one_ticket(graph, judge, supabase, "run-1", row, _args()))

    assert supabase.pairwise_table.inserted == []
    assert judge.calls == []


def test_run_continues_past_a_failing_row(monkeypatch, tmp_path):
    csv_path = tmp_path / "rysera.csv"
    csv_path.write_text(
        "ticket_text,source,response\n"
        "bad row,https://example.com/1,resp1\n"
        "good row,https://example.com/2,resp2\n",
        encoding="utf-8",
    )

    calls = {"n": 0}

    async def _fake_evaluate(graph, judge, supabase, eval_run_id, row, args):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("judge outage")

    monkeypatch.setattr(rpe, "build_graph", lambda: object())
    monkeypatch.setattr(rpe, "get_judge", lambda: object())
    monkeypatch.setattr(rpe, "_get_supabase", lambda: object())
    monkeypatch.setattr(rpe, "_evaluate_one_ticket", _fake_evaluate)

    summary = asyncio.run(rpe.run(_args(csv=str(csv_path))))

    assert summary == {"processed": 1, "skipped": 0, "failed": 1}
