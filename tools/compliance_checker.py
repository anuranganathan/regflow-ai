def check_gst_compliance(
    gstin: str,
    taxable_value: float,
    total_amount: float
):
    issues = []

    if len(gstin) != 15:
        issues.append("Invalid GSTIN length")

    if taxable_value <= 0:
        issues.append("Taxable value must be positive")

    if total_amount <= 0:
        issues.append("Total amount must be positive")

    if issues:
        return {
            "status": "non_compliant",
            "issues": issues
        }

    return {
        "status": "compliant",
        "issues": []
    }