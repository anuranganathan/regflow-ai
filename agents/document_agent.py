from google.adk.agents import Agent
from tools.tools import process_invoice, extract_text_from_pdf

document_agent = Agent(
    name="document_agent",
    model="gemini-2.0-flash",
    description="Invoice Processing Agent",
    instruction="""
You are the Document Agent. Your job is to extract structured JSON data from invoice files.

If you are given a PDF file path or file content, call `extract_text_from_pdf` to extract the raw text.
Then, call `process_invoice` to parse and structure the metadata.
Return the structured invoice JSON output.
""",
    tools=[process_invoice, extract_text_from_pdf]
)