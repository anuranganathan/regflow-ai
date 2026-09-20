"""The agent workflow: Document Agent -> Compliance Agent -> Filing Summary Agent.

Each agent has one job and passes its output to the next. The order is fixed in
code, so every document goes through the same, predictable steps.
"""
import logging

from app.agents.compliance_agent import run_compliance_agent
from app.agents.document_agent import run_document_agent
from app.agents.filing_agent import run_filing_agent
from app.models.schemas import AnalysisResult

logger = logging.getLogger("regflow.workflow")

MAX_TEXT_IN_RESULT = 5_000


def analyze_pdf(pdf_bytes: bytes) -> AnalysisResult:
    document = run_document_agent(pdf_bytes)
    logger.info("Document Agent: extracted fields with %s", document.extraction.method)

    compliance = run_compliance_agent(document)
    logger.info("Compliance Agent: %s (%s confidence)", compliance.status, compliance.confidence)

    filing = run_filing_agent(document.invoice, compliance)

    return AnalysisResult(
        invoice=document.invoice,
        extraction=document.extraction,
        compliance=compliance,
        filing_summary=filing,
        extracted_text=document.text[:MAX_TEXT_IN_RESULT],
    )
