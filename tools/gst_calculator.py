def calculate_gst_summary(
    taxable_value: float,
    cgst: float,
    sgst: float,
    total_amount: float
):
    return {
        "taxable_value": taxable_value,
        "cgst": cgst,
        "sgst": sgst,
        "total_tax": cgst + sgst,
        "total_amount": total_amount
    }