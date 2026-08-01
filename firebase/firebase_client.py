import os
import json
import shutil
import uuid
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Global state
db = None
FIREBASE_INITIALIZED = False

# Path to firebase keys
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "firebase-key.json")
UPLOADS_DIR = "uploads"
LOCAL_DB_PATH = os.path.join(UPLOADS_DIR, "invoices_db.json")


def load_local_db() -> dict:
    if not os.path.exists(LOCAL_DB_PATH):
        return {}
    try:
        with open(LOCAL_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_local_db(data: dict):
    if not os.path.exists(UPLOADS_DIR):
        os.makedirs(UPLOADS_DIR)
    try:
        with open(LOCAL_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving to local DB fallback: {e}")


# 1. Initialize Firebase Admin SDK
try:
    if os.path.exists(CREDENTIALS_PATH):
        cred = credentials.Certificate(CREDENTIALS_PATH)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        FIREBASE_INITIALIZED = True
        print(f"Firebase Admin SDK initialized successfully from certificate: {CREDENTIALS_PATH}")
    else:
        # Check environment variable fallback
        fallback_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if fallback_path and os.path.exists(fallback_path):
            cred = credentials.Certificate(fallback_path)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            db = firestore.client()
            FIREBASE_INITIALIZED = True
            print(f"Firebase Admin SDK initialized from GOOGLE_APPLICATION_CREDENTIALS fallback: {fallback_path}")
        else:
            print(f"Warning: Firebase credentials file not found at '{CREDENTIALS_PATH}' and no GOOGLE_APPLICATION_CREDENTIALS fallback. Firebase persistence will be bypassed.")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")


# 2. Local Storage upload function
def save_uploaded_file(file_source: str) -> str:
    """
    Saves the file or raw text locally in the 'uploads/' directory.
    Does NOT upload to Firebase Storage as per the billing plan rules.

    Args:
        file_source: A path to a local file, or a block of raw invoice text.

    Returns:
        The relative path 'uploads/<filename>' of the saved file.
    """
    # Ensure uploads directory exists
    if not os.path.exists(UPLOADS_DIR):
        os.makedirs(UPLOADS_DIR)
        print(f"Created local uploads folder at: {os.path.abspath(UPLOADS_DIR)}")

    # Check if the source is an existing local file path
    if os.path.isfile(file_source):
        filename = os.path.basename(file_source)
        dest_path = os.path.join(UPLOADS_DIR, filename)
        
        # Avoid self-copying if it is already in uploads
        if os.path.abspath(file_source) != os.path.abspath(dest_path):
            shutil.copy2(file_source, dest_path)
            print(f"Copied local invoice file to: {dest_path}")
        return f"uploads/{filename}"
    else:
        # It's raw text content, save it to a generated .txt file
        filename = f"raw_invoice_{uuid.uuid4().hex[:8]}.txt"
        dest_path = os.path.join(UPLOADS_DIR, filename)
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(file_source)
        print(f"Saved raw invoice text to local file: {dest_path}")
        return f"uploads/{filename}"


# 3. Firestore CRUD Helpers
def save_invoice(invoice_data: dict) -> bool:
    """
    Creates or updates a document in the 'invoices' collection.
    Uses invoice_number as the document ID when available.
    Also syncs to a local JSON backup database for offline support.
    """
    doc_id = invoice_data.get("invoice_number")
    if not doc_id or doc_id == "UNKNOWN":
        doc_id = f"INV-GEN-{uuid.uuid4().hex[:8]}"

    # Save to local JSON fallback database first
    try:
        local_data = {
            "invoice_number": invoice_data.get("invoice_number") or doc_id,
            "supplier": invoice_data.get("supplier") or "UNKNOWN",
            "gstin": invoice_data.get("gstin") or "UNKNOWN",
            "taxable_value": float(invoice_data.get("taxable_value") or 0.0),
            "cgst": float(invoice_data.get("cgst") or 0.0),
            "sgst": float(invoice_data.get("sgst") or 0.0),
            "total_tax": float(invoice_data.get("total_tax") or 0.0),
            "total_amount": float(invoice_data.get("total_amount") or 0.0),
            "compliance_status": invoice_data.get("compliance_status") or "non_compliant",
            "issues": list(invoice_data.get("issues") or []),
            "file_path": invoice_data.get("file_path") or "",
            "processed_at": datetime.utcnow().isoformat(),
        }
        db_data = load_local_db()
        db_data[doc_id] = local_data
        save_local_db(db_data)
        print(f"Saved invoice {doc_id} to local offline database backup.")
    except Exception as e:
        print(f"Error saving to local fallback database: {e}")

    if not FIREBASE_INITIALIZED or db is None:
        print("Warning: Firestore is not initialized. save_invoice Firestore write skipped (using local backup).")
        return True

    try:
        doc_data = {
            "invoice_number": invoice_data.get("invoice_number") or doc_id,
            "supplier": invoice_data.get("supplier") or "UNKNOWN",
            "gstin": invoice_data.get("gstin") or "UNKNOWN",
            "taxable_value": float(invoice_data.get("taxable_value") or 0.0),
            "cgst": float(invoice_data.get("cgst") or 0.0),
            "sgst": float(invoice_data.get("sgst") or 0.0),
            "total_tax": float(invoice_data.get("total_tax") or 0.0),
            "total_amount": float(invoice_data.get("total_amount") or 0.0),
            "compliance_status": invoice_data.get("compliance_status") or "non_compliant",
            "issues": list(invoice_data.get("issues") or []),
            "file_path": invoice_data.get("file_path") or "",
            "processed_at": firestore.SERVER_TIMESTAMP,
        }
        doc_ref = db.collection("invoices").document(doc_id)
        doc_ref.set(doc_data)
        print(f"Successfully saved invoice metadata to Firestore with ID: {doc_id}")
        return True
    except Exception as e:
        print(f"Error saving invoice to Firestore: {e}. Bypassing using offline fallback database.")
        return True


def get_invoice(invoice_number: str) -> dict | None:
    """
    Returns one invoice document by its invoice number.
    Tries Firestore (with a 2s timeout), falls back to the local database on error.
    """
    if FIREBASE_INITIALIZED and db is not None:
        try:
            doc_ref = db.collection("invoices").document(invoice_number)
            doc = doc_ref.get(timeout=2.0)
            if doc.exists:
                data = doc.to_dict()
                if "processed_at" in data and hasattr(data["processed_at"], "isoformat"):
                    data["processed_at"] = data["processed_at"].isoformat()
                return data
            else:
                print(f"Invoice {invoice_number} not found in Firestore. Checking offline fallback...")
        except Exception as e:
            print(f"Error retrieving invoice from Firestore: {e}. Checking offline fallback...")

    # Fallback to local DB
    db_data = load_local_db()
    return db_data.get(invoice_number)


def list_invoices() -> list[dict]:
    """
    Returns all invoices ordered by processing timestamp.
    """
    if FIREBASE_INITIALIZED and db is not None:
        try:
            invoices_ref = db.collection("invoices")
            query = invoices_ref.order_by("processed_at", direction=firestore.Query.ASCENDING)
            results = []
            for doc in query.stream(timeout=2.0):
                data = doc.to_dict()
                if "processed_at" in data and hasattr(data["processed_at"], "isoformat"):
                    data["processed_at"] = data["processed_at"].isoformat()
                results.append(data)
            return results
        except Exception as e:
            print(f"Error listing invoices from Firestore: {e}. Using offline fallback database...")

    # Fallback to local DB
    try:
        db_data = load_local_db()
        return sorted(db_data.values(), key=lambda x: x.get("processed_at", ""))
    except Exception as e:
        print(f"Error reading local offline database: {e}")
        return []


def update_invoice_status(invoice_number: str, status: str) -> bool:
    """
    Updates the processing/compliance status of an invoice.
    """
    # Update local DB first
    try:
        db_data = load_local_db()
        if invoice_number in db_data:
            db_data[invoice_number]["compliance_status"] = status
            db_data[invoice_number]["processed_at"] = datetime.utcnow().isoformat()
            save_local_db(db_data)
            print(f"Updated invoice {invoice_number} status to {status} in offline backup DB.")
    except Exception as e:
        print(f"Error updating status in local offline DB: {e}")

    if not FIREBASE_INITIALIZED or db is None:
        return True

    try:
        doc_ref = db.collection("invoices").document(invoice_number)
        doc_ref.update({
            "compliance_status": status,
            "processed_at": firestore.SERVER_TIMESTAMP
        })
        print(f"Successfully updated invoice {invoice_number} status to: {status} in Firestore")
        return True
    except Exception as e:
        print(f"Error updating invoice status in Firestore: {e}")
        return True


def get_all_invoices() -> list[dict]:
    """
    Returns all invoices ordered by processing timestamp (newest first).
    Tries Firestore (with a 2s timeout) and merges with local offline DB documents.
    """
    invoices_dict = {}

    # 1. Load from local offline DB first
    try:
        db_data = load_local_db()
        for doc_id, data in db_data.items():
            invoices_dict[doc_id] = data
    except Exception as e:
        print(f"Error reading local DB: {e}")

    # 2. Try Firestore and merge/override
    if FIREBASE_INITIALIZED and db is not None:
        try:
            invoices_ref = db.collection("invoices")
            query = invoices_ref.order_by("processed_at", direction=firestore.Query.DESCENDING)
            for doc in query.stream(timeout=2.0):
                data = doc.to_dict()
                doc_id = doc.id
                if "processed_at" in data and hasattr(data["processed_at"], "isoformat"):
                    data["processed_at"] = data["processed_at"].isoformat()
                invoices_dict[doc_id] = data
        except Exception as e:
            print(f"Firestore stream failed or timed out: {e}. Falling back to local offline DB only.")

    # 3. Sort merged invoices by processed_at descending
    try:
        return sorted(invoices_dict.values(), key=lambda x: x.get("processed_at", ""), reverse=True)
    except Exception as e:
        print(f"Error sorting merged invoices: {e}")
        return list(invoices_dict.values())



