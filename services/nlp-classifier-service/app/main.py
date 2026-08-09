"""FastAPI interface for NLP Classification Service."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.tools.local_llm import _load_model as load_llm, classify_ticket_local

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    import threading
    def preload():
        try:
            logger.info("Preloading Gemma-3 Model...")
            load_llm()
            logger.info("Gemma-3 Preloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to preload model: {e}")
    threading.Thread(target=preload, daemon=True).start()
    yield

app = FastAPI(title="NLP Classifier Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/classify")
async def classify(request: ClassifyRequest):
    try:
        import asyncio
        result = await asyncio.get_event_loop().run_in_executor(
            None, classify_ticket_local, request.text
        )
        return result
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

