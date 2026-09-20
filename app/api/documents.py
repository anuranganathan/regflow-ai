"""REST endpoints for GST documents.

POST /documents/upload                 upload a PDF (S3 or local) and analyse it
GET  /documents/{document_id}          upload/processing record
POST /documents/{document_id}/analyze  re-run the analysis on the stored PDF
GET  /documents/{document_id}/result   the latest compliance result

The endpoints are plain `def` (not `async def`) because the work is blocking
(PyMuPDF, boto3, Gemini); FastAPI runs them in a thread pool.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, Path, UploadFile

from app.agents.workflow import analyze_pdf
from app.config import get_settings
from app.errors import DocumentExtractionError, DocumentNotFoundError
from app.models.schemas import AnalysisResult, DocumentRecord, UploadResponse
from app.services import document_service, storage_service

router = APIRouter(prefix="/documents", tags=["documents"])

DocumentId = Path(..., pattern=r"^[0-9a-f]{32}$", description="ID returned by /documents/upload")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _analyze_and_save(record: DocumentRecord, pdf_bytes: bytes) -> AnalysisResult:
    try:
        result = analyze_pdf(pdf_bytes)
    except DocumentExtractionError as exc:
        record.status, record.error = "FAILED", exc.message
        storage_service.save_record(record)
        raise
    record.status, record.error, record.analyzed_at = "ANALYZED", None, _now()
    storage_service.save_record(record, result)
    return result


@router.post("/upload", response_model=UploadResponse, status_code=201)
def upload_document(file: UploadFile = File(..., description="GST invoice PDF")):
    filename = file.filename or "document.pdf"
    pdf_bytes = file.file.read()
    document_service.validate_pdf(filename, pdf_bytes)      # 400 if not a usable PDF

    document_id = uuid.uuid4().hex
    object_key = storage_service.build_object_key(document_id, filename)
    storage_service.save_document(object_key, pdf_bytes)    # S3 or local; 502 on failure

    record = DocumentRecord(
        document_id=document_id,
        filename=filename,
        object_key=object_key,
        storage_mode=get_settings().storage_mode,
        status="UPLOADED",
        uploaded_at=_now(),
    )
    storage_service.save_record(record)

    result = _analyze_and_save(record, pdf_bytes)
    return UploadResponse(document=record, result=result)


@router.get("/{document_id}", response_model=DocumentRecord)
def get_document(document_id: str = DocumentId):
    return storage_service.get_record(document_id)


@router.post("/{document_id}/analyze", response_model=AnalysisResult)
def analyze_document(document_id: str = DocumentId):
    record = storage_service.get_record(document_id)
    pdf_bytes = storage_service.load_document(record)       # downloads from S3 in s3 mode
    return _analyze_and_save(record, pdf_bytes)


@router.get("/{document_id}/result", response_model=AnalysisResult)
def get_result(document_id: str = DocumentId):
    result = storage_service.get_result(document_id)
    if result is None:
        raise DocumentNotFoundError(f"Document {document_id} has not been analysed yet.")
    return result
