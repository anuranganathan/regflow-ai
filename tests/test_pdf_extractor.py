import os
import sys
import unittest
import fitz

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.pdf_extractor import extract_text_from_pdf


class TestPDFExtractor(unittest.TestCase):

    def test_digital_pdf_extraction(self):
        doc_digital = fitz.open()
        page = doc_digital.new_page()
        text_content = (
            "Invoice Number: INV-100\n"
            "Supplier: Digital Solutions Pvt Ltd\n"
            "GSTIN: 29ABCDE1234F1Z5\n"
            "Taxable Value: 50000\n"
            "CGST: 4500\n"
            "SGST: 4500\n"
            "Total Amount: 59000"
        )
        page.insert_text((50, 50), text_content, fontsize=12)
        pdf_bytes = doc_digital.write()

        extracted_text = extract_text_from_pdf(pdf_bytes)
        self.assertIn("INV-100", extracted_text)
        self.assertIn("29ABCDE1234F1Z5", extracted_text)


if __name__ == "__main__":
    unittest.main()
