"""mask_pii redacts irreversibly; mask_pii_reversible gives PERSON/EMAIL a fake stand-in."""

from app.tools.redaction_tool import mask_pii, mask_pii_reversible


def test_mask_pii_redacts_person_and_email_without_leaking_the_value() -> None:
    text, pii_found = mask_pii("Hi, I'm Jane Doe and my email is jane.doe@example.com.")
    assert "Jane Doe" not in text
    assert "jane.doe@example.com" not in text
    assert "[REDACTED_PERSON]" in text
    assert "[REDACTED_EMAIL]" in text
    assert {p["type"] for p in pii_found} == {"person", "email"}
    # The contract is type + offsets only, never the raw value.
    assert all(set(p.keys()) == {"type", "start_char", "end_char"} for p in pii_found)


def test_mask_pii_redacts_phone_and_card_generically() -> None:
    text, _ = mask_pii("Call me at +1 555 123 4567 or charge card 4111 1111 1111 1111.")
    assert "[REDACTED_PHONE]" in text
    assert "[REDACTED_CREDIT_CARD]" in text


def test_reversible_mask_replaces_name_with_a_realistic_stand_in() -> None:
    text, shadow_map, pii_found = mask_pii_reversible("Hi, I'm Jane Doe, please help.")
    assert "Jane Doe" not in text
    assert "[REDACTED_PERSON]" not in text
    assert len(shadow_map) == 1
    fake_name = next(iter(shadow_map))
    assert shadow_map[fake_name] == "Jane Doe"
    assert fake_name in text
    assert {p["type"] for p in pii_found} == {"person"}


def test_reversible_mask_gives_email_a_realistic_stand_in_too() -> None:
    text, shadow_map, _ = mask_pii_reversible("Reach me at jane.doe@example.com please.")
    assert "jane.doe@example.com" not in text
    assert "[REDACTED_EMAIL]" not in text
    assert list(shadow_map.values()) == ["jane.doe@example.com"]


def test_reversible_mask_still_redacts_phone_and_card_generically() -> None:
    """No legitimate reason for a response to ever echo these back."""
    text, shadow_map, _ = mask_pii_reversible(
        "Call +1 555 123 4567 or charge 4111 1111 1111 1111."
    )
    assert "[REDACTED_PHONE]" in text
    assert "[REDACTED_CREDIT_CARD]" in text
    assert shadow_map == {}


def test_reversible_mask_reuses_the_same_stand_in_for_repeated_mentions() -> None:
    text, shadow_map, _ = mask_pii_reversible("Jane Doe called. Jane Doe called again.")
    assert len(shadow_map) == 1
    fake_name = next(iter(shadow_map))
    assert text.count(fake_name) == 2


def test_reversible_mask_round_trips_back_to_the_original_value() -> None:
    original = "Hi, I'm Jane Doe (jane.doe@example.com)."
    text, shadow_map, _ = mask_pii_reversible(original)
    for fake_value, real_value in shadow_map.items():
        text = text.replace(fake_value, real_value)
    assert text == original
