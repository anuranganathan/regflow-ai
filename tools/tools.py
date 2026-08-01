import json
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


from tools.mock_mode import MOCK_ENABLED, mock_process_invoice
from tools.pdf_extractor import extract_text_from_pdf as extract_pdf_bytes


# =========================
# SINGLE GEMINI CALL ENGINE
# =========================

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts text from a PDF file. Use this tool if the user uploads or specifies a PDF invoice file path.
    It automatically detects scanned pages and runs OCR where necessary.

    Args:
        file_path: The local path or filename of the PDF invoice file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Invoice PDF file not found at: {file_path}")
    with open(file_path, "rb") as f:
        pdf_bytes = f.read()
    return extract_pdf_bytes(pdf_bytes)


from google.adk.tools.tool_context import ToolContext


def process_invoice(invoice_text: str, tool_context: ToolContext = None, ctx: ToolContext = None):
    """
    One-call GST processing engine (NO multiple tool calls)
    """
    ctx = tool_context or ctx
    original_source = invoice_text

    # If a file path is passed, extract text from it first
    if isinstance(invoice_text, str) and os.path.exists(invoice_text):
        ext = os.path.splitext(invoice_text)[1].lower()
        if ext == ".pdf":
            with open(invoice_text, "rb") as f:
                pdf_bytes = f.read()
            invoice_text = extract_pdf_bytes(pdf_bytes)
        elif ext in {".png", ".jpg", ".jpeg"}:
            from utils.image_reader import extract_text_from_image_file
            invoice_text = extract_text_from_image_file(invoice_text)


    if MOCK_ENABLED:
        result = mock_process_invoice(invoice_text)
    else:
        prompt = f"""
You are a GST compliance engine for India.

Return ONLY valid JSON. No explanation.

Process this invoice:

{invoice_text}

Return format:
{{
  "invoice_number": "",
  "supplier": "",
  "gstin": "",
  "taxable_value": 0,
  "cgst": 0,
  "sgst": 0,
  "total_tax": 0,
  "total_amount": 0,
  "compliance_status": "compliant or non-compliant",
  "issues": []
}}

Rules:
- GSTIN must be 15 characters else mark non-compliant
- CGST = SGST
- total_tax = cgst + sgst
- total_amount = taxable_value + total_tax
"""

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )

            text = response.text.strip()

            # clean markdown if model returns ```json
            if "```" in text:
                text = text.replace("```json", "").replace("```", "").strip()

            result = json.loads(text)
        except Exception as api_err:
            print(f"Gemini API rate limit or error in tools.py ({api_err}). Using regex fallback.")
            from tools.invoice_extractor import regex_fallback_invoice_extract
            result = regex_fallback_invoice_extract(invoice_text)

    # Local Storage saving
    try:
        from firebase.firebase_client import save_uploaded_file
        local_file_path = save_uploaded_file(original_source)
    except Exception as e:
        print(f"Error saving file locally: {e}")
        local_file_path = ""

    result["file_path"] = local_file_path

    # Firestore Metadata persistence
    try:
        from firebase.firebase_client import save_invoice
        save_invoice(result)
    except Exception as e:
        print(f"Error persisting invoice metadata to Firestore: {e}")

    # Save to session memory if context is active
    if ctx is not None:
        invoices = ctx.state.get("invoices", [])
        
        # Deduplicate: check if invoice_number already exists
        invoice_number = result.get("invoice_number")
        existing_numbers = {inv.get("invoice_number") for inv in invoices if isinstance(inv, dict) and inv.get("invoice_number")}
        
        if not invoice_number or invoice_number not in existing_numbers:
            invoices.append(result)
            ctx.state["invoices"] = invoices
            print(f"Session Memory: Stored invoice {invoice_number}. Session count: {len(invoices)}")
        else:
            print(f"Session Memory: Invoice {invoice_number} already in session. Skipping duplicate save.")

    return result



# =========================
# FINAL FILING AGGREGATOR (NO GEMINI)
# =========================

def generate_filing_summary(invoices_json: str = None, tool_context: ToolContext = None, ctx: ToolContext = None):
    """
    Pure Python aggregation (no API calls)
    """
    ctx = tool_context or ctx
    if invoices_json is None or invoices_json == "" or invoices_json == "[]":
        if ctx is not None:
            invoices = ctx.state.get("invoices", [])
        else:
            invoices = []
    elif isinstance(invoices_json, list):
        invoices = invoices_json
    else:
        try:
            invoices = json.loads(invoices_json)
        except Exception:
            # Fallback if string cannot be parsed as JSON directly
            return {
                "invoice_count": 0,
                "total_taxable_value": 0,
                "total_cgst": 0,
                "total_sgst": 0,
                "total_tax": 0,
                "status": "ERROR PARSING INVOICES"
            }

    total_taxable = 0
    total_cgst = 0
    total_sgst = 0

    for inv in invoices:
        # Resolve nested key if present (e.g. from ADK tool response wrapping)
        if isinstance(inv, dict):
            if "process_invoice_response" in inv:
                inv = inv["process_invoice_response"]
            elif "process_invoice" in inv:
                inv = inv["process_invoice"]
            elif len(inv) == 1 and isinstance(list(inv.values())[0], dict):
                inv = list(inv.values())[0]

        if not isinstance(inv, dict):
            continue

        total_taxable += inv.get("taxable_value", 0) or 0
        total_cgst += inv.get("cgst", 0) or 0
        total_sgst += inv.get("sgst", 0) or 0

    return {
        "invoice_count": len(invoices),
        "total_taxable_value": total_taxable,
        "total_cgst": total_cgst,
        "total_sgst": total_sgst,
        "total_tax": total_cgst + total_sgst,
        "status": "READY FOR GSTR-3B FILING"
    }


def process_invoice_batch(folder_path: str, tool_context: ToolContext = None, ctx: ToolContext = None) -> str:
    """
    Scans a folder and automatically processes all PDF invoice files inside it in a batch.
    Extracted data is accumulated inside the session memory.

    Args:
        folder_path: The path to the folder containing the invoices.
    """
    ctx = tool_context or ctx
    if not os.path.exists(folder_path):
        return f"Error: Folder path '{folder_path}' does not exist."
    if not os.path.isdir(folder_path):
        return f"Error: Path '{folder_path}' is not a directory."

    files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    if not files:
        return f"No PDF invoices found in directory: {folder_path}"

    processed_count = 0
    errors = []

    for file_path in files:
        try:
            # We call process_invoice directly. It handles text extraction and session memory saving.
            process_invoice(invoice_text=file_path, ctx=ctx)
            processed_count += 1
        except Exception as e:
            errors.append(f"Failed to process {os.path.basename(file_path)}: {str(e)}")

    status_msg = f"Successfully batch-processed {processed_count} invoice(s) from '{folder_path}'."
    if errors:
        status_msg += " Warnings:\n" + "\n".join(errors)
    return status_msg