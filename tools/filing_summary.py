from google.adk.tools.tool_context import ToolContext


def generate_filing_summary(invoices_json: str = None, tool_context: ToolContext = None, ctx: ToolContext = None):
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
            return {
                "invoice_count": 0,
                "total_taxable_value": 0,
                "total_cgst": 0,
                "total_sgst": 0,
                "total_tax": 0,
                "status": "ERROR PARSING INVOICES"
            }

    total_taxable_value = 0
    total_cgst = 0
    total_sgst = 0

    for invoice in invoices:
        # Resolve nested key if present (e.g. from ADK tool response wrapping)
        if isinstance(invoice, dict):
            if "process_invoice_response" in invoice:
                invoice = invoice["process_invoice_response"]
            elif "process_invoice" in invoice:
                invoice = invoice["process_invoice"]
            elif len(invoice) == 1 and isinstance(list(invoice.values())[0], dict):
                invoice = list(invoice.values())[0]

        if not isinstance(invoice, dict):
            continue

        total_taxable_value += invoice.get("taxable_value", 0) or 0
        total_cgst += invoice.get("cgst", 0) or 0
        total_sgst += invoice.get("sgst", 0) or 0

    total_tax = total_cgst + total_sgst

    return {
        "invoice_count": len(invoices),
        "total_taxable_value": total_taxable_value,
        "total_cgst": total_cgst,
        "total_sgst": total_sgst,
        "total_tax": total_tax,
        "status": "READY FOR GSTR-3B FILING"
    }