import os
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from services.batch_processor import BatchProcessingService

router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

@router.post("/batch-upload")
async def batch_upload_invoices(files: List[UploadFile] = File(...)):

    """
    POST /batch-upload
    Accepts a list of PDF or image invoices, processes them concurrently
    (maximum 3 at once), saves metadata to Firestore, compiles GSTR-3B summary,
    and returns a consolidated ADK-generated recommendation response.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided in upload request.")
        
    # Validate file formats first
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{ext}' in file '{file.filename}'. Supported: PDF, PNG, JPG, JPEG."
            )
            
    try:
        # Trigger batch processor service
        response = await BatchProcessingService.process_batch(files)
        return response
    except Exception as e:
        print(f"Error in GET /batch-upload endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during batch processing: {str(e)}"
        )
