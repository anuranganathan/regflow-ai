from app.agents.filing_agent import build_gstr3b_totals
from app.models.schemas import InvoiceData
from app.services.compliance_service import calculate_expected_tax, infer_rate, validate_invoice


def make_invoice(**overrides) -> InvoiceData:
    fields = dict(
        invoice_number="INV-1", invoice_date="15-10-2025", supplier_name="ABC Traders",
        supplier_gstin="29ABCDE1234F1Z5", recipient_gstin="29PQRSX5678K1Z3",
        taxable_value=10000, gst_rate_percent=18, cgst=900, sgst=900, total_amount=11800,
    )
    fields.update(overrides)
    return InvoiceData(**fields)


def failed(report) -> set[str]:
    return {c.name for c in report.checks if not c.passed}


def test_expected_tax_is_calculated_in_python():
    assert calculate_expected_tax(10000, 18) == 1800
    assert calculate_expected_tax(2500, 5) == 125
    assert calculate_expected_tax(999.99, 18) == 180.0


def test_rate_is_inferred_from_tax_when_not_printed():
    assert infer_rate(10000, 1800) == 18
    assert infer_rate(10000, 500) == 5
    assert infer_rate(10000, 1234) is None


def test_correct_intra_state_invoice_passes():
    report = validate_invoice(make_invoice())
    assert report.gstin_valid and report.tax_amount_valid
    assert report.expected_tax == 1800
    assert failed(report) == set()


def test_wrong_tax_amount_is_detected():
    report = validate_invoice(make_invoice(cgst=700, sgst=700, total_amount=11400))
    assert not report.tax_amount_valid
    assert "tax_amount" in failed(report)


def test_total_must_equal_taxable_plus_tax():
    report = validate_invoice(make_invoice(total_amount=12000))
    assert "total_amount" in failed(report)


def test_cgst_and_sgst_must_be_equal():
    report = validate_invoice(make_invoice(cgst=1000, sgst=800))
    assert "cgst_equals_sgst" in failed(report)


def test_inter_state_supply_must_use_igst():
    # supplier in Karnataka (29), buyer in Maharashtra (27), but CGST+SGST charged
    report = validate_invoice(make_invoice(recipient_gstin="27PQRSX5678K1Z3"))
    assert "supply_type" in failed(report)

    ok = validate_invoice(make_invoice(recipient_gstin="27PQRSX5678K1Z3", cgst=None, sgst=None, igst=1800))
    assert failed(ok) == set()


def test_missing_fields_are_reported_not_guessed():
    report = validate_invoice(make_invoice(supplier_gstin=None, taxable_value=None))
    assert set(report.missing_fields) == {"supplier_gstin", "taxable_value"}
    assert not report.gstin_valid and not report.tax_amount_valid
    assert failed(report) == {"required_fields"}


def test_gstr3b_totals():
    totals = build_gstr3b_totals([make_invoice(), make_invoice(cgst=None, sgst=None, igst=1800)])
    assert totals == {"taxable": 20000, "igst": 1800, "cgst": 900, "sgst": 900}
