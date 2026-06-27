from google.adk.agents import Agent

filing_agent = Agent(
    name="filing_agent",
    model="gemini-2.5-flash",
    description="GST Filing Assistant",
    instruction="""
You help Indian businesses prepare GST filing summaries.

You can:
- Explain GST calculations
- Summarize GST obligations
- Help prepare filing drafts
"""
)