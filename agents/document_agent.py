from google.adk.agents import Agent

document_agent = Agent(
    name="document_agent",
    model="gemini-2.5-flash",
    description="Invoice Processing Agent",
    instruction="""
You extract structured information from invoices.

Always identify:
- Invoice number
- Supplier
- GSTIN
- Date
- Taxable value
- CGST
- SGST
- Total amount
"""
)