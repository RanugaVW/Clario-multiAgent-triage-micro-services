"""surrogate_node redacts raw_text reversibly and carries the shadow map forward."""

from app.graph.surrogate_node import surrogate_node


def test_writes_redacted_text_pii_found_and_shadow_map_without_touching_raw_text() -> None:
    state = {"raw_text": "Hi, I'm Jane Doe, my email is jane.doe@example.com."}
    result = surrogate_node(state)

    assert result["raw_text"] == state["raw_text"]
    assert "Jane Doe" not in result["redacted_text"]
    assert "jane.doe@example.com" not in result["redacted_text"]
    assert result["pii_shadow_map"]
    assert {p["type"] for p in result["pii_found"]} == {"person", "email"}
    # Every fake stand-in in the shadow map must actually appear in redacted_text.
    for fake_value in result["pii_shadow_map"]:
        assert fake_value in result["redacted_text"]


def test_no_pii_yields_an_empty_shadow_map() -> None:
    result = surrogate_node({"raw_text": "My internet connection keeps dropping."})
    assert result["pii_shadow_map"] == {}
    assert result["redacted_text"] == "My internet connection keeps dropping."
