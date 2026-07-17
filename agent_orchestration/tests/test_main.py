"""HTTP-surface smoke tests that do not invoke external model services."""

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_serves_local_ticket_interface() -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Clario Ticket Orchestration" in response.text
