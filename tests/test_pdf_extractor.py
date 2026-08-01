import fitz
from tools.pdf_extractor import extract_text_from_pdf

def create_test_pdfs():
    # 1. Create a digital PDF
    doc_digital = fitz.open()
    page = doc_digital.new_page()
    text_content = (
        "Invoice Number: INV-100\n"
        "Supplier: Digital Solutions Pvt Ltd\n"
        "GSTIN: 29ABCDE1234F1Z5\n"
        "Date: 20-06-2025\n"
        "Taxable Value: 50000\n"
        "CGST: 4500\n"
        "SGST: 4500\n"
        "Total Amount: 59000"
    )
    page.insert_text((50, 50), text_content, fontsize=12)
    doc_digital.save("test_digital_invoice.pdf")
    print("Created test_digital_invoice.pdf")

    # 2. Create a scanned PDF (render page as image and save in a new PDF)
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    
    doc_scanned = fitz.open()
    page_sc = doc_scanned.new_page()
    page_sc.insert_image(page_sc.rect, stream=img_bytes)
    doc_scanned.save("test_scanned_invoice.pdf")
    print("Created test_scanned_invoice.pdf (image-only scanned version)")

def run_tests():
    create_test_pdfs()

    print("\n--- Testing Digital PDF Extraction ---")
    with open("test_digital_invoice.pdf", "rb") as f:
        digital_bytes = f.read()
    
    digital_text = extract_text_from_pdf(digital_bytes)
    print("Extracted Digital Text:")
    print(digital_text)

    print("\n--- Testing Scanned PDF (OCR) Extraction ---")
    with open("test_scanned_invoice.pdf", "rb") as f:
        scanned_bytes = f.read()
        
    scanned_text = extract_text_from_pdf(scanned_bytes)
    print("Extracted Scanned Text (OCR):")
    print(scanned_text)

if __name__ == "__main__":
    run_tests()
