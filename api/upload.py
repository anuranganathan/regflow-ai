import os
import time
from fastapi import APIRouter, UploadFile, File, HTTPException
from tools.tools import process_invoice
from tools.gst_calculator import calculate_gst_summary
from tools.compliance_checker import check_gst_compliance
from firebase.firebase_client import save_invoice, UPLOADS_DIR
from utils.pdf_reader import extract_text_from_pdf_file
from utils.image_reader import extract_text_from_image_file

router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

@router.post("/upload")
async def upload_invoice(file: UploadFile = File(...)):
    """
    POST /upload
    Accepts PDF or image uploads, saves them locally, extracts text,
    and runs the GST processing and Firestore persistence pipeline.
    """
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Supported formats: PDF, PNG, JPG, JPEG."
        )
        
    try:
        # Create uploads folder if not exists
        if not os.path.exists(UPLOADS_DIR):
            os.makedirs(UPLOADS_DIR)
            
        # Deduplicate filename: append timestamp if it already exists
        base, extension = os.path.splitext(filename)
        dest_path = os.path.join(UPLOADS_DIR, filename)
        if os.path.exists(dest_path):
            timestamp = int(time.time())
            filename = f"{base}_{timestamp}{extension}"
            dest_path = os.path.join(UPLOADS_DIR, filename)
            
        # Save file locally
        with open(dest_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        print(f"Uploaded file saved locally to: {dest_path}")
        
        # Extract text based on file type
        if ext == ".pdf":
            try:
                extracted_text = extract_text_from_pdf_file(dest_path)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Corrupt or unreadable PDF: {str(e)}")
        else:
            try:
                extracted_text = extract_text_from_image_file(dest_path)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to process image OCR: {str(e)}")
                
        if not extracted_text or not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Empty document or no readable text found.")
            
        # Call the existing process_invoice engine to extract values & run audits
        invoice_data = process_invoice(extracted_text)
        
        # Override file_path in output to point to the actual saved local file path
        invoice_data["file_path"] = f"uploads/{filename}"
        
        # Re-save to Firestore to update the file_path metadata
        save_invoice(invoice_data)
        
        # Generate GST summary and compliance output
        gst_summary = calculate_gst_summary(invoice_data)
        
        compliance = check_gst_compliance(
            gstin=invoice_data.get("gstin") or "",
            taxable_value=float(invoice_data.get("taxable_value") or 0.0),
            total_amount=float(invoice_data.get("total_amount") or 0.0)
        )
        
        return {
            "success": True,
            "filename": filename,
            "invoice": invoice_data,
            "gst_summary": gst_summary,
            "compliance": compliance
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error in upload API: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while uploading/processing the invoice: {str(e)}"
        )
