"""agent_edit_refs store: gated retrieval that can never break drafting."""

from app.tools import agent_edit_store as store


class _Vec:
    def tolist(self):
        return [0.1, 0.2]


class _Embedder:
    def encode(self, _text, normalize_embeddings=True):
        return _Vec()


class _Collection:
    def __init__(self, result=None):
        self.upserts, self.queries, self._result = [], [], result

    def upsert(self, **kw):
        self.upserts.append(kw)

    def query(self, **kw):
        self.queries.append(kw)
        return self._result


class _Client:
    def __init__(self, collection=None, missing=False):
        self._collection, self._missing = collection, missing

    def get_or_create_collection(self, _name):
        return self._collection

    def get_collection(self, _name):
        if self._missing:
            raise ValueError("Collection does not exist")
        return self._collection


def _wire(monkeypatch, collection=None, missing=False):
    monkeypatch.setattr(store, "_get_client", lambda: _Client(collection, missing))
    monkeypatch.setattr(store, "_embedder", lambda: _Embedder())


def _result(*items):
    # items: (takeaway, edit_type, distance)
    return {
        "documents": [[t for t, _, _ in items]],
        "metadatas": [[{"edit_type": et, "review_id": f"r{i}"} for i, (_, et, _) in enumerate(items)]],
        "distances": [[d for _, _, d in items]],
    }


def test_upsert_stores_takeaway_with_deterministic_id_and_metadata(monkeypatch) -> None:
    collection = _Collection()
    _wire(monkeypatch, collection)

    store.upsert_agent_edit(
        review_id="r1", issue_text="cannot log in", takeaway="Mention the 2FA reset link.",
        edit_type="factual", domain="technical", category="Login", priority="High", sentiment="Frustrated",
    )

    call = collection.upserts[0]
    assert call["ids"] == ["edit_r1"]
    assert call["documents"] == ["Mention the 2FA reset link."]
    assert call["metadatas"][0] == {
        "edit_type": "factual", "domain": "technical", "category": "Login",
        "priority": "High", "sentiment": "Frustrated", "review_id": "r1",
    }


def test_upsert_ignores_empty_input(monkeypatch) -> None:
    collection = _Collection()
    _wire(monkeypatch, collection)
    store.upsert_agent_edit(review_id="r1", issue_text="", takeaway="x", edit_type="style",
                            domain="hr", category="c", priority="p", sentiment="s")
    assert collection.upserts == []


def test_select_is_a_noop_when_the_flag_is_off(monkeypatch) -> None:
    monkeypatch.delenv(store.FLAG, raising=False)
    monkeypatch.setattr(store, "_get_client", lambda: (_ for _ in ()).throw(AssertionError("must not touch chroma")))
    assert store.select_agent_edits("cannot log in", "technical") == []


def test_select_filters_by_domain_and_similarity(monkeypatch) -> None:
    monkeypatch.setenv(store.FLAG, "true")
    # distance 0.2 -> similarity 0.9 ; distance 1.4 -> similarity 0.3 (below default 0.5)
    collection = _Collection(_result(("close", "factual", 0.2), ("far", "style", 1.4)))
    _wire(monkeypatch, collection)

    edits = store.select_agent_edits("cannot log in", "technical")

    assert [e["takeaway"] for e in edits] == ["close"]
    assert edits[0]["similarity"] == 0.9 and edits[0]["edit_type"] == "factual"
    assert collection.queries[0]["where"] == {"domain": "technical"}


def test_select_returns_empty_when_the_collection_does_not_exist_yet(monkeypatch) -> None:
    monkeypatch.setenv(store.FLAG, "true")
    _wire(monkeypatch, missing=True)
    assert store.select_agent_edits("cannot log in", "technical") == []


def test_select_never_raises(monkeypatch) -> None:
    monkeypatch.setenv(store.FLAG, "true")
    monkeypatch.setattr(store, "_get_client", lambda: (_ for _ in ()).throw(RuntimeError("chroma exploded")))
    assert store.select_agent_edits("cannot log in", "technical") == []


def test_format_edit_guidance_includes_style_only() -> None:
    edits = [
        {"takeaway": "Open with an apology for a delayed reply.", "edit_type": "style"},
        {"takeaway": "Refunds take 5-7 business days.", "edit_type": "factual"},
    ]
    text = store.format_edit_guidance(edits)
    assert "Open with an apology" in text
    assert "Refunds take" not in text


def test_format_edit_guidance_is_none_without_style_edits() -> None:
    assert store.format_edit_guidance([]) is None
    assert store.format_edit_guidance([{"takeaway": "x", "edit_type": "factual"}]) is None


def test_factual_context_items_never_raise_the_relevance_gate() -> None:
    edits = [
        {"takeaway": "Refunds take 5-7 business days.", "edit_type": "factual"},
        {"takeaway": "Be warmer.", "edit_type": "style"},
    ]
    assert store.factual_context_items(edits) == [
        {"source_file": "agent_edit_correction", "text": "Refunds take 5-7 business days.", "score": 0.0},
    ]
