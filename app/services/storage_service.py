"""Where documents and results are kept.

- PDFs: AWS S3 when STORAGE_MODE=s3, the local uploads/ folder when STORAGE_MODE=local.
- Processing records and results: one JSON file per document in results/.
  (Firestore was removed; a database is not needed for this project's size.)
"""
import json
import re
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.errors import DocumentNotFoundError, StorageError
from app.models.schemas import AnalysisResult, DocumentRecord
from app.services import s3_service


def build_object_key(document_id: str, filename: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name) or "document.pdf"
    return f"documents/{document_id}/{safe_name}"


# ---------- documents (PDF bytes) ----------

def save_document(object_key: str, file_bytes: bytes) -> None:
    settings = get_settings()
    if settings.storage_mode == "s3":
        s3_service.upload_document(file_bytes, object_key)
        return
    path = settings.local_upload_dir / object_key
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_bytes)
    except OSError as exc:
        raise StorageError(f"Could not save the document locally: {exc}") from exc


def load_document(record: DocumentRecord) -> bytes:
    # Read from wherever the document was stored when it was uploaded
    if record.storage_mode == "s3":
        return s3_service.download_document(record.object_key)
    path = get_settings().local_upload_dir / record.object_key
    if not path.exists():
        raise DocumentNotFoundError(f"Stored file for document {record.document_id} is missing.")
    return path.read_bytes()


# ---------- records and results (local JSON) ----------

def _record_path(document_id: str) -> Path:
    return get_settings().results_dir / f"{document_id}.json"


def _read(document_id: str) -> dict:
    path = _record_path(document_id)
    if not path.exists():
        raise DocumentNotFoundError(f"Document {document_id} not found.")
    return json.loads(path.read_text(encoding="utf-8"))


def _write(document_id: str, data: dict) -> None:
    path = _record_path(document_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        raise StorageError(f"Could not save the processing record: {exc}") from exc


def save_record(record: DocumentRecord, result: Optional[AnalysisResult] = None) -> None:
    data = {"document": record.model_dump()}
    if result is not None:
        data["result"] = result.model_dump()
    elif _record_path(record.document_id).exists():
        # keep a previous result when only the record changes
        previous = _read(record.document_id).get("result")
        if previous is not None:
            data["result"] = previous
    _write(record.document_id, data)


def get_record(document_id: str) -> DocumentRecord:
    return DocumentRecord(**_read(document_id)["document"])


def get_result(document_id: str) -> Optional[AnalysisResult]:
    result = _read(document_id).get("result")
    return AnalysisResult(**result) if result else None
