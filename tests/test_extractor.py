import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.invoice_extractor import extract_invoice_data


class TestInvoiceExtractor(unittest.TestCase):

    def test_extract_invoice(self):
        sample_path = os.path.join("data", "sample_invoices", "invoice_1.txt")
        if not os.path.exists(sample_path):
            sample_path = os.path.join("..", "data", "sample_invoices", "invoice_1.txt")
            
        with open(sample_path, "r", encoding="utf-8") as f:
            invoice_text = f.read()

        result = extract_invoice_data(invoice_text)
        self.assertIsNotNone(result)
        self.assertIn("invoice_number", result)
        self.assertIn("gstin", result)


if __name__ == "__main__":
    unittest.main()