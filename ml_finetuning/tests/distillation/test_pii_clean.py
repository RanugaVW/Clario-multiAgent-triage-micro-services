from types import SimpleNamespace

import pandas as pd
import pytest

from src.distillation.pii_clean import mask_entities, mask_pii_dataframe


class FakeNlp:
    def pipe(self, texts, batch_size: int):
        for text in texts:
            start = text.index("Alice") if "Alice" in text else 0
            entities = [SimpleNamespace(label_="PERSON", start_char=start, end_char=start + 5)] if "Alice" in text else []
            yield SimpleNamespace(ents=entities)


def test_mask_entities_replaces_selected_entities_without_losing_offsets() -> None:
    entities = [SimpleNamespace(label_="PERSON", start_char=0, end_char=5)]

    cleaned, report = mask_entities("Alice contacted support.", entities)

    assert cleaned == "[PERSON] contacted support."
    assert report == {"person": 1}


def test_mask_pii_dataframe_masks_structured_and_named_entity_pii() -> None:
    source = pd.DataFrame({"text": ["Alice: alice@example.com, +1 212 555 0100", None]})

    cleaned, report = mask_pii_dataframe(source, "text", nlp=FakeNlp())

    assert source.loc[0, "text"].startswith("Alice")
    assert cleaned.loc[0, "text"] == "[PERSON]: [EMAIL], [PHONE]"
    assert pd.isna(cleaned.loc[1, "text"])
    assert report["person"] == report["email"] == report["phone"] == 1


def test_mask_pii_dataframe_validates_arguments() -> None:
    with pytest.raises(KeyError):
        mask_pii_dataframe(pd.DataFrame({"body": []}), "text", nlp=FakeNlp())
    with pytest.raises(ValueError):
        mask_pii_dataframe(pd.DataFrame({"text": []}), "text", nlp=FakeNlp(), batch_size=0)
