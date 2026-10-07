"""upsert_reference: backwards-compatible source + extra metadata."""

from app.tools import few_shot_selector as fss


class _Vec:
    def tolist(self):
        return [0.1, 0.2]


class _FakeEmbedder:
    def encode(self, _text, normalize_embeddings=True):
        return _Vec()


class _FakeCollection:
    def __init__(self):
        self.upserts = []

    def upsert(self, **kwargs):
        self.upserts.append(kwargs)


class _FakeClient:
    def __init__(self, collection):
        self._collection = collection

    def get_or_create_collection(self, _name):
        return self._collection


def _wire(monkeypatch):
    collection = _FakeCollection()
    monkeypatch.setattr(fss, "_get_client", lambda: _FakeClient(collection))
    monkeypatch.setattr(fss, "_embedder", lambda: _FakeEmbedder())
    return collection


def test_default_source_is_still_admin_override(monkeypatch) -> None:
    collection = _wire(monkeypatch)
    fss.upsert_reference("t1", "issue", "resolution", "technical", doc_id="d1")
    meta = collection.upserts[0]["metadatas"][0]
    assert meta["source"] == "admin_override"
    assert collection.upserts[0]["ids"] == ["d1"]


def test_custom_source_and_extra_metadata_are_stored(monkeypatch) -> None:
    collection = _wire(monkeypatch)
    fss.upsert_reference(
        "t1", "issue", "resolution", "billing", priority="High", category="Billing", doc_id="customer_feedback_t1",
        source="customer_feedback", extra_metadata={"sentiment": "Frustrated", "customer_score": 5},
    )
    meta = collection.upserts[0]["metadatas"][0]
    assert meta["source"] == "customer_feedback"
    assert meta["sentiment"] == "Frustrated"
    assert meta["customer_score"] == 5
    assert meta["priority"] == "High" and meta["domain"] == "billing"


def test_extra_metadata_cannot_overwrite_core_fields(monkeypatch) -> None:
    collection = _wire(monkeypatch)
    fss.upsert_reference("t1", "issue", "res", "billing", extra_metadata={"domain": "hr", "ticket_id": "evil"})
    meta = collection.upserts[0]["metadatas"][0]
    assert meta["domain"] == "billing" and meta["ticket_id"] == "t1"


def test_empty_text_is_ignored(monkeypatch) -> None:
    collection = _wire(monkeypatch)
    fss.upsert_reference("t1", "", "res", "billing")
    fss.upsert_reference("t1", "issue", "", "billing")
    assert collection.upserts == []
