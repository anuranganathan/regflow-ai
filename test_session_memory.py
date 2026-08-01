import json
import tools.tools
import tools.mock_mode


class MockToolContext:
    def __init__(self):
        self.state = {}


def test_session_memory():
    # Disable mock mode in both module scopes to ensure real API execution
    orig_mock_tool = tools.tools.MOCK_ENABLED
    orig_mock_mode = tools.mock_mode.MOCK_ENABLED
    tools.tools.MOCK_ENABLED = False
    tools.mock_mode.MOCK_ENABLED = False
    
    try:
        print("Initializing Mock Tool Context...")
        ctx = MockToolContext()

        # 1. Process Invoice 1
        invoice_1_text = (
            "Invoice Number: INV-201\n"
            "Supplier: Alpha Services\n"
            "GSTIN: 29ABCDE1234F1Z5\n"
            "Taxable Value: 30000\n"
            "CGST: 2700\n"
            "SGST: 2700\n"
            "Total Amount: 35400"
        )
        print("\nProcessing Invoice 1...")
        res1 = tools.tools.process_invoice(invoice_1_text, ctx=ctx)
        print("Parsed result 1:", res1)
        print("Current state invoices:", ctx.state.get("invoices"))

        # 2. Process Invoice 2
        invoice_2_text = (
            "Invoice Number: INV-202\n"
            "Supplier: Beta Tech\n"
            "GSTIN: 29ABCDE1234F1Z5\n"
            "Taxable Value: 20000\n"
            "CGST: 1800\n"
            "SGST: 1800\n"
            "Total Amount: 23600"
        )
        print("\nProcessing Invoice 2...")
        res2 = tools.tools.process_invoice(invoice_2_text, ctx=ctx)
        print("Parsed result 2:", res2)
        print("Current state invoices count:", len(ctx.state.get("invoices", [])))

        # 3. Process Duplicate Invoice 1 (should be skipped by deduplication)
        print("\nProcessing Duplicate Invoice 1...")
        tools.tools.process_invoice(invoice_1_text, ctx=ctx)
        print("Current state invoices count (should remain 2):", len(ctx.state.get("invoices", [])))

        # 4. Generate summary using the ToolContext session state (no invoices_json parameter)
        print("\nGenerating Filing Summary across the Session...")
        summary = tools.tools.generate_filing_summary(ctx=ctx)
        print("Session Summary Output:")
        print(json.dumps(summary, indent=2))

        # Assertions
        assert len(ctx.state["invoices"]) == 2, "Expected exactly 2 invoices in session state"
        assert summary["invoice_count"] == 2, "Expected 2 invoices processed in summary"
        assert summary["total_taxable_value"] == 50000.0, "Expected total taxable value to be 50,000"
        assert summary["total_cgst"] == 4500.0, "Expected total CGST to be 4,500"
        assert summary["total_sgst"] == 4500.0, "Expected total SGST to be 4,500"
        assert summary["total_tax"] == 9000.0, "Expected total tax to be 9,000"
        
        print("\n✅ Session Memory test PASSED successfully!")
    finally:
        tools.tools.MOCK_ENABLED = orig_mock_tool
        tools.mock_mode.MOCK_ENABLED = orig_mock_mode


if __name__ == "__main__":
    test_session_memory()
