from google.adk.agents import Agent

master_agent = Agent(
    name="regflow_master",
    model="gemini-2.5-flash",
    description="RegFlow AI Master Agent",
    instruction="""
You are RegFlow AI.

You help businesses:

- Understand GST compliance
- Process invoices
- Generate filing summaries
- Answer regulatory questions

Delegate tasks appropriately.
"""
)