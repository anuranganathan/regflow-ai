import json
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


# =========================
# SINGLE GEMINI CALL ENGINE
# =========================

def process_invoice(invoice_text: str):
    """
    One-call GST processing engine (NO multiple tool calls)
    """
    if MOCK_ENABLED:
        return mock_process_invoice(invoice_text)

        
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

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    text = response.text.strip()

    # clean markdown if model returns ```json
    if "```" in text:
        text = text.replace("```json", "").replace("```", "").strip()

    return json.loads(text)


# =========================
# FINAL FILING AGGREGATOR (NO GEMINI)
# =========================

def generate_filing_summary(invoices_json: str):
    """
    Pure Python aggregation (no API calls)
    """

    invoices = json.loads(invoices_json)

    total_taxable = 0
    total_cgst = 0
    total_sgst = 0

    for inv in invoices:
        total_taxable += inv.get("taxable_value", 0)
        total_cgst += inv.get("cgst", 0)
        total_sgst += inv.get("sgst", 0)

    return {
        "invoice_count": len(invoices),
        "total_taxable_value": total_taxable,
        "total_cgst": total_cgst,
        "total_sgst": total_sgst,
        "total_tax": total_cgst + total_sgst,
        "status": "READY FOR GSTR-3B FILING"
    }