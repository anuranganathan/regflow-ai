"""API tests. AWS S3 and Gemini are replaced with mocks, so no network is used."""
import io
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from app.agents.document_agent import regex_extract
from app.config import get_settings
from app.errors import GeminiError
from app.models.schemas import InvoiceData, LLMReview
from app.services import gemini_service, s3_service
from tests.helpers import COMPLIANT_INVOICE, WRONG_TAX_INVOICE, make_pdf


def upload(client, text=COMPLIANT_INVOICE, filename="invoice.pdf"):
    return client.post("/documents/upload", files={"file": (filename, make_pdf(text), "application/pdf")})


def fake_gemini(invoice: InvoiceData, review: LLMReview):
    """Stand-in for gemini_service.generate_structured: returns a fixed answer per schema."""
    def generate_structured(prompt, schema):
        return invoice.model_copy() if schema is InvoiceData else review
    return generate_structured


GOOD_REVIEW = LLMReview(
    summary="The invoice contains the mandatory fields and the tax is correct.",
    additional_issues=[], recommendations=[],
    sources_cited=["gst_invoice_rules.txt", "gst_rates.txt"], needs_human_review=False,
)


# ---------- local storage mode ----------

def test_upload_stores_pdf_and_returns_result(client, local_settings):
    response = upload(client)
    assert response.status_code == 201
    body = response.json()

    doc = body["document"]
    assert doc["status"] == "ANALYZED" and doc["storage_mode"] == "local"
    assert doc["object_key"] == f"documents/{doc['document_id']}/invoice.pdf"
    assert (local_settings / "uploads" / doc["object_key"]).exists()

    # Gemini is off in tests: Python checks pass, but a person must review
    result = body["result"]
    assert result["extraction"]["method"] == "regex"
    assert result["compliance"]["gstin_valid"] and result["compliance"]["tax_amount_valid"]
    assert result["compliance"]["status"] == "NEEDS_REVIEW"
    assert result["compliance"]["requires_human_review"] is True
    assert result["filing_summary"]["total_tax"] == 1800


def test_get_endpoints_and_reanalyze(client):
    document_id = upload(client).json()["document"]["document_id"]

    assert client.get(f"/documents/{document_id}").json()["status"] == "ANALYZED"
    assert client.get(f"/documents/{document_id}/result").status_code == 200
    reanalyzed = client.post(f"/documents/{document_id}/analyze")
    assert reanalyzed.status_code == 200
    assert reanalyzed.json()["invoice"]["invoice_number"] == "INV-2025-001"


def test_wrong_tax_is_non_compliant(client):
    compliance = upload(client, WRONG_TAX_INVOICE).json()["result"]["compliance"]
    assert compliance["status"] == "NON_COMPLIANT"
    assert not compliance["tax_amount_valid"]


def test_invalid_upload_returns_400(client):
    response = client.post("/documents/upload", files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert response.status_code == 400
    assert "not a valid PDF" in response.json()["detail"]


def test_scanned_pdf_without_ocr_returns_422(client):
    assert upload(client, text="").status_code == 422


def test_unknown_document_returns_404(client):
    assert client.get("/documents/" + "0" * 32).status_code == 404
    assert client.get("/documents/not-an-id").status_code == 422   # rejected by the path pattern


# ---------- S3 storage mode (boto3 mocked) ----------

def use_s3(monkeypatch):
    monkeypatch.setenv("STORAGE_MODE", "s3")
    monkeypatch.setenv("S3_BUCKET_NAME", "test-bucket")
    get_settings.cache_clear()  # settings were cached when the app started
    s3_client = MagicMock()
    monkeypatch.setattr(s3_service, "get_s3_client", lambda: s3_client)
    return s3_client


def test_upload_goes_to_s3(client, monkeypatch):
    s3_client = use_s3(monkeypatch)
    response = upload(client)
    assert response.status_code == 201

    key = response.json()["document"]["object_key"]
    s3_client.put_object.assert_called_once()
    assert s3_client.put_object.call_args.kwargs["Bucket"] == "test-bucket"
    assert s3_client.put_object.call_args.kwargs["Key"] == key

    # re-analysis downloads the PDF back from S3
    s3_client.get_object.return_value = {"Body": io.BytesIO(make_pdf(COMPLIANT_INVOICE))}
    document_id = response.json()["document"]["document_id"]
    assert client.post(f"/documents/{document_id}/analyze").status_code == 200
    s3_client.get_object.assert_called_once_with(Bucket="test-bucket", Key=key)


def test_s3_failure_returns_502(client, monkeypatch):
    s3_client = use_s3(monkeypatch)
    s3_client.put_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject"
    )
    response = upload(client)
    assert response.status_code == 502
    assert "S3" in response.json()["detail"]


# ---------- Gemini (mocked) ----------

def enable_gemini(monkeypatch, fake):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    monkeypatch.setattr(gemini_service, "generate_structured", fake)


def test_compliant_with_gemini_and_rag(client, monkeypatch):
    enable_gemini(monkeypatch, fake_gemini(regex_extract(COMPLIANT_INVOICE), GOOD_REVIEW))

    compliance = upload(client).json()["result"]["compliance"]
    assert compliance["status"] == "COMPLIANT"
    assert compliance["confidence"] == "HIGH"
    assert compliance["requires_human_review"] is False
    assert compliance["llm_used"] is True
    assert compliance["sources_used"] == ["gst_invoice_rules.txt", "gst_rates.txt"]


def test_llm_cannot_override_python_checks(client, monkeypatch):
    # Gemini says "all good" about an invoice whose tax is wrong
    enable_gemini(monkeypatch, fake_gemini(regex_extract(WRONG_TAX_INVOICE), GOOD_REVIEW))

    compliance = upload(client, WRONG_TAX_INVOICE).json()["result"]["compliance"]
    assert compliance["status"] == "NON_COMPLIANT"


def test_hallucinated_gstin_is_discarded(client, monkeypatch):
    invented = regex_extract(COMPLIANT_INVOICE).model_copy(update={"supplier_gstin": "27ZZZZZ9999Z1Z9"})
    enable_gemini(monkeypatch, fake_gemini(invented, GOOD_REVIEW))

    result = upload(client).json()["result"]
    assert result["invoice"]["supplier_gstin"] is None
    assert result["extraction"]["ungrounded_fields"] == ["supplier_gstin"]
    assert result["compliance"]["status"] == "NEEDS_REVIEW"
    assert result["compliance"]["requires_human_review"] is True


def test_gemini_failure_falls_back_to_python(client, monkeypatch):
    def broken(prompt, schema):
        raise GeminiError("429 quota exceeded")
    enable_gemini(monkeypatch, broken)

    response = upload(client)
    assert response.status_code == 201                      # the request still succeeds
    result = response.json()["result"]
    assert result["extraction"]["method"] == "regex"
    assert result["compliance"]["llm_used"] is False
    assert result["compliance"]["requires_human_review"] is True
