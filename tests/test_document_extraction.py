import pytest

from app.agents.document_agent import regex_extract
from app.errors import DocumentExtractionError, InvalidDocumentError
from app.services.document_service import clean_text, extract_text, validate_pdf
from tests.helpers import COMPLIANT_INVOICE, make_pdf


def test_text_is_extracted_from_digital_pdf():
    result = extract_text(make_pdf(COMPLIANT_INVOICE))
    assert result.page_count == 1
    assert result.ocr_pages == []
    assert "INV-2025-001" in result.text
    assert "29ABCDE1234F1ZW" in result.text


def test_scanned_pdf_without_ocr_raises_clear_error():
    # blank page = no text layer, and Gemini (OCR) is disabled in tests
    with pytest.raises(DocumentExtractionError):
        extract_text(make_pdf(""))


@pytest.mark.parametrize("filename, data", [
    ("invoice.txt", make_pdf("x" * 50)),       # wrong extension
    ("invoice.pdf", b""),                        # empty
    ("invoice.pdf", b"hello, not a pdf"),        # not a PDF
    ("invoice.pdf", b"%PDF-1.7 broken"),         # PDF header but corrupt
])
def test_invalid_uploads_are_rejected(filename, data):
    with pytest.raises(InvalidDocumentError):
        validate_pdf(filename, data)


def test_clean_text_normalises_whitespace():
    assert clean_text("  GSTIN:\t 29ABC  \r\n\n\n\nTotal:   100  ") == "GSTIN: 29ABC\nTotal: 100"


def test_regex_fallback_extracts_fields_without_guessing():
    invoice = regex_extract(COMPLIANT_INVOICE)
    assert invoice.invoice_number == "INV-2025-001"
    assert invoice.supplier_gstin == "29ABCDE1234F1ZW"
    assert invoice.recipient_gstin == "29PQRSX5678K1ZU"
    assert (invoice.taxable_value, invoice.cgst, invoice.sgst, invoice.total_amount) == (10000, 900, 900, 11800)
    assert invoice.gst_rate_percent == 18
    assert invoice.igst is None                     # not on the invoice -> None, not a default

    empty = regex_extract("nothing useful here")
    assert empty.supplier_gstin is None and empty.taxable_value is None
