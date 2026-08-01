import os
import io
from PIL import Image
from tools.pdf_extractor import ocr_image_google_vision, ocr_image_gemini

def extract_text_from_image_file(file_path: str) -> str:
    """
    Extracts text from an image file using OCR.
    Tries Google Cloud Vision API first, falling back to Gemini OCR.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Image file not found at: {file_path}")
        
    try:
        with Image.open(file_path) as img:
            # Convert to PNG format in bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
    except Exception as e:
        raise ValueError(f"Failed to open or process image file: {e}")
        
    # Try Google Vision OCR first, fallback to Gemini OCR if it fails or returns empty
    try:
        text = ocr_image_google_vision(img_bytes)
        if text and text.strip():
            return text.strip()
    except Exception as e:
        print(f"Vision OCR failed, falling back to Gemini OCR: {e}")
        
    return ocr_image_gemini(img_bytes).strip()
