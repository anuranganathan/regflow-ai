"""Document Agent: PDF -> text -> structured invoice fields.

1. PyMuPDF extracts and cleans the text (Gemini OCR only for scanned pages).
2. Gemini reads the text and returns the invoice fields as structured JSON.
3. If Gemini is unavailable, simple regular expressions extract what they can.
Missing values stay None; nothing is guessed.
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.config import get_settings
from app.errors import GeminiError
from app.models.schemas import ExtractionInfo, InvoiceData
from app.services import document_service, gemini_service

logger = logging.getLogger("regflow.document_agent")

MAX_PROMPT_CHARS = 15_000

EXTRACTION_PROMPT = """You extract fields from Indian GST invoices.

Rules:
- Copy values exactly as they appear in the invoice text. Do not calculate, correct or infer values.
- Use null for any field that is not present in the text.
- Amounts are plain numbers without currency symbols or commas.
- gst_rate_percent is the total GST rate (e.g. 18 for CGST 9% + SGST 9%) only if printed on the invoice.
- supplier_* is the seller issuing the invoice; recipient_* is the buyer.

INVOICE TEXT:
{text}
"""


@dataclass
class DocumentAgentOutput:
    invoice: InvoiceData
    extraction: ExtractionInfo
    text: str


def run_document_agent(pdf_bytes: bytes) -> DocumentAgentOutput:
    extracted = document_service.extract_text(pdf_bytes)
    text = extracted.text

    llm_error: Optional[str] = None
    ungrounded: list[str] = []
    if get_settings().gemini_enabled:
        try:
            invoice = gemini_service.generate_structured(
                EXTRACTION_PROMPT.format(text=text[:MAX_PROMPT_CHARS]), InvoiceData
            )
            method = "gemini"
            ungrounded = _drop_ungrounded_identifiers(invoice, text)
        except GeminiError as exc:
            logger.warning("Gemini extraction failed, using regex fallback: %s", exc)
            invoice, method, llm_error = regex_extract(text), "regex", str(exc)
    else:
        invoice, method, llm_error = regex_extract(text), "regex", "GEMINI_API_KEY is not configured."

    return DocumentAgentOutput(
        invoice=invoice,
        extraction=ExtractionInfo(
            method=method,
            page_count=extracted.page_count,
            ocr_pages=extracted.ocr_pages,
            ungrounded_fields=ungrounded,
            llm_error=llm_error,
        ),
        text=text,
    )


def _drop_ungrounded_identifiers(invoice: InvoiceData, text: str) -> list[str]:
    """Hallucination guard: identifiers the LLM returns must literally exist in the document."""
    compact_text = re.sub(r"\s+", "", text).upper()
    dropped = []
    for field in ("invoice_number", "supplier_gstin", "recipient_gstin"):
        value = getattr(invoice, field)
        if value and re.sub(r"\s+", "", value).upper() not in compact_text:
            logger.warning("Discarding %s=%r: not found in document text", field, value)
            setattr(invoice, field, None)
            dropped.append(field)
    return dropped


# ---------- regex fallback (used only when Gemini is unavailable) ----------

_NUMBER = r"(?:₹|Rs\.?|INR)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)"


def _find(pattern: str, text: str) -> Optional[str]:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _amount(label: str, text: str) -> Optional[float]:
    # handles "CGST: 900", "CGST @ 9%: 900" and "CGST (9%) Rs. 900.00"
    value = _find(rf"{label}\s*\(?@?\s*(?:[0-9.]+\s*%)?\)?\s*[:\-]?\s*{_NUMBER}", text)
    return float(value.replace(",", "")) if value else None


def regex_extract(text: str) -> InvoiceData:
    gstins = re.findall(r"GSTIN(?:/UIN)?\s*[:\-]?\s*([0-9A-Z]{10,20})", text, re.IGNORECASE)
    rate = _find(r"(?:GST\s*)?Rate\s*[:\-]?\s*([0-9.]+)\s*%", text)
    return InvoiceData(
        invoice_number=_find(r"Invoice\s*(?:Number|No\.?|#)\s*[:\-]?\s*([A-Za-z0-9\-/]+)", text),
        invoice_date=_find(r"(?:Invoice\s*)?Date\s*[:\-]?\s*([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})", text),
        supplier_name=_find(r"(?:Supplier|Seller)(?:\s*Name)?\s*[:\-]\s*([^\n]+)", text),
        supplier_gstin=gstins[0].upper() if gstins else None,
        recipient_name=_find(r"(?:Recipient|Buyer|Bill\s*To)(?:\s*Name)?\s*[:\-]\s*([^\n]+)", text),
        recipient_gstin=gstins[1].upper() if len(gstins) > 1 else None,
        place_of_supply=_find(r"Place\s*of\s*Supply\s*[:\-]\s*([^\n]+)", text),
        hsn_codes=re.findall(r"(?:HSN|SAC)(?:/SAC)?(?:\s*Code)?\s*[:\-]?\s*([0-9]{4,8})", text, re.IGNORECASE),
        taxable_value=_amount(r"Taxable\s*(?:Value|Amount)", text),
        gst_rate_percent=float(rate) if rate else None,
        cgst=_amount("CGST", text),
        sgst=_amount(r"(?:SGST|UTGST)", text),
        igst=_amount("IGST", text),
        total_amount=_amount(r"(?:Grand\s*)?Total\s*(?:Invoice\s*)?(?:Amount|Value)", text),
    )
