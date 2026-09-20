# RegFlow AI: GST Document Compliance Assistant

RegFlow AI checks Indian GST invoice PDFs for compliance. You upload a PDF, it is stored in **AWS S3**, **PyMuPDF** extracts the text, **Python** validates the GSTIN and the tax arithmetic, a small **RAG** layer finds the relevant GST rules, and **Gemini** explains the result against those rules. The output is a structured compliance report and a GSTR-3B style summary.

> The GST rule files in `data/gst_rules/` are short summaries written for this demo. They are not legal advice. Always verify against CBIC / GST portal sources.

---

## Problem

Checking GST invoices by hand is slow and error-prone. Someone has to read each document, check that the GSTIN is valid, recalculate CGST/SGST/IGST, confirm the mandatory fields are present, and look up the rules that apply before the invoice can go into a GST return.

## Solution

RegFlow AI automates that checklist:

| Step | Done by | Why |
|---|---|---|
| Store the PDF | AWS S3 (boto3) | Durable, cheap storage outside the app server |
| Read the PDF | PyMuPDF | Fast local text extraction; Gemini OCR only for scanned pages |
| Understand the document | Gemini (structured JSON output) | Invoices have many layouts, so an LLM reads them better than fixed patterns |
| GSTIN check digit, required fields, tax maths | Plain Python | These have one correct answer. Code is exact; an LLM is not |
| Find the relevant GST rules | Keyword retriever over local rule files (RAG) | Gemini answers from trusted text instead of its memory |
| Explain the result | Gemini | Turns check results and rules into a readable explanation |
| Decide status and confidence | Python reliability layer | The LLM can flag issues but can never override the Python checks |

---

## Architecture

```text
User (browser UI or Swagger /docs)
 ↓
FastAPI  (POST /documents/upload)
 ↓
AWS S3  (or ./uploads when STORAGE_MODE=local)
 ↓
PyMuPDF  (text extraction + cleaning)          ── Document Agent
 ↓
Gemini  (read invoice fields as JSON)          ── Document Agent
 ↓
Python validation  (GSTIN, required fields, tax maths)
 ↓
RAG: retrieve GST rules from data/gst_rules/   ── Compliance Agent
 ↓
Gemini  (review invoice against retrieved rules)
 ↓
Reliability layer  (status, confidence, human review)
 ↓
GSTR-3B summary (3.1(a) sale / Table 4 ITC)    ── Filing Summary Agent
 ↓
JSON result (also saved to ./results/<document_id>.json)
```

AWS is used only for S3. There is no EC2, Lambda, SQS or database in this version.

---

## Technologies and why each one is used

| Technology | Purpose in this project |
|---|---|
| **Python 3.11** | Whole backend: agents, validation, retrieval |
| **FastAPI** | REST API with automatic request validation and Swagger docs at `/docs` |
| **REST APIs** | 4 endpoints: upload, get record, re-analyse, get result |
| **AWS S3** | Stores uploaded PDFs. Survives server restarts and scales without managing disks |
| **boto3** | AWS SDK for Python, used for `put_object` / `get_object` in `app/services/s3_service.py` |
| **Gemini** (`google-genai`) | Reads invoice fields from text, OCRs scanned pages, explains compliance using the retrieved rules |
| **Structured output** | Gemini returns JSON matching a Pydantic model (`InvoiceData`, `LLMReview`), not free text |
| **RAG** | `app/rag/retriever.py` finds relevant paragraphs in `data/gst_rules/*.txt` and puts them in the prompt |
| **PyMuPDF** | Extracts text from digital PDFs locally, with no API cost |
| **Pydantic** | Typed models for API responses and Gemini output |
| **Google ADK** | Optional chat agent (`regflow_agent/`) that calls the same Python tools. Not used by the API |
| **Docker** | Same runtime on any machine: `docker build` + `docker run` |
| **pytest** | Tests with AWS and Gemini mocked, so they run offline |

---

## Project structure

```text
regflow-ai/
├── app/
│   ├── main.py                    # FastAPI app, error handler, serves the UI
│   ├── config.py                  # environment variables (STORAGE_MODE, S3, Gemini)
│   ├── errors.py                  # exceptions → HTTP status codes
│   ├── api/
│   │   └── documents.py           # the 4 REST endpoints
│   ├── agents/
│   │   ├── workflow.py            # Document → Compliance → Filing, in a fixed order
│   │   ├── document_agent.py      # PDF → text → invoice fields (Gemini, regex fallback)
│   │   ├── compliance_agent.py    # Python checks + RAG + Gemini review + reliability layer
│   │   └── filing_agent.py        # GSTR-3B Table 3.1(a) style summary
│   ├── services/
│   │   ├── s3_service.py          # upload_document / download_document (boto3)
│   │   ├── storage_service.py     # local vs S3 switch; results saved as JSON files
│   │   ├── document_service.py    # PDF validation, PyMuPDF extraction, text cleaning
│   │   ├── compliance_service.py  # deterministic GST validation (no LLM)
│   │   └── gemini_service.py      # all Gemini calls (structured JSON, OCR)
│   ├── rag/
│   │   └── retriever.py           # keyword + IDF retriever over data/gst_rules
│   └── models/
│       └── schemas.py             # Pydantic models
├── data/
│   ├── gst_rules/                 # the knowledge base (8 short .txt files)
│   └── sample_invoices/           # 4 PDFs to try: compliant, wrong tax,
│                                  #   wrong tax type, mistyped GSTIN
├── frontend/                      # single-page upload UI served at /
├── regflow_agent/agent.py         # optional Google ADK chat agent
├── tests/                         # pytest (AWS + Gemini mocked)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt               # runtime dependencies
├── requirements-dev.txt           # + pytest, httpx
└── .env.example
```

---

## API

| Method | Path | What it does |
|---|---|---|
| `POST` | `/documents/upload` | Validate the PDF, store it (S3 or local), run the full workflow, return the record and the result |
| `GET` | `/documents/{document_id}` | Upload/processing record (file name, S3 key, status, timestamps) |
| `POST` | `/documents/{document_id}/analyze` | Download the stored PDF again (from S3 in S3 mode) and re-run the workflow |
| `GET` | `/documents/{document_id}/result` | The latest saved result |

Interactive docs: http://localhost:8000/docs

Example `compliance` block from a result:

```json
{
  "status": "COMPLIANT",
  "confidence": "HIGH",
  "gstin_valid": true,
  "tax_amount_valid": true,
  "issues": [],
  "recommendations": [],
  "explanation": "The invoice includes the mandatory Rule 46 fields and the 18% tax is correctly split into CGST and SGST.",
  "sources_used": ["gst_invoice_rules.txt", "gst_rates.txt"],
  "requires_human_review": false,
  "review_reasons": [],
  "llm_used": true,
  "checks": [
    {"name": "required_fields", "passed": true, "message": "All required fields are present."},
    {"name": "tax_amount", "passed": true, "message": "Tax charged 1800.0 matches expected 1800.0 (18.0% of 10000.0)."}
  ]
}
```

### Errors

| Situation | HTTP | Response |
|---|---|---|
| Not a PDF, empty, corrupt, encrypted, > 10 MB | 400 | `{"detail": "The file is not a valid PDF."}` |
| Unknown document id | 404 | `{"detail": "Document ... not found."}` |
| PDF has no readable text (scanned and no Gemini key) | 422 | `{"detail": "No readable text was found ..."}` |
| S3 upload/download fails (bad credentials, no bucket, network) | 502 | `{"detail": "Could not upload the document to S3: ..."}` |
| `STORAGE_MODE=s3` without `S3_BUCKET_NAME` | app refuses to start | clear error in the log |
| Gemini fails (quota, network, bad key) | **200/201** | Falls back to regex extraction and Python-only checks. Result has `llm_used: false`, `requires_human_review: true` |
| Invalid GST data (bad GSTIN, wrong tax) | 201 | Not an error: `status: "NON_COMPLIANT"` with the failed checks listed |

---

## How the result stays reliable (hallucination handling)

1. **Python does the maths and format checks.** Expected tax = taxable value × rate, CGST = SGST, total = taxable + tax, intra-state vs inter-state from the GSTIN state codes, and the GSTIN's format, state code and check digit. Gemini is told these results are final.
2. **Gemini only sees trusted rules.** The prompt contains only the retrieved rule paragraphs and says "use ONLY these rules".
3. **Citations are checked.** `sources_used` keeps only files that were actually retrieved. If Gemini cites anything else, confidence drops.
4. **Extracted identifiers are grounded.** If Gemini returns a GSTIN or invoice number that does not appear in the PDF text, it is discarded (`extraction.ungrounded_fields`).
5. **Missing values stay missing.** Nothing is filled in with defaults. A missing field gives `NEEDS_REVIEW`, not a guess.
6. **The LLM cannot override Python.** Any failed Python check means `NON_COMPLIANT`. Issues raised only by Gemini give `NEEDS_REVIEW`, not a fail.
7. **Confidence and human review.** Confidence drops to MEDIUM for OCR, regex fallback, Gemini uncertainty or an unavailable LLM, and to LOW for missing fields or no rules retrieved. `requires_human_review` is true unless the status is COMPLIANT with HIGH confidence. `review_reasons` says why.

---

## Run locally (no AWS needed)

Requires Python 3.11+.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then put your Gemini key in .env (STORAGE_MODE=local)
uvicorn app.main:app --reload
```

Open http://localhost:8000 (upload UI) or http://localhost:8000/docs (Swagger).

With curl:

```bash
curl -F "file=@data/sample_invoices/sample_compliant_invoice.pdf" http://localhost:8000/documents/upload
curl http://localhost:8000/documents/<document_id>/result
```

Without `GEMINI_API_KEY` the app still works. It uses regex extraction and Python checks only, and every result is flagged for human review.

## Run with Docker

```bash
docker build -t regflow-ai .
docker run --rm -p 8000:8000 --env-file .env regflow-ai
```

Or `docker compose up --build`, which also mounts `uploads/` and `results/` so local data survives restarts.

Secrets are passed at runtime with `--env-file`. `.env` is excluded from the image by `.dockerignore` and from git by `.gitignore`.

---

## AWS S3 setup

You need an AWS account and the AWS CLI (`aws --version`) logged in as an admin user, only for this setup.

**1. Create a private bucket.** Bucket names are global, so add something unique:

```bash
export BUCKET=regflow-ai-docs-<your-name>
aws s3api create-bucket --bucket $BUCKET --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-public-access-block --bucket $BUCKET --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

New buckets already encrypt objects at rest (SSE-S3) by default.

**2. Create an IAM user with least-privilege access.** It can only read and write objects under `documents/` in this bucket:

```bash
cat > /tmp/regflow-s3-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject"],
    "Resource": "arn:aws:s3:::$BUCKET/documents/*"
  }]
}
EOF
aws iam create-user --user-name regflow-app
aws iam put-user-policy --user-name regflow-app --policy-name regflow-s3-documents \
  --policy-document file:///tmp/regflow-s3-policy.json
aws iam create-access-key --user-name regflow-app
```

**3. Give the app the credentials.** Choose one:

- **Local run:** `aws configure --profile regflow` (paste the key pair), then add `AWS_PROFILE=regflow` to `.env`.
- **Docker:** put `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env`, which is passed with `--env-file`.

**4. Switch to S3 mode** in `.env`:

```env
STORAGE_MODE=s3
AWS_REGION=ap-south-1
S3_BUCKET_NAME=regflow-ai-docs-<your-name>
```

**5. Verify.** Upload a PDF, then run `aws s3 ls s3://$BUCKET/documents/ --recursive`.

The code never reads the keys itself. boto3 finds them through its standard chain: environment variables → `~/.aws/credentials` (profile) → IAM role. On AWS you would attach an IAM role instead of using keys.

**Clean up** when you no longer need it:

```bash
aws s3 rm s3://$BUCKET --recursive && aws s3api delete-bucket --bucket $BUCKET
aws iam delete-access-key --user-name regflow-app --access-key-id <KEY_ID>
aws iam delete-user-policy --user-name regflow-app --policy-name regflow-s3-documents
aws iam delete-user --user-name regflow-app
```

---

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `STORAGE_MODE` | `local` | `local` saves PDFs in `./uploads`; `s3` uploads to S3 |
| `S3_BUCKET_NAME` | none | Required when `STORAGE_MODE=s3` |
| `AWS_REGION` | `ap-south-1` | Bucket region |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | none | Optional; read by boto3, not by the code. Or use `AWS_PROFILE` |
| `BUSINESS_GSTIN` | none | Your own GSTIN. Decides sale vs purchase; if unset every invoice is treated as a sale |
| `GEMINI_API_KEY` | none | `GOOGLE_API_KEY` is also accepted |
| `GEMINI_MODEL` | `gemini-flash-lite-latest` | Alias for the current Flash-Lite model (fast, generous free quota). `gemini-flash-latest` uses the larger model; pin a version (e.g. `gemini-3.5-flash`) for fixed behaviour |
| `MAX_UPLOAD_MB` | `10` | Upload size limit |

## Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

| File | Covers |
|---|---|
| `tests/test_gstin_validation.py` | GSTIN format, length, state codes and the check-digit algorithm |
| `tests/test_tax_calculation.py` | Expected tax, rate inference, CGST = SGST, IGST vs CGST/SGST, totals, GSTR-3B totals |
| `tests/test_document_extraction.py` | PyMuPDF extraction, invalid/scanned PDFs, text cleaning, regex fallback |
| `tests/test_filing_direction.py` | Sale vs purchase detection and the GSTR-3B table each one lands in |
| `tests/test_retriever.py` | RAG retrieval returns the right rule file |
| `tests/test_api_upload.py` | Upload in local and S3 mode (boto3 mocked), S3 failure → 502, Gemini mocked: compliant path, LLM cannot override Python, hallucinated GSTIN discarded, Gemini failure fallback |

## Optional: chat with the ADK agent

`regflow_agent/agent.py` defines one Google ADK agent. Gemini chooses between four Python tools: analyse a PDF, search GST rules, check a GSTIN, calculate GST. It reuses the API's code and is not needed to run the API.

```bash
adk run regflow_agent      # terminal chat, from the project root
```

## Limitations

- The knowledge base is eight short summaries, enough to show the RAG pattern. It is not a complete GST reference.
- Retrieval is keyword-based, which is a deliberate choice: with a handful of rule files, keyword matching with IDF weighting is accurate and easy to debug. Embeddings and a vector store would be the upgrade for a much larger knowledge base.
- The GSTIN check covers format, state code and the check digit, so typos and invented numbers are caught. It cannot tell whether a well-formed GSTIN is actually registered and active — that needs the GST portal, which has no free public API.
- Sale vs purchase is decided by matching `BUSINESS_GSTIN` against the invoice. Without it, every invoice is assumed to be a sale.
- Processing is synchronous: the upload request waits for Gemini (typically a few seconds). Fine at this scale; a queue and polling would be the change if volume grew.
- No authentication. Add it before exposing the API publicly.

See [docs/interview-notes.md](docs/interview-notes.md) for design questions and answers.
