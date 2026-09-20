"""Sales invoices and purchase invoices go to different GSTR-3B tables."""
import pytest

from app.agents.filing_agent import run_filing_agent
from app.models.schemas import ComplianceResult, InvoiceData
from app.services.compliance_service import detect_direction

OUR_GSTIN = "29ABCDE1234F1ZW"       # the business running RegFlow
OTHER_GSTIN = "27AAPFS1234K1ZW"     # someone else

SALE = InvoiceData(supplier_gstin=OUR_GSTIN, recipient_gstin=OTHER_GSTIN,
                   taxable_value=10000, igst=1800, total_amount=11800)
PURCHASE = InvoiceData(supplier_gstin=OTHER_GSTIN, recipient_gstin=OUR_GSTIN,
                       taxable_value=10000, igst=1800, total_amount=11800)
UNRELATED = InvoiceData(supplier_gstin=OTHER_GSTIN, recipient_gstin="29PQRSX5678K1ZU",
                        taxable_value=10000, igst=1800, total_amount=11800)

COMPLIANT = ComplianceResult(
    status="COMPLIANT", confidence="HIGH", gstin_valid=True, tax_amount_valid=True,
    issues=[], recommendations=[], explanation="", sources_used=[],
    requires_human_review=False, review_reasons=[], llm_used=True, checks=[],
)


@pytest.mark.parametrize("invoice, expected", [
    (SALE, "OUTWARD"),
    (PURCHASE, "INWARD"),
    (UNRELATED, "UNKNOWN"),
])
def test_direction_from_our_own_gstin(invoice, expected):
    assert detect_direction(invoice, OUR_GSTIN) == expected


def test_without_business_gstin_everything_is_assumed_to_be_a_sale():
    assert detect_direction(PURCHASE, "") == "OUTWARD"
    summary = run_filing_agent(PURCHASE, COMPLIANT, "OUTWARD", business_gstin_set=False)
    assert "BUSINESS_GSTIN is not set" in summary.note


def test_sale_goes_to_table_31a():
    summary = run_filing_agent(SALE, COMPLIANT, "OUTWARD", business_gstin_set=True)
    assert summary.direction == "OUTWARD"
    assert summary.table == "3.1(a) Outward taxable supplies"
    assert summary.total_igst == 1800 and summary.ready_to_file


def test_purchase_goes_to_the_itc_table():
    summary = run_filing_agent(PURCHASE, COMPLIANT, "INWARD", business_gstin_set=True)
    assert summary.direction == "INWARD"
    assert summary.table == "4(A)(5) All other ITC"
    assert "input tax credit" in summary.note
    assert "GSTR-2B" in summary.note and "180 days" in summary.note


def test_unknown_direction_is_never_ready_to_file():
    summary = run_filing_agent(UNRELATED, COMPLIANT, "UNKNOWN", business_gstin_set=True)
    assert not summary.ready_to_file
    assert "unclear whether" in summary.note
