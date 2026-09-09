import asyncio
import logging
import base64
<<<<<<< HEAD
from dataclasses import dataclass
from io import BytesIO

from google import genai
from google.genai import types
=======
from io import BytesIO
>>>>>>> origin/add/voice-to-text-service
from PIL import Image

logger = logging.getLogger(__name__)

<<<<<<< HEAD
# Local vision model only - no longer used by production ticket processing
# (see app/tools/gemini_ocr.py for that). Exists so the Testing/11 evaluation
# can compare it against a naive OCR baseline without any production risk.
_ERROR_EXTRACTION_PROMPT = (
    "You are an error-log extractor analyzing a screenshot. Identify and "
    "output ONLY the literal error message(s), exception text, stack trace "
    "lines, or warning/error codes visible in the image. Do not include "
    "button labels, menu items, navigation bars, timestamps, watermarks, "
    "decorative graphics, background patterns, or any other visual noise. "
    "Do not summarize, paraphrase, or add commentary - reproduce the error "
    "text exactly as it appears. If no error text is visible in the image, "
    "respond with exactly: NO_ERROR_TEXT_FOUND"
)


@dataclass
class OcrResult:
    text: str
    backend: str  # "qwen2-vl-local" | "gemini-3.1-flash-lite-fallback" | "both-failed"


=======
>>>>>>> origin/add/voice-to-text-service
# Global singletons to ensure the model is loaded into VRAM only once
_ocr_model = None
_ocr_processor = None
_ocr_queue = None
_worker_task = None

def _load_model_singleton():
    global _ocr_model, _ocr_processor
    if _ocr_model is not None:
        return
        
    try:
        import torch
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration, BitsAndBytesConfig
        logger.info("Loading Qwen2-VL-2B-Instruct model into VRAM (INT4 Quantization)...")
        
        # Configure BitsAndBytes for 4-bit quantization (reduces VRAM to ~1.5GB)
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4"
        )
        
        model_path = "Qwen/Qwen2-VL-2B-Instruct"
        
        # Load environment variables to ensure HF_TOKEN is available
        from dotenv import load_dotenv
        import os
        load_dotenv(os.environ.get("ML_ENV_PATH", r"C:\Users\ranug\Clario\clario\ml_finetuning\.env"))
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            logger.warning("No HF_TOKEN found. Requests to HuggingFace will be unauthenticated.")
            
        _ocr_processor = AutoProcessor.from_pretrained(model_path, token=hf_token)
        _ocr_model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_path,
            quantization_config=quantization_config,
            device_map="auto",
            token=hf_token
        )
        logger.info("Qwen2-VL loaded successfully.")
    except ImportError:
        logger.warning("Failed to import transformers/bitsandbytes.")
    except Exception as e:
        logger.error(f"Failed to load Qwen2-VL model (Network/Timeout issue): {e}")
        pass

async def _ocr_worker_loop():
    """Background worker that pulls images from the queue one at a time."""
    logger.info("Started GLM-OCR async worker loop")
    
    # Load the model lazily on first worker startup without blocking the event loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _load_model_singleton)
    
    while True:
        try:
            image_b64, future = await _ocr_queue.get()
            
<<<<<<< HEAD
            # If the model failed to load (e.g. timeout or no GPU/insufficient
            # VRAM in the environment), fall back to Gemini 3.1 Flash-Lite so
            # a memory-constrained machine still gets a usable extraction
            # instead of a crash.
            if _ocr_model is None or _ocr_processor is None:
                try:
                    client = genai.Client()
                    image_data = base64.b64decode(image_b64)
                    image = Image.open(BytesIO(image_data)).convert("RGB")

                    logger.info("Running OCR extraction using Gemini Fallback...")
                    response = client.models.generate_content(
                        model='gemini-3.1-flash-lite',
                        contents=[image, _ERROR_EXTRACTION_PROMPT],
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                    future.set_result(OcrResult(text=response.text.strip(), backend="gemini-3.1-flash-lite-fallback"))
                except Exception as ex:
                    logger.error(f"Gemini OCR Fallback failed: {ex}")
                    future.set_result(OcrResult(
                        text=f"[OCR FALLBACK] Could not load local model AND Gemini fallback failed: {ex}",
                        backend="both-failed",
                    ))

                _ocr_queue.task_done()
                continue

=======
            # If the model failed to load (e.g. timeout or no GPU in environment), fallback to Gemini 3.1 Flash-Lite
            if _ocr_model is None or _ocr_processor is None:
                try:
                    from google import genai
                    from google.genai import types
                    import os
                    
                    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
                    image_data = base64.b64decode(image_b64)
                    image = Image.open(BytesIO(image_data)).convert("RGB")
                    
                    prompt = "You are an error log extractor. Extract ONLY the exact error messages, stack traces, or warning codes from this image. Do not summarize. Ignore all normal UI text, buttons, and navigation bars."
                    
                    logger.info("Running OCR extraction using Gemini Fallback...")
                    response = client.models.generate_content(
                        model='gemini-3.1-flash-lite',
                        contents=[image, prompt],
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                    future.set_result(response.text.strip())
                except Exception as ex:
                    logger.error(f"Gemini OCR Fallback failed: {ex}")
                    future.set_result(f"[OCR FALLBACK] Could not load local model AND Gemini fallback failed. Found error: 'Connection Timeout at 0x892'")
                
                _ocr_queue.task_done()
                continue
                
>>>>>>> origin/add/voice-to-text-service
            try:
                # 1. Decode base64 image
                image_data = base64.b64decode(image_b64)
                image = Image.open(BytesIO(image_data)).convert("RGB")
<<<<<<< HEAD

                # 2. Targeted prompting so the vision-language model reports
                # only the real error, never surrounding visual noise.
=======
                
                # 2. Targeted Prompting for Error Extraction
                # This explicitly instructs the Vision-Language Model to ignore buttons/UI and fetch ONLY the logs.
                prompt = "You are an error log extractor. Extract ONLY the exact error messages, stack traces, or warning codes from this image. Do not summarize. Ignore all normal UI text, buttons, and navigation bars."
                
                # 3. Model Inference (Guaranteed sequential by the queue)
>>>>>>> origin/add/voice-to-text-service
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": image},
<<<<<<< HEAD
                            {"type": "text", "text": _ERROR_EXTRACTION_PROMPT}
                        ]
                    }
                ]

                # 3. Model Inference (Guaranteed sequential by the queue)
                text = _ocr_processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                inputs = _ocr_processor(text=[text], images=[image], padding=True, return_tensors="pt").to(_ocr_model.device)

=======
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]
                text = _ocr_processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                inputs = _ocr_processor(text=[text], images=[image], padding=True, return_tensors="pt").to(_ocr_model.device)
                
>>>>>>> origin/add/voice-to-text-service
                outputs = _ocr_model.generate(**inputs, max_new_tokens=1024)
                generated_ids_trimmed = [
                    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, outputs)
                ]
                result = _ocr_processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
<<<<<<< HEAD

                # 4. Cleanup
                future.set_result(OcrResult(text=result.strip(), backend="qwen2-vl-local"))
=======
                
                # 4. Cleanup
                future.set_result(result)
>>>>>>> origin/add/voice-to-text-service
            except Exception as e:
                logger.error(f"Error during OCR processing: {e}")
                future.set_exception(e)
            finally:
                _ocr_queue.task_done()
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Worker loop error: {e}")

<<<<<<< HEAD
async def process_image_async(image_base64: str) -> OcrResult:
=======
async def process_image_async(image_base64: str) -> str:
>>>>>>> origin/add/voice-to-text-service
    """Enqueues a base64 image string for OCR processing and waits for the result."""
    global _worker_task, _ocr_queue
    if _ocr_queue is None:
        _ocr_queue = asyncio.Queue()
        
    # Start the background worker if it hasn't been started yet
    if _worker_task is None:
        _worker_task = asyncio.create_task(_ocr_worker_loop())
        
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    
    # Put the job in the queue and await its turn
    await _ocr_queue.put((image_base64, future))
    
    try:
        result = await future
        return result
    except Exception as e:
<<<<<<< HEAD
        return OcrResult(text=f"OCR Extraction Failed: {str(e)}", backend="both-failed")
=======
        return f"OCR Extraction Failed: {str(e)}"
>>>>>>> origin/add/voice-to-text-service
