import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import tools.tools
import tools.mock_mode


class MockToolContext:
    def __init__(self):
        self.state = {}


class TestSessionMemory(unittest.TestCase):

    def test_session_memory_flow(self):
        ctx = MockToolContext()

        invoice_1_text = (
            "Invoice Number: INV-201\n"
            "Supplier: Alpha Services\n"
            "GSTIN: 29ABCDE1234F1Z5\n"
            "Taxable Value: 30000\n"
            "CGST: 2700\n"
            "SGST: 2700\n"
            "Total Amount: 35400"
        )
        res1 = tools.tools.process_invoice(invoice_1_text, ctx=ctx)
        self.assertIsNotNone(res1)
        self.assertEqual(len(ctx.state.get("invoices", [])), 1)

        invoice_2_text = (
            "Invoice Number: INV-202\n"
            "Supplier: Beta Tech\n"
            "GSTIN: 29ABCDE1234F1Z5\n"
            "Taxable Value: 20000\n"
            "CGST: 1800\n"
            "SGST: 1800\n"
            "Total Amount: 23600"
        )
        res2 = tools.tools.process_invoice(invoice_2_text, ctx=ctx)
        self.assertIsNotNone(res2)
        self.assertEqual(len(ctx.state.get("invoices", [])), 2)

        summary = tools.tools.generate_filing_summary(ctx=ctx)
        self.assertEqual(summary.get("invoice_count"), 2)


if __name__ == "__main__":
    unittest.main()
