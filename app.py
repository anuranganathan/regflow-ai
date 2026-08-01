import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from tools.pdf_extractor import extract_text_from_pdf
from tools.invoice_extractor import process_invoice

load_dotenv()

app = FastAPI(title="RegFlow AI Compliance Backend")

# Mount frontend directory to serve CSS and JS
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """
    Serve the single-page application dashboard.
    """
    index_path = os.path.join("frontend", "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


from api.upload import router as upload_router
app.include_router(upload_router)
app.include_router(upload_router, prefix="/api")

from api.history import router as history_router
app.include_router(history_router)
app.include_router(history_router, prefix="/api")

from api.dashboard import router as dashboard_router
app.include_router(dashboard_router)
app.include_router(dashboard_router, prefix="/api")

from api.batch_upload import router as batch_upload_router
app.include_router(batch_upload_router)
app.include_router(batch_upload_router, prefix="/api")





