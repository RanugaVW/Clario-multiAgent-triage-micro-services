import base64
import logging
import os
from io import BytesIO

from PIL import Image

logger = logging.getLogger(__name__)

_PROMPT = (
    "You are an error log extractor. Extract ONLY the exact error messages, "
    "stack traces, or warning codes from this image. Do not summarize. Ignore "
    "all normal UI text, buttons, and navigation bars."
)


async def process_image_async(image_base64: str) -> str:
    """Extracts error-log text from a base64-encoded image via the Gemini API.

    No GPU is available in this deployment, so there is no local vision model
    to try first - Gemini is called directly instead of through a fallback path.
    """
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        image_data = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_data)).convert("RGB")

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[image, _PROMPT],
            config=types.GenerateContentConfig(temperature=0.0),
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini OCR extraction failed: {e}")
        return f"OCR Extraction Failed: {str(e)}"
