import json


def generate_filing_summary(invoices_json: str):

    invoices = json.loads(invoices_json)

    total_taxable_value = 0
    total_cgst = 0
    total_sgst = 0

    for invoice in invoices:
        total_taxable_value += invoice.get("taxable_value", 0)
        total_cgst += invoice.get("cgst", 0)
        total_sgst += invoice.get("sgst", 0)

    total_tax = total_cgst + total_sgst

    return {
        "invoice_count": len(invoices),
        "total_taxable_value": total_taxable_value,
        "total_cgst": total_cgst,
        "total_sgst": total_sgst,
        "total_tax": total_tax
    }