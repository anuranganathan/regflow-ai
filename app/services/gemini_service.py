"""All calls to the Gemini API go through this module.

Any failure (missing key, network error, quota/429, bad JSON) is raised as
GeminiError so callers can fall back to Python-only processing.
"""
import logging
from functools import lru_cache
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import get_settings
from app.errors import GeminiError

logger = logging.getLogger("regflow.gemini")
T = TypeVar("T", bound=BaseModel)


def _short(exc: Exception) -> str:
    """Keep error messages readable in results and logs."""
    return f"{type(exc).__name__}: {str(exc)[:150]}"


@lru_cache
def _client() -> genai.Client:
    settings = get_settings()
    if not settings.gemini_enabled:
        raise GeminiError("GEMINI_API_KEY is not configured.")
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=60_000),  # milliseconds
    )


def generate_structured(prompt: str, schema: type[T]) -> T:
    """Ask Gemini for JSON that matches a Pydantic model (structured output)."""
    try:
        response = _client().models.generate_content(
            model=get_settings().gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
    except GeminiError:
        raise
    except Exception as exc:
        logger.warning("Gemini request failed: %s", _short(exc))
        raise GeminiError(f"Gemini request failed ({_short(exc)})") from exc

    if isinstance(response.parsed, schema):
        return response.parsed
    try:
        return schema.model_validate_json(response.text or "")
    except Exception as exc:
        raise GeminiError(f"Gemini returned output that does not match {schema.__name__}.") from exc


def ocr_image(png_bytes: bytes) -> str:
    """Transcribe the text of a scanned page image."""
    try:
        response = _client().models.generate_content(
            model=get_settings().gemini_model,
            contents=[
                types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
                "Transcribe all text on this invoice page exactly as printed. "
                "Return only the text. If a value is unreadable write [unreadable]; never guess.",
            ],
            config=types.GenerateContentConfig(temperature=0),
        )
    except GeminiError:
        raise
    except Exception as exc:
        logger.warning("Gemini OCR failed: %s", _short(exc))
        raise GeminiError(f"Gemini OCR failed ({_short(exc)})") from exc
    return (response.text or "").strip()
