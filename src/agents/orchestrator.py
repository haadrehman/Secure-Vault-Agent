from google.adk.agents import Agent
from google.adk.tools import AgentTool
from src.agents.ingestion import ingestion_agent
from src.agents.query import query_agent

# ARCHITECTURAL CHOICE: Agent-as-a-Tool
# We wrap the IngestionAgent and QueryAgent using `AgentTool` rather than sub-agent transfer.
# This ensures that the Orchestrator receives the results from the QueryAgent (including the 
# bracketed tokens) and retains conversation control. It allows the Orchestrator to execute 
# the HITL (Human-in-the-loop) safety gate and the final de-anonymization step without permanently
# passing control away to a sub-agent.
#
# We use `skip_summarization=True` for the QueryAgent to ensure its raw redacted/structured output 
# reaches the orchestrator unmodified.

orchestrator_agent = Agent(
    name="orchestrator_agent",
    model="gemini-flash-latest",
    description="The primary router and orchestrator for Sovereign Vault.",
    instruction="""You are the Sovereign Vault Orchestrator. 
Your job is to route user requests to the appropriate specialized agents using your tools.
- If the user query implies data ingestion or processing files, call the `ingestion_agent` tool.
- If the user is querying their data, call the `query_agent` tool.
- Rely on the `description` fields of your agent tools to route effectively.

When the `query_agent` returns its response, it will contain bracketed placeholders for PII (e.g., [PERSON_1]).
You must de-anonymize the response using the `token_map` stored in the session state before answering the user!""",
    tools=[
        AgentTool(ingestion_agent),
        AgentTool(query_agent, skip_summarization=True)
    ]
)
