import os
import shutil
import unittest
from unittest.mock import MagicMock
import firebase.firebase_client as fc


class MockDocument:
    def __init__(self, data, exists=True):
        self._data = data
        self.exists = exists
        # Mocking hasattr / method for isoformat conversion
        if data and "processed_at" in data:
            class MockTimestamp:
                def isoformat(self):
                    return "2026-06-30T18:00:00Z"
            data["processed_at"] = MockTimestamp()

    def to_dict(self):
        return self._data


class MockDocRef:
    def __init__(self, doc_id, mock_db):
        self.doc_id = doc_id
        self.mock_db = mock_db

    def set(self, data):
        # Convert SERVER_TIMESTAMP placeholder to mock timestamp object
        if data.get("processed_at") == "SERVER_TIMESTAMP_MOCK":
            data["processed_at"] = "2026-06-30T18:00:00Z"
        self.mock_db.data_store[self.doc_id] = data

    def get(self, *args, **kwargs):
        if self.doc_id in self.mock_db.data_store:
            return MockDocument(self.mock_db.data_store[self.doc_id])
        return MockDocument(None, exists=False)

    def update(self, update_dict):
        if self.doc_id in self.mock_db.data_store:
            self.mock_db.data_store[self.doc_id].update(update_dict)


class MockQuery:
    def __init__(self, mock_db):
        self.mock_db = mock_db

    def stream(self, *args, **kwargs):
        return [MockDocument(data) for data in self.mock_db.data_store.values()]



class MockCollectionRef:
    def __init__(self, mock_db):
        self.mock_db = mock_db

    def document(self, doc_id):
        return MockDocRef(doc_id, self.mock_db)

    def order_by(self, field, direction=None):
        return MockQuery(self.mock_db)


class MockFirestoreClient:
    def __init__(self):
        self.data_store = {}

    def collection(self, name):
        return MockCollectionRef(self)


class TestFirebaseIntegration(unittest.TestCase):
    def setUp(self):
        self.test_uploads_dir = "test_uploads"
        # Temporarily redirect uploads folder path in firebase_client
        self.orig_uploads_dir = fc.UPLOADS_DIR
        fc.UPLOADS_DIR = self.test_uploads_dir
        
        # Temporarily redirect local db path to ensure hermetic testing
        self.orig_local_db_path = fc.LOCAL_DB_PATH
        fc.LOCAL_DB_PATH = os.path.join(self.test_uploads_dir, "invoices_db.json")

        # ALWAYS setup mock db for unit tests to avoid network calls and DNS timeouts
        self.orig_initialized = fc.FIREBASE_INITIALIZED
        self.orig_db = fc.db
        
        print("Patching with MockFirestoreClient for hermetic unit tests...")
        fc.db = MockFirestoreClient()
        fc.FIREBASE_INITIALIZED = True
        
        # Mock firestore SERVER_TIMESTAMP and Query
        class MockFirestoreModule:
            SERVER_TIMESTAMP = "SERVER_TIMESTAMP_MOCK"
            class Query:
                ASCENDING = "ASCENDING"
                DESCENDING = "DESCENDING"
        
        self.orig_firestore = fc.firestore
        fc.firestore = MockFirestoreModule()

    def tearDown(self):
        fc.UPLOADS_DIR = self.orig_uploads_dir
        fc.LOCAL_DB_PATH = self.orig_local_db_path
        fc.FIREBASE_INITIALIZED = self.orig_initialized
        fc.db = self.orig_db
        if hasattr(self, "orig_firestore"):
            fc.firestore = self.orig_firestore
        if os.path.exists(self.test_uploads_dir):
            shutil.rmtree(self.test_uploads_dir)

    def test_save_uploaded_file_with_text(self):
        text_source = "Invoice Number: TEST-TEXT-001\nSupplier: Text Supplier\nTotal: 100"
        rel_path = fc.save_uploaded_file(text_source)
        
        self.assertTrue(rel_path.startswith("uploads/"))
        full_path = os.path.join(self.test_uploads_dir, os.path.basename(rel_path))
        self.assertTrue(os.path.exists(full_path))
        with open(full_path, "r") as f:
            self.assertEqual(f.read(), text_source)

    def test_save_uploaded_file_with_local_file(self):
        temp_file = "temp_invoice.pdf"
        try:
            with open(temp_file, "w") as f:
                f.write("Dummy PDF content")
            
            rel_path = fc.save_uploaded_file(temp_file)
            self.assertEqual(rel_path, f"uploads/{temp_file}")
            
            copied_path = os.path.join(self.test_uploads_dir, temp_file)
            self.assertTrue(os.path.exists(copied_path))
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_firestore_crud_operations(self):
        invoice_data = {
            "invoice_number": "INV-TEST-999",
            "supplier": "Acme Corp",
            "gstin": "29ABCDE1234F1Z5",
            "taxable_value": 15000.0,
            "cgst": 1350.0,
            "sgst": 1350.0,
            "total_tax": 2700.0,
            "total_amount": 17700.0,
            "compliance_status": "compliant",
            "issues": [],
            "file_path": "uploads/temp_invoice.pdf"
        }

        # 1. Save invoice
        save_status = fc.save_invoice(invoice_data)
        self.assertTrue(save_status)

        # 2. Get invoice
        retrieved = fc.get_invoice("INV-TEST-999")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["supplier"], "Acme Corp")
        self.assertEqual(retrieved["taxable_value"], 15000.0)

        # 3. List invoices
        all_invoices = fc.list_invoices()
        self.assertEqual(len(all_invoices), 1)
        self.assertEqual(all_invoices[0]["invoice_number"], "INV-TEST-999")

        # 4. Update status
        update_status = fc.update_invoice_status("INV-TEST-999", "non_compliant")
        self.assertTrue(update_status)
        
        updated = fc.get_invoice("INV-TEST-999")
        self.assertEqual(updated["compliance_status"], "non_compliant")

    def test_upload_endpoint(self):
        from fastapi.testclient import TestClient
        from app import app
        from unittest.mock import patch

        client = TestClient(app)
        
        mock_result = {
            "invoice_number": "INV-API-777",
            "supplier": "API Supplier",
            "gstin": "29ABCDE1234F1Z5",
            "taxable_value": 8000.0,
            "cgst": 720.0,
            "sgst": 720.0,
            "total_tax": 1440.0,
            "total_amount": 9440.0,
            "compliance_status": "compliant",
            "issues": [],
            "file_path": "uploads/dummy.pdf"
        }

        # Patch tools.tools.process_invoice and utils.pdf_reader.extract_text_from_pdf_file
        with patch("api.upload.extract_text_from_pdf_file", return_value="dummy text") as mock_extract, \
             patch("api.upload.process_invoice", return_value=mock_result) as mock_proc:
             
            dummy_pdf_content = b"%PDF-1.4 dummy contents"
            response = client.post(
                "/upload",
                files={"file": ("dummy.pdf", dummy_pdf_content, "application/pdf")}
            )
            
            self.assertEqual(response.status_code, 200)
            json_data = response.json()
            
            self.assertTrue(json_data["success"])
            self.assertEqual(json_data["filename"], "dummy.pdf")
            self.assertEqual(json_data["invoice"]["invoice_number"], "INV-API-777")
            self.assertEqual(json_data["gst_summary"]["total_tax"], 1440.0)
            self.assertEqual(json_data["compliance"]["status"], "compliant")
            
            # Assert file was saved under the test uploads directory
            saved_pdf = os.path.join(self.test_uploads_dir, "dummy.pdf")
            self.assertTrue(os.path.exists(saved_pdf))
            with open(saved_pdf, "rb") as f:
                self.assertEqual(f.read(), dummy_pdf_content)

            # Ensure process_invoice was called with the extracted text
            mock_proc.assert_called_once_with("dummy text")
            mock_extract.assert_called_once_with(saved_pdf)

    def test_history_endpoints(self):
        from fastapi.testclient import TestClient
        from app import app
        from unittest.mock import patch

        client = TestClient(app)

        mock_invoices = [
            {
                "invoice_number": "INV-TEST-001",
                "supplier": "Supplier A",
                "gstin": "29ABCDE1234F1Z5",
                "taxable_value": 10000.0,
                "total_amount": 11800.0,
                "compliance_status": "compliant",
                "issues": [],
                "processed_at": "2026-07-01T10:00:00Z",
                "file_path": "uploads/inv1.pdf",
                "secret_metadata": "should_be_filtered_out"
            },
            {
                "invoice_number": "INV-TEST-002",
                "supplier": "Supplier B",
                "gstin": "29ABCDE1234F1Z5",
                "taxable_value": 20000.0,
                "total_amount": 23600.0,
                "compliance_status": "non_compliant",
                "issues": ["Invalid GSTIN length"],
                "processed_at": "2026-07-01T11:00:00Z",
                "file_path": "uploads/inv2.pdf"
            }
        ]

        with patch("api.history.get_all_invoices", return_value=mock_invoices) as mock_get_all, \
             patch("api.history.get_invoice") as mock_get_one:

            # 1. Test GET /history (no filters)
            response = client.get("/history")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["count"], 2)
            self.assertEqual(data["invoices"][0]["invoice_number"], "INV-TEST-001")
            # Verify internal metadata is filtered out
            self.assertNotIn("secret_metadata", data["invoices"][0])
            self.assertEqual(data["invoices"][1]["invoice_number"], "INV-TEST-002")

            # 2. Test GET /history?status=non_compliant
            response = client.get("/history?status=non_compliant")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["invoices"][0]["invoice_number"], "INV-TEST-002")

            # 3. Test GET /history?supplier=Supplier A
            response = client.get("/history?supplier=Supplier A")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["invoices"][0]["invoice_number"], "INV-TEST-001")

            # 4. Test GET /history?limit=1
            response = client.get("/history?limit=1")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["invoices"][0]["invoice_number"], "INV-TEST-001")

            # 5. Test GET /history/{invoice_number} (success)
            mock_get_one.return_value = mock_invoices[0]
            response = client.get("/history/INV-TEST-001")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["invoice"]["invoice_number"], "INV-TEST-001")

            # 6. Test GET /history/{invoice_number} (404 not found)
            mock_get_one.return_value = None
            response = client.get("/history/INV-NON-EXISTENT")
            self.assertEqual(response.status_code, 404)
            self.assertIn("not found", response.json()["detail"])

    def test_dashboard_endpoint(self):
        from fastapi.testclient import TestClient
        from app import app
        from unittest.mock import patch
        from datetime import datetime

        client = TestClient(app)

        # 1. Test empty database
        with patch("services.dashboard_service.get_all_invoices", return_value=[]) as mock_get:
            response = client.get("/dashboard")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["summary"]["total_invoices"], 0)
            self.assertEqual(data["summary"]["compliance_percentage"], 0.0)
            self.assertEqual(data["summary"]["top_supplier"], "")

        # 2. Test multiple invoices with mixed compliance
        mock_invoices = [
            {
                "invoice_number": "INV-A",
                "supplier": "Acme Corp",
                "gstin": "29ABCDE1234F1Z5",
                "taxable_value": 10000.0,
                "cgst": 900.0,
                "sgst": 900.0,
                "total_amount": 11800.0,
                "compliance_status": "compliant",
                "processed_at": datetime.now().isoformat()
            },
            {
                "invoice_number": "INV-B",
                "supplier": "Beta Solutions",
                "gstin": "29ABCDE1234F1Z5",
                "taxable_value": 20000.0,
                "cgst": 1800.0,
                "sgst": 1800.0,
                "total_amount": 23600.0,
                "compliance_status": "non_compliant",
                "processed_at": datetime.now().isoformat()
            },
            {
                "invoice_number": "INV-C",
                "supplier": "Acme Corp",
                "gstin": "29ABCDE1234F1Z5",
                "taxable_value": 5000.0,
                "cgst": 450.0,
                "sgst": 450.0,
                "total_amount": 5900.0,
                "compliance_status": "compliant",
                "processed_at": datetime.now().isoformat()
            }
        ]

        with patch("services.dashboard_service.get_all_invoices", return_value=mock_invoices) as mock_get:
            response = client.get("/dashboard")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            self.assertTrue(data["success"])
            # Validate summary metrics
            self.assertEqual(data["summary"]["total_invoices"], 3)
            self.assertEqual(data["summary"]["compliant"], 2)
            self.assertEqual(data["summary"]["non_compliant"], 1)
            self.assertEqual(data["summary"]["compliance_percentage"], 66.67) # 2/3 * 100
            self.assertEqual(data["summary"]["total_taxable_value"], 35000.0)
            self.assertEqual(data["summary"]["total_cgst"], 3150.0)
            self.assertEqual(data["summary"]["total_gst"], 6300.0) # cgst + sgst
            self.assertEqual(data["summary"]["total_invoice_value"], 41300.0)
            self.assertEqual(data["summary"]["average_invoice_value"], round(41300.0 / 3, 2))
            
            # Validate top supplier
            self.assertEqual(data["summary"]["top_supplier"], "Acme Corp")
            self.assertEqual(data["summary"]["top_supplier_invoice_count"], 2)
            
            # Validate supplier breakdown count
            self.assertEqual(len(data["supplier_breakdown"]), 2)
            self.assertEqual(data["supplier_breakdown"][0]["supplier"], "Acme Corp")
            self.assertEqual(data["supplier_breakdown"][0]["invoice_count"], 2)

    def test_batch_upload_endpoint(self):
        from fastapi.testclient import TestClient
        from app import app
        from unittest.mock import patch

        client = TestClient(app)

        mock_inv1 = {
            "invoice_number": "INV-BATCH-1",
            "supplier": "Supplier 1",
            "gstin": "29ABCDE1234F1Z5",
            "taxable_value": 1000.0,
            "cgst": 90.0,
            "sgst": 90.0,
            "total_tax": 180.0,
            "total_amount": 1180.0,
            "compliance_status": "compliant",
            "issues": []
        }

        # 1. Test complete success
        with patch("services.batch_processor.extract_text_from_file", return_value="inv1 text") as mock_extract, \
             patch("services.batch_processor.process_invoice", return_value=mock_inv1) as mock_proc, \
             patch("google.genai.Client") as mock_gemini_client:

            # Mock Gemini recommendation response
            mock_gen_response = mock_gemini_client.return_value.models.generate_content.return_value
            mock_gen_response.text = "Batch processed successfully. Invoices are ready for filing."

            # Perform multipart files upload
            files = [
                ("files", ("inv1.pdf", b"%PDF-1.4 mock contents 1", "application/pdf")),
                ("files", ("inv2.pdf", b"%PDF-1.4 mock contents 2", "application/pdf"))
            ]
            response = client.post("/batch-upload", files=files)
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["success"])
            self.assertEqual(data["total_uploaded"], 2)
            self.assertEqual(data["processed"], 2)
            self.assertEqual(data["failed"], 0)
            self.assertEqual(len(data["results"]), 2)
            self.assertEqual(data["results"][0]["invoice_number"], "INV-BATCH-1")
            self.assertEqual(data["filing_summary"]["invoice_count"], 2)
            self.assertEqual(data["filing_summary"]["total_taxable_value"], 2000.0) # mock returned INV-BATCH-1 for both
            self.assertEqual(data["recommendation"], "Batch processed successfully. Invoices are ready for filing.")

        # 2. Test batch upload with a mix of success and failure
        def side_effect_extract(file_path):
            if "fail" in file_path:
                raise ValueError("OCR extraction failed")
            return "inv text"

        with patch("services.batch_processor.extract_text_from_file", side_effect=side_effect_extract) as mock_extract, \
             patch("services.batch_processor.process_invoice", return_value=mock_inv1) as mock_proc, \
             patch("google.genai.Client") as mock_gemini_client:

            mock_gen_response = mock_gemini_client.return_value.models.generate_content.return_value
            mock_gen_response.text = "Incomplete batch due to failures."

            files = [
                ("files", ("ok.pdf", b"%PDF-1.4 contents", "application/pdf")),
                ("files", ("fail.pdf", b"%PDF-1.4 contents", "application/pdf"))
            ]
            response = client.post("/batch-upload", files=files)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            self.assertTrue(data["success"])
            self.assertEqual(data["total_uploaded"], 2)
            self.assertEqual(data["processed"], 1)
            self.assertEqual(data["failed"], 1)
            self.assertEqual(len(data["failed_files"]), 1)
            self.assertEqual(data["failed_files"][0]["filename"], "fail.pdf")
            self.assertIn("OCR extraction failed", data["failed_files"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
