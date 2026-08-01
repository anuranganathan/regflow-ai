import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.filing_summary import generate_filing_summary


class TestFilingSummary(unittest.TestCase):

    def test_generate_filing_summary(self):
        sample_invoices = [
            {"taxable_value": 50000, "cgst": 4500, "sgst": 4500},
            {"taxable_value": 75000, "cgst": 6750, "sgst": 6750},
            {"taxable_value": 25000, "cgst": 2250, "sgst": 2250}
        ]

        result = generate_filing_summary(sample_invoices)
        self.assertEqual(result.get("invoice_count"), 3)
        self.assertEqual(result.get("total_taxable_value"), 150000)
        self.assertEqual(result.get("total_cgst"), 13500)
        self.assertEqual(result.get("total_sgst"), 13500)


if __name__ == "__main__":
    unittest.main()