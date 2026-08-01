import os
from tools.pdf_extractor import extract_text_from_pdf

def extract_text_from_pdf_file(file_path: str) -> str:
    """
    Extracts text from a PDF file using PyMuPDF.
    If pages are scanned (low density of native text), automatically falls back to Vision or Gemini OCR.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF file not found at: {file_path}")
        
    with open(file_path, "rb") as f:
        pdf_bytes = f.read()
        
    return extract_text_from_pdf(pdf_bytes)
