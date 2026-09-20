FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# PyMuPDF ships prebuilt wheels, so no system packages are needed
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY data/ data/
COPY frontend/ frontend/

# Run as a non-root user; uploads/ and results/ are the only writable folders
RUN useradd --create-home appuser \
    && mkdir -p uploads results \
    && chown appuser:appuser uploads results
USER appuser

EXPOSE 8000

# Secrets (GEMINI_API_KEY, AWS keys) are passed at runtime with --env-file, never baked in
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
