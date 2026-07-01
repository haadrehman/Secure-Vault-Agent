from google.adk.agents import Agent

# We define the IngestionAgent here as a standard Agent. 
# It will be wrapped in an AgentTool inside the Orchestrator 
# to ensure the Orchestrator retains conversation control instead of doing a sub-agent transfer.

from src.mcp_client import get_mcp_toolset

ingestion_agent = Agent(
    name="ingestion_agent",
    model="gemini-flash-latest",
    description="Handles ingesting new documents into the vault: validates file paths, chunks text, and stores embeddings. Use for requests about adding, scanning, or processing new files.",
    instruction="""You are the Sovereign Vault Ingestion Agent.
Your exclusive focus is on folder parsing, validation, and invoking the local `ingest_document` MCP tool (bound via the ingest_doc skill).
- Validate that the file path is absolute and within the workspace boundary before processing.
- Do not attempt to read files from /tmp, /etc, or outside the designated project folder.
- Execute the ingestion pipeline safely without leaking raw data.""",
    tools=[get_mcp_toolset(tool_filter=["ingest_document", "list_vault_documents"])]
)
