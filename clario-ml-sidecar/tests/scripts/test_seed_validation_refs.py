import csv

from scripts import seed_validation_refs


def _write_csv(path, rows):
    fieldnames = ["doc_id", "category", "domain", "issue_text", "resolution_text", "source", "source_url", "responder_role", "collected_at"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_seed_from_csv_upserts_valid_rows_and_skips_incomplete_ones(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(seed_validation_refs, "upsert_reference", lambda **kwargs: calls.append(kwargs))

    csv_path = tmp_path / "real_responses.csv"
    _write_csv(csv_path, [
        {
            "doc_id": "real_moodle_jira_MDL-1001",
            "category": "Login Issue",
            "domain": "technical",
            "issue_text": "I cannot log in",
            "resolution_text": "Clear your browser cache and try again.",
            "source": "moodle_jira",
            "source_url": "https://moodle.atlassian.net/browse/MDL-1001",
            "responder_role": "commenter",
            "collected_at": "2026-09-03T00:00:00+00:00",
        },
        {
            "doc_id": "real_discourse_forums_community.udemy.com:555",
            "category": "Account Suspension",
            "domain": "",
            "issue_text": "My account was suspended",
            "resolution_text": "",
            "source": "discourse_forums",
            "source_url": "https://community.udemy.com/t/x/555",
            "responder_role": "staff",
            "collected_at": "2026-09-03T00:00:00+00:00",
        },
    ])

    summary = seed_validation_refs.seed_from_csv(csv_path)

    assert summary == {"read": 2, "seeded": 1, "skipped": 1}
    assert len(calls) == 1
    assert calls[0] == {
        "ticket_id": "real_moodle_jira_MDL-1001",
        "issue_text": "I cannot log in",
        "resolution_text": "Clear your browser cache and try again.",
        "domain": "technical",
        "priority": "Unknown",
        "category": "Login Issue",
        "doc_id": "real_moodle_jira_MDL-1001",
    }
