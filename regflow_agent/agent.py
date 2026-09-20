"""Optional chat interface built with Google ADK.

The REST API does not use this. It is one tool-calling agent: Gemini decides which
Python tool to call, and the tools reuse the same code as the API.

Run from the project root:  adk run regflow_agent   (terminal chat)
                        or  adk web                 (browser chat, pick regflow_agent)
"""
from pathlib import Path

from google.adk.agents import Agent

from app.agents.workflow import analyze_pdf
from app.config import get_settings
from app.rag.retriever import get_retriever
from app.services.compliance_service import calculate_expected_tax, validate_gstin


def analyze_invoice_pdf(file_path: str) -> dict:
    """Runs the full RegFlow compliance workflow on a local PDF invoice.

    Args:
        file_path: Path to the invoice PDF, e.g. data/sample_invoices/sample_compliant_invoice.pdf
    """
    path = Path(file_path)
    if not path.is_file() or path.suffix.lower() != ".pdf":
        return {"error": f"No PDF file found at '{file_path}'."}
    result = analyze_pdf(path.read_bytes())
    return result.model_dump(exclude={"extracted_text"})


def search_gst_rules(question: str) -> list[dict]:
    """Searches the local GST rule knowledge base and returns the most relevant rule paragraphs.

    Args:
        question: What to look up, e.g. "mandatory fields on a tax invoice".
    """
    return [{"source": c.source, "text": c.text} for c in get_retriever().retrieve(question, top_k=3)]


def check_gstin(gstin: str) -> dict:
    """Checks whether a GSTIN has a valid format.

    Args:
        gstin: The 15-character GSTIN to check.
    """
    valid, message = validate_gstin(gstin)
    return {"valid": valid, "message": message}


def calculate_gst(taxable_value: float, rate_percent: float, inter_state: bool) -> dict:
    """Calculates GST for a taxable value.

    Args:
        taxable_value: Amount before tax, in rupees.
        rate_percent: GST rate, e.g. 18.
        inter_state: True for IGST (different states), False for CGST + SGST (same state).
    """
    tax = calculate_expected_tax(taxable_value, rate_percent)
    split = {"igst": tax} if inter_state else {"cgst": round(tax / 2, 2), "sgst": round(tax / 2, 2)}
    return {"taxable_value": taxable_value, "total_tax": tax, **split, "total_amount": round(taxable_value + tax, 2)}


root_agent = Agent(
    name="regflow_assistant",
    model=get_settings().gemini_model,
    description="RegFlow AI GST compliance assistant",
    instruction=(
        "You help Indian businesses check GST invoices. "
        "Always use the tools for facts and numbers: analyze_invoice_pdf for invoice files, "
        "check_gstin for GSTIN formats, calculate_gst for tax arithmetic, and search_gst_rules "
        "for GST rules. Never do tax arithmetic yourself. When you explain a rule, name the "
        "source file returned by search_gst_rules. If the tools do not answer a question, say so."
    ),
    tools=[analyze_invoice_pdf, search_gst_rules, check_gstin, calculate_gst],
)
