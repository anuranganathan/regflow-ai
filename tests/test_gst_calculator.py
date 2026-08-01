import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.invoice_extractor import extract_invoice_data
from tools.gst_calculator import calculate_gst_summary


class TestGSTCalculator(unittest.TestCase):

    def test_gst_calculator(self):
        sample_path = os.path.join("data", "sample_invoices", "invoice_1.txt")
        if not os.path.exists(sample_path):
            sample_path = os.path.join("..", "data", "sample_invoices", "invoice_1.txt")

        with open(sample_path, "r", encoding="utf-8") as f:
            invoice_text = f.read()

        invoice_data = extract_invoice_data(invoice_text)
        summary = calculate_gst_summary(invoice_data)
        self.assertIsNotNone(summary)
        self.assertIn("taxable_value", summary)
        self.assertIn("total_amount", summary)


if __name__ == "__main__":
    unittest.main()