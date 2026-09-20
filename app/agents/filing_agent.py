"""Filing Summary Agent: compliance result -> GSTR-3B style summary.

Pure Python aggregation; no LLM.

Where an invoice belongs in GSTR-3B depends on which side of it you are on:
- a sale you issued       (OUTWARD) -> Table 3.1(a), tax you owe
- a purchase you received (INWARD)  -> Table 4, input tax credit you can claim
Set BUSINESS_GSTIN to your own GSTIN so the two can be told apart.
"""
from app.models.schemas import ComplianceResult, FilingSummary, InvoiceData

TABLES = {
    "OUTWARD": "3.1(a) Outward taxable supplies",
    "INWARD": "4(A)(5) All other ITC",
    "UNKNOWN": "Not determined",
}


def build_gstr3b_totals(invoices: list[InvoiceData]) -> dict:
    """Add up taxable value and tax heads across invoices."""
    totals = {"taxable": 0.0, "igst": 0.0, "cgst": 0.0, "sgst": 0.0}
    for inv in invoices:
        totals["taxable"] += inv.taxable_value or 0.0
        totals["igst"] += inv.igst or 0.0
        totals["cgst"] += inv.cgst or 0.0
        totals["sgst"] += inv.sgst or 0.0
    return {key: round(value, 2) for key, value in totals.items()}


def _note(direction: str, ready: bool, compliance: ComplianceResult, business_gstin_set: bool) -> str:
    if direction == "UNKNOWN":
        return ("Neither GSTIN on this invoice matches BUSINESS_GSTIN, so it is unclear whether this "
                "is a sale or a purchase. A person should decide where it belongs.")
    if not ready:
        if compliance.status == "NON_COMPLIANT":
            return ("Fix the listed issues (for example with a credit or debit note) before using "
                    "this invoice in GSTR-3B.")
        return "A person should review this invoice before it is used in GSTR-3B."
    if direction == "INWARD":
        return ("Purchase invoice: the tax can be claimed as input tax credit in Table 4, provided the "
                "supplier has reported it (check GSTR-2B) and you pay the supplier within 180 days.")
    assumed = "" if business_gstin_set else " (treated as a sale because BUSINESS_GSTIN is not set)"
    return f"Sales invoice: include the taxable value and tax in GSTR-3B Table 3.1(a){assumed}."


def run_filing_agent(invoice: InvoiceData, compliance: ComplianceResult,
                     direction: str = "OUTWARD", business_gstin_set: bool = False) -> FilingSummary:
    totals = build_gstr3b_totals([invoice])
    ready = (compliance.status == "COMPLIANT"
             and not compliance.requires_human_review
             and direction != "UNKNOWN")

    return FilingSummary(
        direction=direction,
        table=TABLES[direction],
        invoice_count=1,
        total_taxable_value=totals["taxable"],
        total_igst=totals["igst"],
        total_cgst=totals["cgst"],
        total_sgst=totals["sgst"],
        total_tax=round(totals["igst"] + totals["cgst"] + totals["sgst"], 2),
        ready_to_file=ready,
        note=_note(direction, ready, compliance, business_gstin_set),
    )
