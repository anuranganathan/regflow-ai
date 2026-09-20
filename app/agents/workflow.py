"""The agent workflow: Document Agent -> Compliance Agent -> Filing Summary Agent.

Each agent has one job and passes its output to the next. The order is fixed in
code, so every document goes through the same, predictable steps.
"""
import logging

from app.agents.compliance_agent import run_compliance_agent
from app.agents.document_agent import run_document_agent
from app.agents.filing_agent import run_filing_agent
from app.config import get_settings
from app.models.schemas import AnalysisResult
from app.services.compliance_service import detect_direction

logger = logging.getLogger("regflow.workflow")

MAX_TEXT_IN_RESULT = 5_000


def analyze_pdf(pdf_bytes: bytes) -> AnalysisResult:
    business_gstin = get_settings().business_gstin

    document = run_document_agent(pdf_bytes)
    logger.info("Document Agent: extracted fields with %s", document.extraction.method)

    # Sale or purchase? Decided in Python from our own GSTIN, before the LLM is involved.
    direction = detect_direction(document.invoice, business_gstin)

    compliance = run_compliance_agent(document, direction)
    logger.info("Compliance Agent: %s (%s confidence, %s invoice)",
                compliance.status, compliance.confidence, direction)

    filing = run_filing_agent(document.invoice, compliance, direction, bool(business_gstin))

    return AnalysisResult(
        invoice=document.invoice,
        extraction=document.extraction,
        compliance=compliance,
        filing_summary=filing,
        extracted_text=document.text[:MAX_TEXT_IN_RESULT],
    )
