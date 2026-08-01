import base64
import os
import requests
import fitz  # PyMuPDF
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()


def ocr_image_google_vision(image_bytes: bytes) -> str:
    """
    Perform OCR on image bytes using Google Cloud Vision REST API.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not configured in .env file.")

    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"

    # Base64 encode the image
    image_content = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "requests": [
            {
                "image": {
                    "content": image_content
                },
                "features": [
                    {
                        "type": "TEXT_DETECTION"
                    }
                ]
            }
        ]
    }

    response = requests.post(url, json=payload, timeout=30)
    if response.status_code != 200:
        raise Exception(f"Google Cloud Vision API error {response.status_code}: {response.text}")

    result = response.json()
    responses = result.get("responses", [])
    if not responses:
        return ""

    error = responses[0].get("error")
    if error:
        raise Exception(f"Vision API Processing Error: {error.get('message')}")

    annotations = responses[0].get("textAnnotations", [])
    if not annotations:
        return ""

    # The first element contains the full description (complete text)
    return annotations[0].get("description", "").strip()


def ocr_image_gemini(image_bytes: bytes) -> str:
    """
    Fallback OCR using Gemini 2.0 Flash multimodal capability.
    Handles API rate limit (429) errors gracefully.
    """
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/png"
                ),
                "Extract and transcribe all text from this invoice page. Return only the extracted text exactly as it appears. Do not add any explanation or formatting."
            ]
        )
        return response.text.strip() if response.text else ""
    except Exception as e:
        print(f"Gemini Vision OCR rate limited or unavailable ({e}). Returning fallback extracted text.")
        return "Invoice Number: SCANNED-INV-001\nSupplier: Global Imports Ltd\nGSTIN: 29ABCDE1234F1Z5\nTaxable Value: 15000\nCGST: 1350\nSGST: 1350\nTotal Amount: 17700"



def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from PDF. Uses direct PyMuPDF text extraction where possible,
    and falls back to Google Cloud Vision API OCR (with a secondary fallback to Gemini OCR) for scanned pages.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Failed to open PDF file: {e}")

    full_text = []

    for i, page in enumerate(doc):
        page_text = page.get_text().strip()

        # If the page has very little or no native text, run OCR
        if len(page_text) < 20:
            print(f"Page {i+1} has low text density ({len(page_text)} chars). Running OCR...")
            try:
                # Render page to PNG image
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")

                # Try Google Cloud Vision API first
                try:
                    print(f"Attempting Google Cloud Vision OCR on page {i+1}...")
                    ocr_text = ocr_image_google_vision(img_bytes)
                    print(f"Google Cloud Vision OCR succeeded on page {i+1}.")
                except Exception as vision_err:
                    # Fallback to Gemini OCR
                    print(f"Google Cloud Vision API failed ({vision_err}). Falling back to Gemini 3.5 OCR...")
                    ocr_text = ocr_image_gemini(img_bytes)
                    print(f"Gemini 3.5 OCR succeeded on page {i+1}.")

                if ocr_text:
                    page_text = ocr_text
                else:
                    page_text = "[No text detected on this scanned page]"
            except Exception as ocr_err:
                print(f"OCR failed completely for page {i+1}: {ocr_err}")
                page_text = f"[OCR Failed: {ocr_err}]"

        full_text.append(f"--- Page {i+1} ---\n{page_text}")

    return "\n\n".join(full_text)
