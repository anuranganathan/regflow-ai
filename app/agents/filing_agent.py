"""Filing Summary Agent: compliance result -> GSTR-3B style summary.

Pure Python aggregation; no LLM. Uploaded invoices are treated as the business's
own sales invoices, so they belong in GSTR-3B Table 3.1(a) (outward taxable supplies).
"""
from app.models.schemas import ComplianceResult, FilingSummary, InvoiceData


def build_gstr3b_totals(invoices: list[InvoiceData]) -> dict:
    """Add up taxable value and tax heads across invoices."""
    totals = {"taxable": 0.0, "igst": 0.0, "cgst": 0.0, "sgst": 0.0}
    for inv in invoices:
        totals["taxable"] += inv.taxable_value or 0.0
        totals["igst"] += inv.igst or 0.0
        totals["cgst"] += inv.cgst or 0.0
        totals["sgst"] += inv.sgst or 0.0
    return {key: round(value, 2) for key, value in totals.items()}


def run_filing_agent(invoice: InvoiceData, compliance: ComplianceResult) -> FilingSummary:
    totals = build_gstr3b_totals([invoice])
    ready = compliance.status == "COMPLIANT" and not compliance.requires_human_review

    if ready:
        note = "Invoice passed all checks and can be included in GSTR-3B Table 3.1(a)."
    elif compliance.status == "NON_COMPLIANT":
        note = "Fix the listed issues (e.g. with a credit/debit note) before including this invoice in GSTR-3B."
    else:
        note = "A person should review this invoice before it is included in GSTR-3B."

    return FilingSummary(
        invoice_count=1,
        total_taxable_value=totals["taxable"],
        total_igst=totals["igst"],
        total_cgst=totals["cgst"],
        total_sgst=totals["sgst"],
        total_tax=round(totals["igst"] + totals["cgst"] + totals["sgst"], 2),
        ready_to_file=ready,
        note=note,
    )
