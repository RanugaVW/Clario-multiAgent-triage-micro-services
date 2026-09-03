import csv
import json

from src.curation import collect_real_responses as collector
from src.curation.sources.common import RawExample


def _fake_source(examples):
    def _fetch(category, keywords, limit):
        return examples[:limit]

    class _Module:
        __name__ = "src.curation.sources.fake_source"
        fetch = staticmethod(_fetch)

    return _Module()


def test_collect_writes_csv_and_manifest(tmp_path, monkeypatch):
    example = RawExample(
        issue_text="I cannot log in",
        resolution_text="Please clear your browser cache and try again, this fixed it for other users.",
        source_url="https://example.com/1",
        original_id="1",
        responder_role="staff",
    )
    fake_module = _fake_source([example])

    monkeypatch.setattr(
        collector,
        "CATEGORY_CONFIG",
        {"Login Issue": {"domain": "technical", "sources": [(fake_module, ["login"])]}},
    )
    monkeypatch.setattr(collector, "TARGET_PER_CATEGORY", 1)
    monkeypatch.setattr(collector, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(collector, "CACHE_DIR", tmp_path / "batch_cache")
    monkeypatch.setattr(collector, "OUTPUT_CSV", tmp_path / "real_responses.csv")
    monkeypatch.setattr(collector, "MANIFEST_PATH", tmp_path / "manifest.json")

    manifest = collector.collect()

    assert manifest["categories"]["Login Issue"]["total"] == 1
    with (tmp_path / "real_responses.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["category"] == "Login Issue"
    assert rows[0]["domain"] == "technical"
    assert rows[0]["doc_id"] == "real_fake_source_1"

    manifest_on_disk = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest_on_disk["categories"]["Login Issue"]["total"] == 1


def test_collect_filters_pii_candidates(tmp_path, monkeypatch):
    clean = RawExample(
        issue_text="I cannot log in",
        resolution_text="Please clear your browser cache and try again, this fixed it for other users.",
        source_url="https://example.com/1",
        original_id="1",
        responder_role="staff",
    )
    with_pii = RawExample(
        issue_text="I cannot log in",
        resolution_text="Email me at support@example.com and I'll fix it manually for you.",
        source_url="https://example.com/2",
        original_id="2",
        responder_role="staff",
    )
    fake_module = _fake_source([with_pii, clean])

    monkeypatch.setattr(
        collector,
        "CATEGORY_CONFIG",
        {"Login Issue": {"domain": "technical", "sources": [(fake_module, ["login"])]}},
    )
    monkeypatch.setattr(collector, "TARGET_PER_CATEGORY", 5)
    monkeypatch.setattr(collector, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(collector, "CACHE_DIR", tmp_path / "batch_cache")
    monkeypatch.setattr(collector, "OUTPUT_CSV", tmp_path / "real_responses.csv")
    monkeypatch.setattr(collector, "MANIFEST_PATH", tmp_path / "manifest.json")

    manifest = collector.collect()

    assert manifest["categories"]["Login Issue"]["total"] == 1
    with (tmp_path / "real_responses.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["doc_id"] == "real_fake_source_1"


def test_collect_reuses_cache_on_second_run(tmp_path, monkeypatch):
    call_count = {"n": 0}

    def _fetch(category, keywords, limit):
        call_count["n"] += 1
        return [
            RawExample(
                issue_text="I cannot log in",
                resolution_text="Please clear your browser cache and try again, this fixed it.",
                source_url="https://example.com/1",
                original_id="1",
                responder_role="staff",
            )
        ]

    class _Module:
        __name__ = "src.curation.sources.fake_source"
        fetch = staticmethod(_fetch)

    monkeypatch.setattr(
        collector,
        "CATEGORY_CONFIG",
        {"Login Issue": {"domain": "technical", "sources": [(_Module(), ["login"])]}},
    )
    monkeypatch.setattr(collector, "TARGET_PER_CATEGORY", 1)
    monkeypatch.setattr(collector, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(collector, "CACHE_DIR", tmp_path / "batch_cache")
    monkeypatch.setattr(collector, "OUTPUT_CSV", tmp_path / "real_responses.csv")
    monkeypatch.setattr(collector, "MANIFEST_PATH", tmp_path / "manifest.json")

    collector.collect()
    collector.collect()

    assert call_count["n"] == 1


def test_collect_does_not_cache_empty_fetch_result(tmp_path, monkeypatch):
    call_count = {"n": 0}

    def _fetch(category, keywords, limit):
        call_count["n"] += 1
        return []

    class _Module:
        __name__ = "src.curation.sources.fake_source"
        fetch = staticmethod(_fetch)

    monkeypatch.setattr(
        collector,
        "CATEGORY_CONFIG",
        {"Login Issue": {"domain": "technical", "sources": [(_Module(), ["login"])]}},
    )
    monkeypatch.setattr(collector, "TARGET_PER_CATEGORY", 1)
    monkeypatch.setattr(collector, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(collector, "CACHE_DIR", tmp_path / "batch_cache")
    monkeypatch.setattr(collector, "OUTPUT_CSV", tmp_path / "real_responses.csv")
    monkeypatch.setattr(collector, "MANIFEST_PATH", tmp_path / "manifest.json")

    collector.collect()
    collector.collect()

    assert call_count["n"] == 2
    assert not (tmp_path / "batch_cache").exists()


def test_collect_truncates_long_fields(tmp_path, monkeypatch):
    long_text = "x" * (collector.MAX_FIELD_LENGTH + 500)
    example = RawExample(
        issue_text=long_text,
        resolution_text=long_text,
        source_url="https://example.com/1",
        original_id="1",
        responder_role="staff",
    )
    fake_module = _fake_source([example])

    monkeypatch.setattr(
        collector,
        "CATEGORY_CONFIG",
        {"Login Issue": {"domain": "technical", "sources": [(fake_module, ["login"])]}},
    )
    monkeypatch.setattr(collector, "TARGET_PER_CATEGORY", 1)
    monkeypatch.setattr(collector, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(collector, "CACHE_DIR", tmp_path / "batch_cache")
    monkeypatch.setattr(collector, "OUTPUT_CSV", tmp_path / "real_responses.csv")
    monkeypatch.setattr(collector, "MANIFEST_PATH", tmp_path / "manifest.json")

    collector.collect()

    with (tmp_path / "real_responses.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows[0]["issue_text"]) == collector.MAX_FIELD_LENGTH
    assert len(rows[0]["resolution_text"]) == collector.MAX_FIELD_LENGTH


def test_collect_escapes_formula_injection(tmp_path, monkeypatch):
    example = RawExample(
        issue_text="=cmd|'/c calc'!A1",
        resolution_text="Normal text that does not start with a formula character.",
        source_url="https://example.com/1",
        original_id="1",
        responder_role="staff",
    )
    fake_module = _fake_source([example])

    monkeypatch.setattr(
        collector,
        "CATEGORY_CONFIG",
        {"Login Issue": {"domain": "technical", "sources": [(fake_module, ["login"])]}},
    )
    monkeypatch.setattr(collector, "TARGET_PER_CATEGORY", 1)
    monkeypatch.setattr(collector, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(collector, "CACHE_DIR", tmp_path / "batch_cache")
    monkeypatch.setattr(collector, "OUTPUT_CSV", tmp_path / "real_responses.csv")
    monkeypatch.setattr(collector, "MANIFEST_PATH", tmp_path / "manifest.json")

    collector.collect()

    with (tmp_path / "real_responses.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["issue_text"] == "'=cmd|'/c calc'!A1"
    assert rows[0]["resolution_text"] == "Normal text that does not start with a formula character."


def test_collect_skips_duplicate_doc_id(tmp_path, monkeypatch, caplog):
    first = RawExample(
        issue_text="I cannot log in",
        resolution_text="Please clear your browser cache and try again, this fixed it.",
        source_url="https://example.com/1",
        original_id="1",
        responder_role="staff",
    )
    duplicate = RawExample(
        issue_text="I cannot log in either",
        resolution_text="Same fix applies here, clear your cache and retry.",
        source_url="https://example.com/1-dup",
        original_id="1",
        responder_role="staff",
    )
    fake_module = _fake_source([first, duplicate])

    monkeypatch.setattr(
        collector,
        "CATEGORY_CONFIG",
        {"Login Issue": {"domain": "technical", "sources": [(fake_module, ["login"])]}},
    )
    monkeypatch.setattr(collector, "TARGET_PER_CATEGORY", 5)
    monkeypatch.setattr(collector, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(collector, "CACHE_DIR", tmp_path / "batch_cache")
    monkeypatch.setattr(collector, "OUTPUT_CSV", tmp_path / "real_responses.csv")
    monkeypatch.setattr(collector, "MANIFEST_PATH", tmp_path / "manifest.json")

    with caplog.at_level("WARNING"):
        manifest = collector.collect()

    assert manifest["categories"]["Login Issue"]["total"] == 1
    with (tmp_path / "real_responses.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["issue_text"] == "I cannot log in"
    assert any("Duplicate doc_id" in record.message for record in caplog.records)
