"""HTTP-surface tests for the NLP Classifier Service's real API surface.

This service exposes exactly two endpoints (see app/main.py): GET /health
and POST /classify. classify_ticket_local() itself isn't exercised here -
it loads the real ~1B-param Gemma-3 model, the same reason
clario-ml-sidecar's own test suite doesn't call it directly either - so the
success-path test mocks it at the name app.main imported it under.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_classify_returns_the_local_classifiers_result() -> None:
    fake_result = {
        "category": "Login Issue", "priority": "High",
        "sentiment": "Negative", "confidence": 0.85, "source": "gemma3_lora",
    }
    with patch("app.main.classify_ticket_local", return_value=fake_result) as mock_classify:
        response = client.post("/classify", json={"text": "I cannot log in to my account"})

    assert response.status_code == 200
    assert response.json() == fake_result
    mock_classify.assert_called_once_with("I cannot log in to my account")


def test_classify_rejects_empty_text() -> None:
    response = client.post("/classify", json={"text": ""})
    assert response.status_code == 422


def test_classify_surfaces_classifier_failures_as_a_500() -> None:
    with patch("app.main.classify_ticket_local", side_effect=RuntimeError("model unavailable")):
        response = client.post("/classify", json={"text": "Some ticket text"})

    assert response.status_code == 500
    assert "model unavailable" in response.json()["detail"]
