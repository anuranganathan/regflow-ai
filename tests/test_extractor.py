from tools.invoice_extractor import extract_invoice_data

with open(
    "data/sample_invoices/invoice_1.txt",
    "r"
) as f:
    invoice_text = f.read()

result = extract_invoice_data(invoice_text)

print("\nPARSED RESULT:")
print(result)