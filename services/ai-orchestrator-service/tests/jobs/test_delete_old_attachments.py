"""delete_old_attachments must remove only the stored image + its path
reference for tickets older than 3 days - it must never touch the
ticket's text/history, and must not crash the scheduler if one deletion
fails (matches sync_judge_references' resilience contract)."""

from unittest.mock import MagicMock

from app.jobs import delete_old_attachments as doa


def _stub_client(monkeypatch, rows: list[dict]) -> MagicMock:
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.not_.is_.return_value.lt.return_value.execute.return_value.data = rows
    monkeypatch.setattr(doa, "_get_supabase", lambda: fake_client)
    return fake_client


def test_deletes_storage_object_and_clears_the_path_column(monkeypatch) -> None:
    fake_client = _stub_client(
        monkeypatch,
        [{"id": "old-ticket-1", "image_storage_path": "old-ticket-1/original.png"}],
    )

    doa.delete_old_attachments()

    fake_client.storage.from_.return_value.remove.assert_called_once_with(["old-ticket-1/original.png"])
    fake_client.table.return_value.update.assert_any_call({"image_storage_path": None})


def test_one_failed_deletion_does_not_stop_the_others(monkeypatch) -> None:
    fake_client = _stub_client(
        monkeypatch,
        [
            {"id": "bad-ticket", "image_storage_path": "bad-ticket/original.png"},
            {"id": "good-ticket", "image_storage_path": "good-ticket/original.png"},
        ],
    )
    fake_client.storage.from_.return_value.remove.side_effect = [RuntimeError("storage down"), None]

    doa.delete_old_attachments()  # must not raise

    assert fake_client.storage.from_.return_value.remove.call_count == 2


def test_failed_initial_fetch_does_not_raise_and_processes_nothing(monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.not_.is_.return_value.lt.return_value.execute.side_effect = (
        RuntimeError("network down")
    )
    monkeypatch.setattr(doa, "_get_supabase", lambda: fake_client)

    doa.delete_old_attachments()  # must not raise

    fake_client.storage.from_.return_value.remove.assert_not_called()
    fake_client.table.return_value.update.assert_not_called()
