"""Graph node that restores original PII (ResolvePass) after escalation drafting."""

from app.graph.state import TicketState


def _restore(text: str | None, shadow_map: dict[str, str]) -> str | None:
    if not text or not shadow_map:
        return text
    for fake_value, real_value in shadow_map.items():
        text = text.replace(fake_value, real_value)
    return text


def resolve_node(state: TicketState) -> TicketState:
    """Restore the customer's real name/email into every draft using the ShadowMap.

    Runs after validation and judging - which must only ever see the Faker
    stand-ins, never real PII - so this is the single place real values
    re-enter the text, right before it's handed off for persistence/display.
    """
    shadow_map = state.get("pii_shadow_map") or {}
    if not shadow_map:
        return {**state}

    agent_drafts = state.get("agent_drafts", {})
    restored_drafts = {
        domain: _restore(draft, shadow_map) for domain, draft in agent_drafts.items()
    }
    return {
        **state,
        "agent_drafts": restored_drafts,
        "final_response": _restore(state.get("final_response"), shadow_map),
    }
