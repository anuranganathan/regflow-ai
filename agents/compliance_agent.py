from google.adk.agents import Agent
from tools.compliance_checker import check_gst_compliance
from tools.gst_calculator import calculate_gst_summary

compliance_agent = Agent(
    name="compliance_agent",
    model="gemini-3.5-flash",
    description="GST Compliance Auditor",
    instruction="""
You are the Compliance Agent. Your job is to deterministically audit GST invoices.

You MUST call the following tools to validate compliance:
- Call `check_gst_compliance` to verify the GSTIN format and structure.
- Call `calculate_gst_summary` to verify that the CGST/SGST tax math is correct.

Do not try to guess or do the math yourself. Always rely on these python tools.
Report any compliance issues or discrepancies found.
""",
    tools=[check_gst_compliance, calculate_gst_summary]
)
