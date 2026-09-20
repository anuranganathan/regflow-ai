"""Sample invoice text and a PDF builder used by several tests."""
import fitz

COMPLIANT_INVOICE = """TAX INVOICE
Invoice Number: INV-2025-001
Invoice Date: 15-10-2025
Supplier: ABC Traders Pvt Ltd, 12 MG Road, Bengaluru
Supplier GSTIN: 29ABCDE1234F1Z5
Recipient: XYZ Retail LLP, 5 Brigade Road, Bengaluru
Recipient GSTIN: 29PQRSX5678K1Z3
Place of Supply: Karnataka (29)
HSN Code: 8471
Description: Laptop accessories, Qty 10
Taxable Value: 10000.00
GST Rate: 18%
CGST @ 9%: 900.00
SGST @ 9%: 900.00
Total Amount: 11800.00"""

WRONG_TAX_INVOICE = COMPLIANT_INVOICE.replace("CGST @ 9%: 900.00", "CGST @ 9%: 700.00") \
                                     .replace("SGST @ 9%: 900.00", "SGST @ 9%: 700.00") \
                                     .replace("Total Amount: 11800.00", "Total Amount: 11400.00")


def make_pdf(text: str) -> bytes:
    doc = fitz.open()
    if text:
        doc.new_page().insert_text((50, 60), text, fontsize=11)
    else:
        doc.new_page()  # blank page: no text layer, like a scan
    return doc.write()
