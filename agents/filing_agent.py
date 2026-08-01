from google.adk.agents import Agent
from tools.tools import generate_filing_summary

filing_agent = Agent(
    name="filing_agent",
    model="gemini-2.0-flash",
    description="GST Filing Assistant",
    instruction="""
You are the Filing Agent. Your job is to aggregate processed invoices and generate GSTR-3B summaries.

Call the `generate_filing_summary` tool with no arguments to load all invoices stored in the session memory and calculate the consolidated taxable values and tax liabilities.
""",
    tools=[generate_filing_summary]
)