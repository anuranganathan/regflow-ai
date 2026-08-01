import os
import time
import json
import asyncio
import logging
from fastapi import UploadFile
from google import genai
from tools.tools import process_invoice, generate_filing_summary
from firebase.firebase_client import save_invoice, UPLOADS_DIR
from utils.batch_utils import extract_text_from_file

logger = logging.getLogger("regflow.batch_processor")

class BatchProcessingService:
    @staticmethod
    def save_uploaded_file_sync(file: UploadFile) -> str:
        """
        Saves an uploaded file to the local uploads directory.
        If a duplicate filename exists, appends an epoch timestamp.
        """
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()
        base = os.path.splitext(filename)[0]
        
        if not os.path.exists(UPLOADS_DIR):
            os.makedirs(UPLOADS_DIR, exist_ok=True)
            
        dest_path = os.path.join(UPLOADS_DIR, filename)
        if os.path.exists(dest_path):
            timestamp = int(time.time())
            filename = f"{base}_{timestamp}{ext}"
            dest_path = os.path.join(UPLOADS_DIR, filename)
            
        # Write bytes synchronously (executed in thread pool)
        with open(dest_path, "wb") as f:
            f.write(file.file.read())
            
        logger.info(f"Upload completed: saved {filename} to {dest_path}")
        return dest_path

    @classmethod
    async def process_single_file(cls, file: UploadFile, semaphore: asyncio.Semaphore) -> dict:
        """
        Processes a single file: uploads, extracts text, audits compliance,
        and saves result to Firestore.
        """
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()
        
        if ext not in {".pdf", ".png", ".jpg", ".jpeg"}:
            raise ValueError(f"Unsupported file extension '{ext}'")
            
        async with semaphore:
            logger.info(f"Invoice processing started: {filename}")
            
            # 1. Save file locally
            saved_path = await asyncio.to_thread(cls.save_uploaded_file_sync, file)
            
            # 2. Extract text (PyMuPDF or Vision/Gemini OCR via batch_utils)
            extracted_text = await asyncio.to_thread(extract_text_from_file, saved_path)
                
            if not extracted_text or not extracted_text.strip():
                raise ValueError("Empty document or no readable text detected.")
                
            # 3. Call process_invoice (saves raw text & creates base Firestore doc)
            invoice_data = await asyncio.to_thread(process_invoice, extracted_text)
            
            # 4. Update with original file path and sync back to Firestore
            invoice_data["file_path"] = f"uploads/{os.path.basename(saved_path)}"
            await asyncio.to_thread(save_invoice, invoice_data)
            logger.info(f"Firestore save completed: {invoice_data.get('invoice_number')}")
            
            logger.info(f"Invoice processing completed: {filename}")
            return invoice_data

    @classmethod
    async def process_batch(cls, files: list[UploadFile]) -> dict:
        """
        Orchestrates batch processing of multiple uploaded invoices concurrently.
        """
        start_time = time.time()
        logger.info(f"Upload started: batch processing of {len(files)} files.")
        
        # Max concurrency: 3 invoices at once to avoid API rate limits
        semaphore = asyncio.Semaphore(3)
        
        # Create async tasks for all files
        tasks = [cls.process_single_file(file, semaphore) for file in files]
        
        # Run concurrently and collect results, allowing individual failures
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_results = []
        failed_files = []
        
        for file, result in zip(files, results):
            if isinstance(result, Exception):
                logger.error(f"Invoice processing failed for {file.filename}: {result}")
                failed_files.append({
                    "filename": file.filename,
                    "reason": str(result)
                })
            else:
                successful_results.append(result)
                
        processing_time = round(time.time() - start_time, 2)
        logger.info(f"Batch completed: {len(successful_results)} succeeded, {len(failed_files)} failed in {processing_time}s.")
        
        # Call ADK Orchestrator to generate filing summary & recommendation
        summary_response = await asyncio.to_thread(
            cls.generate_batch_summary, 
            successful_results, 
            len(files), 
            len(failed_files), 
            processing_time, 
            failed_files
        )
        
        return summary_response

    @staticmethod
    def generate_batch_summary(
        successful_results: list[dict], 
        total_uploaded: int, 
        failed_count: int, 
        processing_time: float,
        failed_files: list[dict]
    ) -> dict:
        """
        Google ADK Orchestrator logic:
        1. Invokes the existing generate_filing_summary.
        2. Leverages Gemini to formulate final compliance recommendations.
        3. Returns the consolidated response.
        """
        # Call existing filing summary generator
        filing_summary = generate_filing_summary(successful_results)
        logger.info("Summary generated: GSTR-3B filing totals aggregated.")
        
        # Formulate recommendations using Gemini (ADK Orchestrator review)
        recommendation = ""
        if len(successful_results) > 0:
            try:
                api_key = os.getenv("GOOGLE_API_KEY")
                client = genai.Client(api_key=api_key)
                
                # Expose only critical fields to model to reduce tokens
                invoices_brief = [
                    {
                        "invoice_number": inv.get("invoice_number"),
                        "supplier": inv.get("supplier"),
                        "compliance_status": inv.get("compliance_status"),
                        "issues": inv.get("issues")
                    }
                    for inv in successful_results
                ]
                
                prompt = f"""
You are the RegFlow AI Filing Agent orchestrator.
Review the following batch summary of processed invoices and GSTR-3B details.
Provide a professional, concise executive compliance recommendation (readiness for filing, highlight any audits/non-compliant items).

Invoices:
{json.dumps(invoices_brief, indent=2)}

Filing Summary:
{json.dumps(filing_summary, indent=2)}

Return ONLY your recommendation text. Keep it under 3 sentences.
"""
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
                recommendation = response.text.strip() if response.text else "No recommendation available."
            except Exception as e:
                logger.error(f"Error generating recommendation from Gemini: {e}")
                recommendation = "Could not generate recommendation due to API error."
        else:
            recommendation = "No successful invoices processed in this batch."
            
        # Format results block
        results_formatted = [
            {
                "invoice_number": inv.get("invoice_number") or "UNKNOWN",
                "supplier": inv.get("supplier") or "UNKNOWN",
                "status": inv.get("compliance_status") or "non_compliant"
            }
            for inv in successful_results
        ]
        
        response_payload = {
            "success": True,
            "total_uploaded": total_uploaded,
            "processed": len(successful_results),
            "failed": failed_count,
            "processing_time_seconds": processing_time,
            "results": results_formatted,
            "filing_summary": filing_summary,
            "recommendation": recommendation
        }
        
        if failed_count > 0:
            response_payload["failed_files"] = failed_files
            
        return response_payload
