"""build_graph() must wrap every node with trace_node so tracing is applied
exactly once per node, at graph-construction time - not scattered across
the 13 individual node files."""

import app.graph.graph_builder as gb


def test_build_graph_wraps_every_node_with_trace_node(monkeypatch) -> None:
    wrapped_names = []

    def fake_trace_node(step_name):
        wrapped_names.append(step_name)
        return lambda fn: fn  # identity wrapper - just record the call

    monkeypatch.setattr(gb, "trace_node", fake_trace_node)
    gb.build_graph()

    expected = {
        "cache_check", "surrogate", "analyzer", "classification", "routing",
        "technical_agent", "billing_agent", "both_specialists", "validation",
        "reflection", "response_judge", "escalation", "handoff", "resolve",
    }
    assert expected.issubset(set(wrapped_names))
