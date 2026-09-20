"""Compliance Agent: invoice fields + GST rules -> compliance result.

Steps:
1. Python validation (GSTIN format, required fields, tax arithmetic) - authoritative.
2. RAG: retrieve the GST rule paragraphs relevant to this invoice.
3. Gemini reviews the invoice against ONLY those rules and explains the result.
4. Reliability layer merges the three and decides status, confidence and
   whether a human must review it.

Decision rules (the LLM never overrides Python):
- Any failed Python check        -> NON_COMPLIANT
- Required fields missing        -> NEEDS_REVIEW (could be an extraction miss)
- Python passes, Gemini flags a rule issue -> NEEDS_REVIEW (the LLM can raise a flag, not fail it)
- Everything passes              -> COMPLIANT
"""
import json
import logging

from app.agents.document_agent import DocumentAgentOutput
from app.config import get_settings
from app.errors import GeminiError
from app.models.schemas import ComplianceResult, LLMReview, ValidationReport
from app.rag.retriever import RuleChunk, get_retriever
from app.services import compliance_service, gemini_service

logger = logging.getLogger("regflow.compliance_agent")

REVIEW_PROMPT = """You are a GST compliance reviewer for Indian tax invoices.

Use ONLY the GST RULES below. If the rules do not cover something, do not invent a rule;
set needs_human_review to true instead.

The PYTHON CHECKS were computed by code and are correct. Do not recompute the tax,
do not contradict these checks, and do not repeat them as additional issues.

Your tasks:
1. summary: 2-3 sentences explaining the compliance result in plain English.
2. additional_issues: problems visible in the INVOICE TEXT that the Python checks do not
   cover and that break one of the GST RULES (e.g. a mandatory invoice field that is absent).
   Cite the rule file in brackets, e.g. "HSN code missing [gst_invoice_rules.txt]".
   Return an empty list if there are none.
3. recommendations: concrete next steps for the business (empty list if none).
4. sources_cited: the rule file names you actually relied on.
5. needs_human_review: true if you are unsure about anything.

GST RULES:
{rules}

EXTRACTED INVOICE FIELDS:
{invoice}

PYTHON CHECKS:
{checks}

INVOICE TEXT:
{text}
"""


def build_query(output: DocumentAgentOutput, report: ValidationReport) -> str:
    """Turn the invoice into a keyword query for the retriever."""
    inv = output.invoice
    terms = ["tax invoice mandatory fields gstin rate calculating tax gstr-3b outward supplies"]
    terms.append("igst inter-state" if inv.igst else "cgst sgst intra-state split")
    if not inv.hsn_codes:
        terms.append("hsn code")
    if not inv.place_of_supply:
        terms.append("place of supply")
    terms.extend(check.message for check in report.checks if not check.passed)
    return " ".join(terms)


def run_compliance_agent(output: DocumentAgentOutput) -> ComplianceResult:
    # 1. Deterministic validation
    report = compliance_service.validate_invoice(output.invoice)

    # 2. Retrieval
    rules = get_retriever().retrieve(build_query(output, report), top_k=5)

    # 3. LLM review (optional - the system still works without it)
    review, llm_error = None, None
    if not get_settings().gemini_enabled:
        llm_error = "GEMINI_API_KEY is not configured."
    elif rules:
        try:
            review = gemini_service.generate_structured(_build_prompt(output, report, rules), LLMReview)
        except GeminiError as exc:
            llm_error = str(exc)
            logger.warning("Compliance review by Gemini failed: %s", exc)

    # 4. Reliability layer
    return _merge(output, report, rules, review, llm_error)


def _build_prompt(output: DocumentAgentOutput, report: ValidationReport, rules: list[RuleChunk]) -> str:
    rules_text = "\n\n".join(f"[{r.source}]\n{r.text}" for r in rules)
    checks_text = "\n".join(f"- {'PASS' if c.passed else 'FAIL'}: {c.message}" for c in report.checks)
    return REVIEW_PROMPT.format(
        rules=rules_text,
        invoice=json.dumps(output.invoice.model_dump(), indent=2),
        checks=checks_text,
        text=output.text[:8000],
    )


def _merge(output, report, rules, review, llm_error) -> ComplianceResult:
    python_issues = report.issues
    failed_checks = [c for c in report.checks if not c.passed and c.name != "required_fields"]
    retrieved_sources = sorted({r.source for r in rules})
    review_reasons: list[str] = []
    confidence = "HIGH"

    def lower_to(level: str, reason: str):
        nonlocal confidence
        order = ["LOW", "MEDIUM", "HIGH"]
        if order.index(level) < order.index(confidence):
            confidence = level
        review_reasons.append(reason)

    # Extraction quality
    if output.extraction.method == "regex":
        lower_to("MEDIUM", "Fields were extracted with regex fallback, not Gemini.")
    if output.extraction.ocr_pages:
        lower_to("MEDIUM", f"Pages {output.extraction.ocr_pages} were scanned and read with OCR.")
    if output.extraction.ungrounded_fields:
        lower_to("MEDIUM", f"Discarded values not found in the document: {output.extraction.ungrounded_fields}.")
    if report.missing_fields:
        lower_to("LOW", f"Could not find: {', '.join(report.missing_fields)}.")
    if not rules:
        lower_to("LOW", "No relevant GST rules were retrieved.")

    # LLM review
    llm_issues, recommendations, sources_used = [], [], []
    explanation = ""
    if review is None:
        lower_to("MEDIUM", f"Regulatory review by Gemini unavailable ({llm_error}); only Python checks were run.")
    else:
        llm_issues = [f"[AI review] {issue}" for issue in review.additional_issues]
        recommendations = review.recommendations
        explanation = review.summary
        # keep only citations that point at rules we actually retrieved
        sources_used = [s for s in retrieved_sources if s in review.sources_cited]
        unknown = [s for s in review.sources_cited if s not in retrieved_sources]
        if unknown:
            lower_to("MEDIUM", f"Gemini cited sources it was not given: {unknown}.")
        if review.needs_human_review:
            lower_to("MEDIUM", "Gemini reported uncertainty about this document.")
        if llm_issues and not failed_checks:
            lower_to("MEDIUM", "Gemini raised rule issues that Python cannot verify.")

    # Status: Python decides, the LLM can only escalate to review
    if failed_checks:
        status = "NON_COMPLIANT"
    elif report.missing_fields or llm_issues or review is None:
        status = "NEEDS_REVIEW"
    else:
        status = "COMPLIANT"

    if not explanation:
        explanation = (
            "All Python checks passed." if not python_issues
            else f"{len(python_issues)} Python check(s) failed: " + " ".join(python_issues)
        )

    return ComplianceResult(
        status=status,
        confidence=confidence,
        gstin_valid=report.gstin_valid,
        tax_amount_valid=report.tax_amount_valid,
        issues=python_issues + llm_issues,
        recommendations=recommendations,
        explanation=explanation,
        sources_used=sources_used,
        requires_human_review=status == "NEEDS_REVIEW" or confidence != "HIGH",
        review_reasons=review_reasons,
        llm_used=review is not None,
        checks=report.checks,
    )
