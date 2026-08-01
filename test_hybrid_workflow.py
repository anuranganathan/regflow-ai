import os
import shutil
import fitz  # PyMuPDF
import tools.tools
import tools.mock_mode
from tools.tools import process_invoice_batch, generate_filing_summary
from agents.master_agent import master_agent
from agents.document_agent import document_agent
from agents.compliance_agent import compliance_agent
from agents.filing_agent import filing_agent


class MockToolContext:
    def __init__(self):
        self.state = {}


def create_test_batch_directory():
    dir_name = "test_batch_invoices"
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)
    os.makedirs(dir_name)

    # Invoice 1
    doc1 = fitz.open()
    page1 = doc1.new_page()
    page1.insert_text((50, 50), "Invoice Number: BATCH-001\nSupplier: Batch Corp\nGSTIN: 29ABCDE1234F1Z5\nTaxable Value: 10000\nCGST: 900\nSGST: 900\nTotal Amount: 11800", fontsize=12)
    doc1.save(os.path.join(dir_name, "inv1.pdf"))

    # Invoice 2
    doc2 = fitz.open()
    page2 = doc2.new_page()
    page2.insert_text((50, 50), "Invoice Number: BATCH-002\nSupplier: Batch LLC\nGSTIN: 29ABCDE1234F1Z5\nTaxable Value: 20000\nCGST: 1800\nSGST: 1800\nTotal Amount: 23600", fontsize=12)
    doc2.save(os.path.join(dir_name, "inv2.pdf"))

    print(f"Created temporary batch directory '{dir_name}' with 2 test PDFs.")
    return dir_name


def run_hybrid_tests():
    # 1. Verify all imports work
    print("Verifying multi-agent structure and imports...")
    assert master_agent is not None
    assert document_agent is not None
    assert compliance_agent is not None
    assert filing_agent is not None
    print("✅ All agents imported and configured successfully!")

    # 2. Enable mock mode in both scopes to run tests with zero API dependencies
    orig_mock_tool = tools.tools.MOCK_ENABLED
    orig_mock_mode = tools.mock_mode.MOCK_ENABLED
    tools.tools.MOCK_ENABLED = True
    tools.mock_mode.MOCK_ENABLED = True

    # Patch mock_process_invoice to dynamically return distinct invoices
    count = 0
    def dynamic_mock(text):
        nonlocal count
        count += 1
        return {
            "invoice_number": f"BATCH-{count:03d}",
            "supplier": f"Batch Supplier {count}",
            "gstin": "29ABCDE1234F1Z5",
            "taxable_value": 10000.0 * count,
            "cgst": 900.0 * count,
            "sgst": 900.0 * count,
            "total_tax": 1800.0 * count,
            "total_amount": 11800.0 * count,
            "compliance_status": "compliant",
            "issues": []
        }
    
    orig_mock_fn = tools.tools.mock_process_invoice
    tools.tools.mock_process_invoice = dynamic_mock

    test_dir = create_test_batch_directory()
    ctx = MockToolContext()

    try:
        # 3. Test Batch Processing Tool
        print("\nTesting process_invoice_batch tool...")
        batch_res = process_invoice_batch(test_dir, ctx=ctx)
        print("Batch process result message:", batch_res)

        invoices = ctx.state.get("invoices", [])
        print("Invoices saved in context:", invoices)
        assert len(invoices) == 2, "Expected exactly 2 invoices in session state"
        assert invoices[0]["invoice_number"] == "BATCH-001"
        assert invoices[1]["invoice_number"] == "BATCH-002"
        print("✅ Batch processing tool correctly parsed and saved distinct PDFs to session state!")

        # 4. Test Filing Aggregation Tool
        print("\nTesting filing summary aggregation...")
        summary = generate_filing_summary(ctx=ctx)
        print("Summary Aggregation output:", summary)
        assert summary["invoice_count"] == 2
        assert summary["total_taxable_value"] == 30000.0
        assert summary["total_cgst"] == 2700.0
        assert summary["total_sgst"] == 2700.0
        assert summary["total_tax"] == 5400.0
        print("✅ Filing summary aggregator calculated totals correctly!")

        print("\n🎉 All hybrid workflow tests passed successfully!")
    finally:
        # Cleanup & Restore
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        tools.tools.MOCK_ENABLED = orig_mock_tool
        tools.mock_mode.MOCK_ENABLED = orig_mock_mode
        tools.tools.mock_process_invoice = orig_mock_fn


if __name__ == "__main__":
    run_hybrid_tests()
