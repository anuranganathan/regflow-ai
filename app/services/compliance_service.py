"""Deterministic GST checks, all in plain Python. No LLM is involved here.

Formats, required fields and tax arithmetic have one correct answer, so code
computes them. Gemini only explains the result afterwards.
"""
import re
from typing import Optional

from app.models.schemas import InvoiceData, ValidationCheck, ValidationReport

# 2-digit state code + 10-char PAN + entity number + 'Z' + check character
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
GSTIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # character values 0-35
VALID_STATE_CODES = {f"{n:02d}" for n in range(1, 39)} | {"97", "99"}

# 5/18/40 since 22-Sep-2025; 12/28 kept for older invoices; 0.25/3 special rates
STANDARD_GST_RATES = (0.0, 0.25, 3.0, 5.0, 12.0, 18.0, 28.0, 40.0)
TOLERANCE = 1.0  # rupees allowed for rounding differences

REQUIRED_FIELDS = ("invoice_number", "invoice_date", "supplier_name", "supplier_gstin",
                   "taxable_value", "total_amount")


def gstin_check_character(first_14: str) -> str:
    """Compute the 15th character of a GSTIN (its check character).

    Each of the first 14 characters becomes a number (0-9 = 0-9, A-Z = 10-35) and is
    multiplied by 1, 2, 1, 2 ... in turn. Each product is folded down to
    (product // 36) + (product % 36), and those are added up. The check character is
    the one that brings the total to the next multiple of 36. A single mistyped
    character changes the total, so the GSTIN no longer matches its check character.
    """
    total = 0
    for position, char in enumerate(first_14):
        product = GSTIN_CHARSET.index(char) * (2 if position % 2 else 1)
        total += product // 36 + product % 36
    return GSTIN_CHARSET[(36 - total % 36) % 36]


def validate_gstin(gstin: Optional[str]) -> tuple[bool, str]:
    """Returns (is_valid, message). Messages start with 'GSTIN' so callers can prefix them."""
    if not gstin:
        return False, "GSTIN is missing."
    gstin = gstin.strip().upper()
    if len(gstin) != 15:
        return False, f"GSTIN '{gstin}' must be 15 characters, found {len(gstin)}."
    if not GSTIN_PATTERN.match(gstin):
        return False, f"GSTIN '{gstin}' does not follow the GSTIN format."
    if gstin[:2] not in VALID_STATE_CODES:
        return False, f"GSTIN '{gstin}' has an invalid state code '{gstin[:2]}'."
    expected = gstin_check_character(gstin[:14])
    if gstin[14] != expected:
        return False, (f"GSTIN '{gstin}' fails the check-digit test: the last character should be "
                       f"'{expected}', not '{gstin[14]}', so the number is mistyped or invented.")
    return True, f"GSTIN '{gstin}' is valid (format, state code and check digit)."


def detect_direction(invoice: InvoiceData, business_gstin: str) -> str:
    """Is this invoice a sale by us (OUTWARD) or a purchase (INWARD)?

    It depends on which side of the invoice our own GSTIN is on. Without
    BUSINESS_GSTIN configured we cannot tell, so we assume it is a sale.
    """
    if not business_gstin:
        return "OUTWARD"        # assumption, stated in the filing summary note
    supplier = (invoice.supplier_gstin or "").strip().upper()
    recipient = (invoice.recipient_gstin or "").strip().upper()
    if supplier == business_gstin:
        return "OUTWARD"
    if recipient == business_gstin:
        return "INWARD"
    return "UNKNOWN"


def calculate_expected_tax(taxable_value: float, rate_percent: float) -> float:
    return round(taxable_value * rate_percent / 100, 2)


def infer_rate(taxable_value: float, total_tax: float) -> Optional[float]:
    """Find the standard GST rate that explains the tax charged, if any."""
    for rate in STANDARD_GST_RATES:
        if abs(calculate_expected_tax(taxable_value, rate) - total_tax) <= TOLERANCE:
            return rate
    return None


def validate_invoice(invoice: InvoiceData) -> ValidationReport:
    checks: list[ValidationCheck] = []

    def check(name: str, ok: bool, pass_msg: str, fail_msg: str) -> bool:
        checks.append(ValidationCheck(name=name, passed=ok, message=pass_msg if ok else fail_msg))
        return ok

    # 1. Required fields
    missing = [f for f in REQUIRED_FIELDS if getattr(invoice, f) in (None, "")]
    check("required_fields", not missing,
          "All required fields are present.", f"Missing required fields: {', '.join(missing)}.")

    # 2. GSTIN format (a missing GSTIN is already reported by required_fields)
    gstin_valid = False
    if invoice.supplier_gstin:
        ok, msg = validate_gstin(invoice.supplier_gstin)
        gstin_valid = check("supplier_gstin", ok, f"Supplier {msg}", f"Supplier {msg}")
    if invoice.recipient_gstin:
        ok, msg = validate_gstin(invoice.recipient_gstin)
        gstin_valid = check("recipient_gstin", ok, f"Recipient {msg}", f"Recipient {msg}") and gstin_valid

    # 3. Tax arithmetic
    cgst, sgst, igst = invoice.cgst or 0.0, invoice.sgst or 0.0, invoice.igst or 0.0
    total_tax = round(cgst + sgst + igst, 2)
    taxable = invoice.taxable_value
    results: list[bool] = []
    expected_tax = rate = None

    if taxable is None:
        results.append(False)  # cannot verify the tax; reported by required_fields
    elif taxable <= 0:
        results.append(check("taxable_value", False, "", "Taxable value must be a positive amount."))
    else:
        if invoice.gst_rate_percent is not None:
            rate = invoice.gst_rate_percent
            results.append(check("gst_rate", rate in STANDARD_GST_RATES,
                                 f"GST rate {rate}% is a standard rate.",
                                 f"GST rate {rate}% is not a standard GST rate."))
        else:
            rate = infer_rate(taxable, total_tax)
            results.append(check("gst_rate", rate is not None,
                                 f"Tax {total_tax} matches the {rate}% GST rate.",
                                 f"Tax {total_tax} on {taxable} does not match any standard GST rate."))

        if rate is not None:
            expected_tax = calculate_expected_tax(taxable, rate)
            results.append(check("tax_amount", abs(expected_tax - total_tax) <= TOLERANCE,
                                 f"Tax charged {total_tax} matches expected {expected_tax} ({rate}% of {taxable}).",
                                 f"Tax charged {total_tax} does not match expected {expected_tax} ({rate}% of {taxable})."))

        if invoice.total_amount is not None:
            expected_total = round(taxable + total_tax, 2)
            results.append(check("total_amount", abs(expected_total - invoice.total_amount) <= TOLERANCE,
                                 f"Total {invoice.total_amount} equals taxable value + tax.",
                                 f"Total {invoice.total_amount} does not equal taxable value + tax ({expected_total})."))

    # 4. Tax type: CGST+SGST (intra-state) or IGST (inter-state), never both
    if (cgst or sgst) and igst:
        results.append(check("tax_type", False, "",
                             "Invoice charges both CGST/SGST and IGST; only one type is allowed."))
    elif cgst or sgst:
        results.append(check("cgst_equals_sgst", abs(cgst - sgst) <= TOLERANCE,
                             f"CGST ({cgst}) equals SGST ({sgst}).",
                             f"CGST ({cgst}) and SGST ({sgst}) must be equal."))

    # 5. Tax type must match the states in the two GSTINs (only when both are known and valid)
    if gstin_valid and invoice.supplier_gstin and invoice.recipient_gstin and total_tax > 0:
        if invoice.supplier_gstin.strip()[:2] == invoice.recipient_gstin.strip()[:2]:
            results.append(check("supply_type", igst == 0,
                                 "Intra-state supply correctly uses CGST + SGST.",
                                 "Intra-state supply (same state code) should charge CGST + SGST, not IGST."))
        else:
            results.append(check("supply_type", cgst == 0 and sgst == 0,
                                 "Inter-state supply correctly uses IGST.",
                                 "Inter-state supply (different state codes) should charge IGST, not CGST + SGST."))

    return ValidationReport(
        gstin_valid=gstin_valid,
        tax_amount_valid=all(results),
        missing_fields=missing,
        checks=checks,
        expected_tax=expected_tax,
        applied_rate_percent=rate,
    )
