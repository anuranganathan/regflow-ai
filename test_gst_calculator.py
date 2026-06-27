from tools.invoice_extractor import extract_invoice_data
from tools.gst_calculator import calculate_gst_summary

with open(
    "data/sample_invoices/invoice_1.txt",
    "r"
) as f:
    invoice_text = f.read()

invoice_data = extract_invoice_data(invoice_text)

summary = calculate_gst_summary(invoice_data)

print(summary)