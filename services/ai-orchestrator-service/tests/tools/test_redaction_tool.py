"""mask_pii redacts irreversibly; mask_pii_reversible gives PERSON/EMAIL a fake stand-in."""

import pytest

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


# Real bug, found live: spaCy's en_core_web_md missed "Deshan" as a PERSON
# entity entirely in "Hi I'm Deshan..." - the name flowed unmasked through
# the whole pipeline and ended up stored verbatim in a cached RAG precedent,
# later served to a different customer by that name. The self-introduction
# pattern below is a second, independent detector for exactly this phrasing,
# not dependent on spaCy's name-diversity training data.
def test_mask_pii_catches_a_self_introduced_name_ner_previously_missed() -> None:
    text, pii_found = mask_pii("Hi I'm Deshan. I logged into the system previously with my password.")
    assert "Deshan" not in text
    assert "[REDACTED_PERSON]" in text
    assert {p["type"] for p in pii_found} == {"person"}


@pytest.mark.parametrize("intro", [
    "I'm Deshan",
    "I am Deshan",
    "My name is Deshan",
    "my name is Deshan Athukorarala",
    "This is Deshan",
])
def test_mask_pii_catches_every_common_self_introduction_phrasing(intro: str) -> None:
    text, _ = mask_pii(f"{intro}, I need help logging in.")
    assert "Deshan" not in text
    assert "[REDACTED_PERSON]" in text


def test_reversible_mask_gives_a_self_introduced_name_a_stand_in_too() -> None:
    text, shadow_map, _ = mask_pii_reversible("Hi I'm Deshan, I need help logging in.")
    assert "Deshan" not in text
    assert shadow_map and list(shadow_map.values()) == ["Deshan"]


# Real bug, found live: every generated customer response opens with
# "Hi <Name>," / "Hello <Name>," / "Dear <Name>," - missed by both spaCy
# NER and SELF_INTRO_PATTERN above (neither matches this phrasing), so a
# real customer's name in a stored draft response went unmasked even with
# both other detectors in place.
@pytest.mark.parametrize(("greeting", "name"), [
    ("Hi Vidushan, thank you for reaching out.", "Vidushan"),
    ("Hello Warusha, we have resolved your issue.", "Warusha"),
    ("Dear Kalana Wijesuriya, your refund is processed.", "Kalana Wijesuriya"),
])
def test_mask_pii_catches_the_name_in_a_generated_response_greeting(greeting: str, name: str) -> None:
    text, _ = mask_pii(greeting)
    assert name not in text
    assert "[REDACTED_PERSON]" in text


def test_greeting_pattern_does_not_swallow_a_self_introduction_that_follows_it() -> None:
    """"Hi I'm Deshan," must resolve to just "Deshan", not "I'm Deshan" -
    the greeting pattern's own capitalized-word match ("I'm") must not
    shadow the more specific self-introduction match."""
    text, shadow_map, _ = mask_pii_reversible("Hi I'm Deshan, I need help logging in.")
    assert "Deshan" not in text
    assert list(shadow_map.values()) == ["Deshan"]


def test_mask_pii_does_not_flag_a_bracketed_section_marker_as_an_org() -> None:
    """Real bug, found live: a stored precedent came back as
    "[[REDACTED_ORG] not load local model...]" - spaCy NER read the words
    inside a structural [ALL CAPS] section marker as an ORG entity and
    mangled the marker itself. A real ORG mention elsewhere must still be
    caught."""
    text, found = mask_pii(
        "[INTERNAL TECHNICAL REPORT]\nCould not load local model. Emulate via Microsoft Azure.\n\n"
        "[CUSTOMER RESPONSE]\nThanks for reaching out."
    )
    assert "[INTERNAL TECHNICAL REPORT]" in text
    assert "[CUSTOMER RESPONSE]" in text
    assert "Microsoft Azure" not in text
    assert {p["type"] for p in found} == {"org"}
