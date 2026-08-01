import os
from utils.pdf_reader import extract_text_from_pdf_file
from utils.image_reader import extract_text_from_image_file

def extract_text_from_file(file_path: str) -> str:
    """
    Extracts text from a PDF or image file by routing to the appropriate reader.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf_file(file_path)
    elif ext in {".png", ".jpg", ".jpeg"}:
        return extract_text_from_image_file(file_path)
    else:
        raise ValueError(f"Unsupported file format '{ext}'")
