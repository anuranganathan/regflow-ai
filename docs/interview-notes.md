# RegFlow AI: interview notes

Short answers tied to the actual code. File references point to where each answer lives.

**1. Why AWS S3?**
PDFs are files, not rows, and S3 is built for storing files. It is durable (designed for 11 nines), cheap, has no disk to manage, and any number of app instances can read the same object. See `app/services/s3_service.py`.

**2. Why not store PDFs on the application server?**
A container's disk is lost when it is replaced, and two servers behind a load balancer would each see different files. With S3 the server is stateless, so any instance can handle any request. Local disk is still available as `STORAGE_MODE=local` for development only.

**3. What is boto3?**
The AWS SDK for Python. I create an S3 client with `boto3.client("s3", region_name=...)` and call `put_object` to upload and `get_object` to download. Errors arrive as `ClientError` / `BotoCoreError`, and I convert them to a `StorageError` (HTTP 502).

**4. How does FastAPI interact with S3?**
`POST /documents/upload` reads the uploaded bytes and validates the PDF. It builds the key `documents/<uuid>/<filename>` and calls `storage_service.save_document`, which calls `s3_service.upload_document` in S3 mode. `POST /documents/{id}/analyze` downloads the object back with `download_document`. The endpoints are sync `def`, so FastAPI runs the blocking boto3 calls in a thread pool.

**5. What is RAG?**
Retrieval-Augmented Generation: before calling the LLM, retrieve relevant text from a trusted source and put it in the prompt, so the answer is grounded in that text. Here `app/rag/retriever.py` retrieves GST rule paragraphs from `data/gst_rules/`, and `compliance_agent.py` sends them to Gemini.

**6. Why use RAG with an LLM?**
An LLM's knowledge can be outdated or wrong. GST rates changed in September 2025, for example. RAG lets me control the source of truth: update a text file and the answers change, with no retraining. It also lets me show which sources were used (`sources_used`).

**7. How do you reduce hallucinations?**
- Python does all maths and format checks, and Gemini is told they are final.
- The prompt contains only retrieved rules and says "use ONLY these rules".
- Structured JSON output checked by Pydantic.
- Citations outside the retrieved set lower confidence.
- A GSTIN or invoice number returned by Gemini must literally appear in the PDF text, or it is discarded.
- Missing values stay `None`, never defaults.
- `requires_human_review` whenever confidence is not HIGH.

**8. Why deterministic Python validation?**
Checks like "18% of 10,000 is 1,800" or "a GSTIN is 15 characters with a valid state code" have exactly one answer. Code gets them right every time, is unit-testable, and costs nothing. An LLM can make arithmetic mistakes and give different answers to the same input. I use the LLM for what code is bad at: reading messy documents and explaining rules.

**9. What is an embedding?**
A list of numbers (a vector) that represents the meaning of a text, so similar meanings give nearby vectors. I don't use embeddings: with 5 rule files, keyword matching with IDF weighting is enough and easier to debug. With thousands of documents I would switch to embeddings to catch synonyms ("ITC" vs "input tax credit").

**10. What is a vector database?**
A database that stores embeddings and quickly finds the nearest vectors to a query vector (for example pgvector, Chroma, OpenSearch). Not used here, because the knowledge base fits in memory. It would replace `GSTRuleRetriever` if the knowledge base grew.

**11. What is an LLM?**
A large language model: a neural network trained on large amounts of text to predict the next token. It can read, summarise and reason over text. Gemini is the LLM here.

**12. What is an AI agent?**
A component that takes an input, uses tools (functions, data sources, an LLM) to do one job, and passes its output on. My pipeline has three: Document Agent (PDF → fields), Compliance Agent (fields + rules → verdict), Filing Agent (verdict → GSTR-3B summary). They run in a fixed order in `app/agents/workflow.py` so behaviour is predictable. The optional ADK agent in `regflow_agent/` is the "LLM chooses the tool" kind of agent.

**13. Why Gemini?**
It supports structured JSON output against a schema, handles images (used for OCR of scanned pages), has a free tier for development, and integrates with Google ADK. All Gemini calls are in `gemini_service.py`, so the provider could be swapped in one place.

**14. How does a document move through the system?**
Upload → validate PDF (400 if bad) → save to S3 or local → record saved to `results/<id>.json` as UPLOADED → PyMuPDF extracts text (Gemini OCR for scanned pages) → Gemini extracts fields (regex if Gemini fails) → Python checks → retriever picks rules → Gemini reviews → reliability layer sets status/confidence → Filing Agent builds the GSTR-3B summary → record updated to ANALYZED with the result → JSON response.

**15. What happens if S3 fails?**
boto3 raises `ClientError` or `BotoCoreError`. `s3_service` converts it to `StorageError` and the API returns HTTP 502 with a clear message. Nothing is analysed or recorded for that upload. A test covers this (`test_s3_failure_returns_502`). At startup, `STORAGE_MODE=s3` without a bucket name stops the app with a clear error.

**16. What happens if Gemini fails?**
`gemini_service` converts any failure (quota/429, timeout, bad key, bad JSON) into `GeminiError`. The Document Agent falls back to regex extraction. The Compliance Agent skips the review and keeps the Python checks. The request still succeeds, with `llm_used: false`, `requires_human_review: true` and the reason in `review_reasons`. A test covers this (`test_gemini_failure_falls_back_to_python`).

**17. How would you scale it?**
The API is already stateless apart from the `results/` JSON files. Steps:
1. Move results to a database (e.g. DynamoDB or PostgreSQL).
2. Run several containers behind a load balancer.
3. Make processing asynchronous: upload returns immediately, a queue (SQS) triggers workers, and the client polls `GET /result`.
4. Add retries/backoff and rate limiting for Gemini.

**18. How would you secure AWS credentials?**
They are never in code or git (`.env` is git- and docker-ignored). boto3 reads them from its credential chain. The IAM user has least privilege: only `s3:PutObject` / `s3:GetObject` on `documents/*` in one bucket. The bucket blocks public access and is encrypted at rest. In production on AWS, use an IAM role (no keys at all), and keep the Gemini key in AWS Secrets Manager.

**19. Why Docker?**
The same image runs identically on my Mac and on any server, and the dependencies are pinned inside it. Secrets are injected at runtime with `--env-file`, not baked into the image, and the container runs as a non-root user.

**20. How would you deploy this to AWS?**
Not deployed in this version. The plan:
1. Push the image to Amazon ECR.
2. Run it on App Runner or ECS Fargate (or a single EC2 instance for a demo) with an IAM role that has the same S3 policy.
3. Pass `STORAGE_MODE=s3` and the bucket name as environment variables.
4. Store the Gemini key in Secrets Manager.
5. Put HTTPS in front.

---

**Possible follow-ups**
- Why IDF weighting in the retriever? Words that appear in every rule ("tax", "invoice") tell you little. Rare words ("igst", "180 days") identify the right paragraph.
- Why `temperature=0`? For extraction and review we want the same answer for the same input, not creativity.
- Why a 1-rupee tolerance? Invoices round tax to whole rupees or paise, so exact float equality would give false failures.
- Why is a missing field NEEDS_REVIEW but a wrong tax NON_COMPLIANT? A missing value might be an extraction miss, so a person should look. A wrong tax amount is proven by arithmetic.
