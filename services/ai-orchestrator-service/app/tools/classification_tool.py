"""Ticket classifier — makes REST call to NLP Classifier Microservice."""

from __future__ import annotations

import logging
import os
import httpx
from typing import Any

logger = logging.getLogger(__name__)

async def classify_ticket(redacted_text: str) -> dict[str, Any]:
    """Classify a redacted ticket; returns category, priority, sentiment, confidence, source."""
    classifier_url = os.environ.get("CLASSIFIER_URL", "http://nlp-classifier-service:8000")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{classifier_url}/classify", 
                json={"text": redacted_text},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(
                "Classification: category=%s priority=%s sentiment=%s confidence=%.2f source=%s",
                result.get("category"), result.get("priority"), result.get("sentiment"),
                result.get("confidence", 0.0), result.get("source")
            )
            return result
    except Exception as e:
        logger.error(f"Failed to reach NLP Classifier Service: {e}")
        return {
            "category": "General",
            "priority": "Medium",
            "sentiment": "Neutral",
            "confidence": 0.0,
            "source": "api_error_fallback"
        }
