"""PDF validation and text extraction with PyMuPDF.

Digital PDFs have a text layer, so PyMuPDF reads the text directly. Pages with
almost no text are probably scans; those are sent to Gemini for OCR if a key is set.
"""
import logging
import re
from dataclasses import dataclass, field

import fitz  # PyMuPDF

from app.config import get_settings
from app.errors import DocumentExtractionError, GeminiError, InvalidDocumentError
from app.services import gemini_service

logger = logging.getLogger("regflow.document")

MIN_TEXT_CHARS_PER_PAGE = 20  # fewer characters than this = treat the page as scanned


@dataclass
class ExtractedText:
    text: str
    page_count: int
    ocr_pages: list[int] = field(default_factory=list)


def validate_pdf(filename: str, data: bytes) -> None:
    """Reject anything that is not a small, readable, unencrypted PDF."""
    max_mb = get_settings().max_upload_mb
    if not filename.lower().endswith(".pdf"):
        raise InvalidDocumentError("Only PDF files are accepted.")
    if not data:
        raise InvalidDocumentError("The uploaded file is empty.")
    if len(data) > max_mb * 1024 * 1024:
        raise InvalidDocumentError(f"The file is larger than {max_mb} MB.")
    if not data.startswith(b"%PDF-"):
        raise InvalidDocumentError("The file is not a valid PDF.")
    with _open_pdf(data) as doc:
        if doc.needs_pass:
            raise InvalidDocumentError("Password-protected PDFs are not supported.")
        if doc.page_count == 0:
            raise InvalidDocumentError("The PDF has no pages.")


def _open_pdf(data: bytes) -> fitz.Document:
    try:
        return fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise InvalidDocumentError(f"The PDF could not be opened: {exc}") from exc


def clean_text(text: str) -> str:
    """Normalise whitespace so the text is easier to search and cheaper to send to Gemini."""
    text = text.replace("\r", "\n").replace(" ", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_text(data: bytes) -> ExtractedText:
    pages_text: list[str] = []
    ocr_pages: list[int] = []

    with _open_pdf(data) as doc:
        page_count = doc.page_count
        for number, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if len(text) < MIN_TEXT_CHARS_PER_PAGE:
                text = _ocr_page(page, number)
                if text:
                    ocr_pages.append(number)
            pages_text.append(text)

    cleaned = clean_text("\n\n".join(pages_text))
    if not cleaned:
        hint = ("Gemini OCR could not read the scanned pages; try again later."
                if get_settings().gemini_enabled
                else "If it is a scanned document, set GEMINI_API_KEY so scanned pages can be read with OCR.")
        raise DocumentExtractionError(f"No readable text was found in the PDF. {hint}")
    return ExtractedText(text=cleaned, page_count=page_count, ocr_pages=ocr_pages)


def _ocr_page(page: fitz.Page, number: int) -> str:
    if not get_settings().gemini_enabled:
        logger.info("Page %d looks scanned but OCR is unavailable (no Gemini key).", number)
        return ""
    try:
        png = page.get_pixmap(dpi=150).tobytes("png")
        logger.info("Page %d looks scanned; running Gemini OCR.", number)
        return gemini_service.ocr_image(png)
    except GeminiError as exc:
        logger.warning("OCR failed on page %d: %s", number, exc)
        return ""
