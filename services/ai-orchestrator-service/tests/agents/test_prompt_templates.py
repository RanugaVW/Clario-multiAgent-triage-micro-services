from app.agents.shared.prompt_templates import build_specialist_prompt


def test_build_specialist_prompt_includes_extra_instructions_when_given() -> None:
    prompt = build_specialist_prompt(
        "issue", [], "hr", extra_instructions="Do not promise a specific outcome."
    )
    assert "Do not promise a specific outcome." in prompt


def test_build_specialist_prompt_omits_extra_instructions_by_default() -> None:
    prompt = build_specialist_prompt("issue", [], "technical")
    assert "Do not promise" not in prompt
