def calculate_gst_summary(
    taxable_value=None,
    cgst=None,
    sgst=None,
    total_amount=None
):
    if isinstance(taxable_value, dict):
        data = taxable_value
        taxable_value = data.get("taxable_value", 0)
        cgst = data.get("cgst", 0)
        sgst = data.get("sgst", 0)
        total_amount = data.get("total_amount", 0)

    taxable_value = float(taxable_value or 0)
    cgst = float(cgst or 0)
    sgst = float(sgst or 0)
    total_amount = float(total_amount or 0)

    return {
        "taxable_value": taxable_value,
        "cgst": cgst,
        "sgst": sgst,
        "total_tax": cgst + sgst,
        "total_amount": total_amount
    }