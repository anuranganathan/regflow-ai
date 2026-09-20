"""Pydantic models shared by the API, the agents and the Gemini calls."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

ComplianceStatus = Literal["COMPLIANT", "NON_COMPLIANT", "NEEDS_REVIEW"]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]


# ---------- Document Agent output ----------

class InvoiceData(BaseModel):
    """Fields pulled out of the invoice text. None means 'not found in the document'."""
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_gstin: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_gstin: Optional[str] = None
    place_of_supply: Optional[str] = None
    hsn_codes: list[str] = Field(default_factory=list)
    taxable_value: Optional[float] = None
    gst_rate_percent: Optional[float] = None
    cgst: Optional[float] = None
    sgst: Optional[float] = None
    igst: Optional[float] = None
    total_amount: Optional[float] = None


class ExtractionInfo(BaseModel):
    method: Literal["gemini", "regex"]   # how fields were extracted from the text
    page_count: int
    ocr_pages: list[int] = Field(default_factory=list)  # pages read by Gemini OCR (scanned)
    # identifiers Gemini returned that do not appear in the document text (discarded)
    ungrounded_fields: list[str] = Field(default_factory=list)
    llm_error: Optional[str] = None


# ---------- Deterministic (Python) validation ----------

class ValidationCheck(BaseModel):
    name: str
    passed: bool
    message: str


class ValidationReport(BaseModel):
    gstin_valid: bool
    tax_amount_valid: bool
    missing_fields: list[str]
    checks: list[ValidationCheck]
    expected_tax: Optional[float] = None
    applied_rate_percent: Optional[float] = None

    @property
    def issues(self) -> list[str]:
        return [c.message for c in self.checks if not c.passed]


# ---------- Gemini structured output for the Compliance Agent ----------

class LLMReview(BaseModel):
    """The exact JSON shape Gemini must return (passed as response_schema)."""
    summary: str
    additional_issues: list[str]
    recommendations: list[str]
    sources_cited: list[str]
    needs_human_review: bool


# ---------- Final results ----------

class ComplianceResult(BaseModel):
    status: ComplianceStatus
    confidence: Confidence
    gstin_valid: bool
    tax_amount_valid: bool
    issues: list[str]
    recommendations: list[str]
    explanation: str
    sources_used: list[str]
    requires_human_review: bool
    review_reasons: list[str]
    llm_used: bool
    checks: list[ValidationCheck]


SupplyDirection = Literal["OUTWARD", "INWARD", "UNKNOWN"]


class FilingSummary(BaseModel):
    """GSTR-3B figures. Sales go to Table 3.1(a); purchases go to Table 4 (input tax credit)."""
    return_type: str = "GSTR-3B"
    direction: SupplyDirection
    table: str
    invoice_count: int
    total_taxable_value: float
    total_igst: float
    total_cgst: float
    total_sgst: float
    total_tax: float
    ready_to_file: bool
    note: str


class AnalysisResult(BaseModel):
    invoice: InvoiceData
    extraction: ExtractionInfo
    compliance: ComplianceResult
    filing_summary: FilingSummary
    extracted_text: str


# ---------- API records ----------

DocumentStatus = Literal["UPLOADED", "ANALYZED", "FAILED"]


class DocumentRecord(BaseModel):
    document_id: str
    filename: str
    object_key: str
    storage_mode: Literal["local", "s3"]
    status: DocumentStatus
    uploaded_at: str
    analyzed_at: Optional[str] = None
    error: Optional[str] = None


class UploadResponse(BaseModel):
    document: DocumentRecord
    result: AnalysisResult
