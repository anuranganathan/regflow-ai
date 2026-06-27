from tools.filing_summary import generate_filing_summary

sample_invoices = [
    {
        "taxable_value": 50000,
        "cgst": 4500,
        "sgst": 4500
    },
    {
        "taxable_value": 75000,
        "cgst": 6750,
        "sgst": 6750
    },
    {
        "taxable_value": 25000,
        "cgst": 2250,
        "sgst": 2250
    }
]

result = generate_filing_summary(sample_invoices)

print(result)