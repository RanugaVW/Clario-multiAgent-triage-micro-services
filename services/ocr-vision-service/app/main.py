"""FastAPI interface for OCR Vision Service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.tools.local_ocr import _load_model_singleton as load_ocr, process_image_async

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    import threading
    def preload():
        try:
            logger.info("Preloading Qwen2-VL Model...")
            load_ocr()
            logger.info("Qwen2-VL Preloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to preload model: {e}")
    threading.Thread(target=preload, daemon=True).start()
    yield

app = FastAPI(title="OCR Vision Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class OCRRequest(BaseModel):
    image_base64: str

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/ocr")
async def extract_ocr(request: OCRRequest):
    try:
        text = await process_image_async(request.image_base64)
        return {"text": text}
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

