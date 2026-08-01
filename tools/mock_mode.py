import json

MOCK_ENABLED = False  # turn ON only if quota breaks


def mock_process_invoice(invoice_text: str):
    return {
        "invoice_number": "MOCK-INV",
        "supplier": "Mock Supplier",
        "gstin": "29ABCDE1234F1Z5",
        "taxable_value": 50000,
        "cgst": 4500,
        "sgst": 4500,
        "total_tax": 9000,
        "total_amount": 59000,
        "compliance_status": "compliant",
        "issues": []
    }