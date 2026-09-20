"""RegFlow AI - FastAPI entry point.

Run locally:  uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.documents import router as documents_router
from app.config import BASE_DIR, get_settings, validate_settings
from app.errors import RegFlowError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    validate_settings(settings)  # stop at startup if e.g. S3 mode has no bucket name
    logging.getLogger("regflow").info(
        "Starting RegFlow AI (storage=%s, gemini=%s)",
        settings.storage_mode, "on" if settings.gemini_enabled else "off",
    )
    yield


app = FastAPI(
    title="RegFlow AI",
    description="GST document compliance: FastAPI + AWS S3 + PyMuPDF + RAG + Gemini",
    version="2.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RegFlowError)
async def handle_regflow_error(_: Request, exc: RegFlowError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(documents_router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
