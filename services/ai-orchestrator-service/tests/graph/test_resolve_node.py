"""resolve_node restores real PII into every draft and final_response using the ShadowMap."""

from app.graph.resolve_node import resolve_node


def test_restores_real_name_into_every_domain_draft() -> None:
    state = {
        "agent_drafts": {
            "technical": "Hi Jordan Blake, please clear your cache.",
            "billing": "Hi Jordan Blake, your refund is processing.",
        },
        "final_response": None,
        "pii_shadow_map": {"Jordan Blake": "Kalana Wijesuriya"},
    }
    result = resolve_node(state)
    assert result["agent_drafts"]["technical"] == "Hi Kalana Wijesuriya, please clear your cache."
    assert result["agent_drafts"]["billing"] == "Hi Kalana Wijesuriya, your refund is processing."


def test_restores_real_name_into_final_response_when_set() -> None:
    state = {
        "agent_drafts": {"technical": "Hi Jordan Blake, please clear your cache."},
        "final_response": "Hi Jordan Blake, please clear your cache.",
        "pii_shadow_map": {"Jordan Blake": "Kalana Wijesuriya"},
    }
    result = resolve_node(state)
    assert result["final_response"] == "Hi Kalana Wijesuriya, please clear your cache."


def test_leaves_final_response_none_when_escalated() -> None:
    state = {
        "agent_drafts": {"technical": "Hi Jordan Blake, please clear your cache."},
        "final_response": None,
        "pii_shadow_map": {"Jordan Blake": "Kalana Wijesuriya"},
    }
    result = resolve_node(state)
    assert result["final_response"] is None


def test_empty_shadow_map_is_a_no_op() -> None:
    """Cache-hit tickets skip surrogate_node and never get a shadow map."""
    state = {
        "agent_drafts": {"technical": "Please clear your cache."},
        "final_response": "Please clear your cache.",
        "pii_shadow_map": {},
    }
    result = resolve_node(state)
    assert result == state


def test_missing_shadow_map_key_is_also_a_no_op() -> None:
    state = {"agent_drafts": {"technical": "Please clear your cache."}, "final_response": None}
    result = resolve_node(state)
    assert result == state
