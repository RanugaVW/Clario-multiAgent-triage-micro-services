"""HTTP-surface smoke tests that do not invoke external model services."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app, TicketRequest, background_orchestration


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_serves_local_ticket_interface() -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Clario Ticket Orchestration" in response.text


@pytest.mark.asyncio
async def test_background_orchestration_uses_the_ocr_cleanup_path_when_it_succeeds():
    ticket = TicketRequest(ticket_id="t1", raw_text="I got this login issue", image_base64="ZmFrZQ==")
    initial_state = {"raw_text": ticket.raw_text, "ticket_id": ticket.ticket_id}

    with patch("app.tools.tesseract_ocr.extract_raw_text", return_value="noisy ocr text") as mock_tess, \
         patch("app.tools.gemini_ocr.extract_error_from_ocr_text", new=AsyncMock(return_value="LoginError: bad credentials")) as mock_cleanup, \
         patch("app.tools.gemini_ocr.extract_error_text", new=AsyncMock(return_value="SHOULD NOT BE CALLED")) as mock_fallback, \
         patch("app.main.graph") as mock_graph, \
         patch("app.main.supabase_client"):
        mock_graph.ainvoke = AsyncMock(return_value={**initial_state, "final_response": None})
        await background_orchestration(ticket, initial_state, start_time=0.0)

    mock_tess.assert_called_once_with("ZmFrZQ==")
    mock_cleanup.assert_awaited_once()
    mock_fallback.assert_not_awaited()
    assert "LoginError: bad credentials" in initial_state["raw_text"]


@pytest.mark.asyncio
async def test_background_orchestration_falls_back_to_direct_image_call_when_cleanup_finds_nothing():
    ticket = TicketRequest(ticket_id="t2", raw_text="I got this login issue", image_base64="ZmFrZQ==")
    initial_state = {"raw_text": ticket.raw_text, "ticket_id": ticket.ticket_id}

    with patch("app.tools.tesseract_ocr.extract_raw_text", return_value=""), \
         patch("app.tools.gemini_ocr.extract_error_from_ocr_text", new=AsyncMock(return_value="")), \
         patch("app.tools.gemini_ocr.extract_error_text", new=AsyncMock(return_value="fallback error text")) as mock_fallback, \
         patch("app.main.graph") as mock_graph, \
         patch("app.main.supabase_client"):
        mock_graph.ainvoke = AsyncMock(return_value={**initial_state, "final_response": None})
        await background_orchestration(ticket, initial_state, start_time=0.0)

    mock_fallback.assert_awaited_once_with("ZmFrZQ==")
    assert "fallback error text" in initial_state["raw_text"]


@pytest.mark.asyncio
async def test_background_orchestration_uploads_the_attachment_and_records_its_path():
    ticket = TicketRequest(ticket_id="t3", raw_text="issue text", image_base64="ZmFrZQ==")
    initial_state = {"raw_text": ticket.raw_text, "ticket_id": ticket.ticket_id}

    with patch("app.tools.tesseract_ocr.extract_raw_text", return_value=""), \
         patch("app.tools.gemini_ocr.extract_error_from_ocr_text", new=AsyncMock(return_value="")), \
         patch("app.tools.gemini_ocr.extract_error_text", new=AsyncMock(return_value="err")), \
         patch("app.main.graph") as mock_graph, \
         patch("app.main.supabase_client") as mock_supabase:
        mock_graph.ainvoke = AsyncMock(return_value={**initial_state, "final_response": None})
        await background_orchestration(ticket, initial_state, start_time=0.0)

    upload_call = mock_supabase.storage.from_.return_value.upload.call_args
    assert upload_call is not None
    uploaded_path = upload_call.args[0]
    assert uploaded_path.startswith("t3/original.")

    update_calls = [c for c in mock_supabase.table.return_value.update.call_args_list
                    if "image_storage_path" in c.args[0]]
    assert len(update_calls) == 1
    assert update_calls[0].args[0]["image_storage_path"] == uploaded_path


@pytest.mark.asyncio
async def test_background_orchestration_leaves_raw_text_untouched_when_neither_ocr_attempt_finds_anything():
    ticket = TicketRequest(ticket_id="t4", raw_text="issue text", image_base64="ZmFrZQ==")
    initial_state = {"raw_text": ticket.raw_text, "ticket_id": ticket.ticket_id}

    with patch("app.tools.tesseract_ocr.extract_raw_text", return_value=""), \
         patch("app.tools.gemini_ocr.extract_error_from_ocr_text", new=AsyncMock(return_value="")), \
         patch("app.tools.gemini_ocr.extract_error_text", new=AsyncMock(return_value="")), \
         patch("app.main.graph") as mock_graph, \
         patch("app.main.supabase_client") as mock_supabase:
        mock_graph.ainvoke = AsyncMock(return_value={**initial_state, "final_response": None})
        await background_orchestration(ticket, initial_state, start_time=0.0)

    assert initial_state["raw_text"] == "issue text"
    assert "[OCR EXTRACTED TEXT FROM ATTACHMENT]" not in initial_state["raw_text"]

    raw_text_update_calls = [
        c for c in mock_supabase.table.return_value.update.call_args_list
        if "raw_text" in c.args[0]
    ]
    assert raw_text_update_calls == []
