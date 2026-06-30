import json
from google.adk.agents import Agent
from google.adk.tools import BaseTool, ToolContext

async def extract_token_map(tool: BaseTool, args: dict, tool_context: ToolContext, tool_response: dict) -> dict | None:
    """Intercepts search_vault results, extracts token_map to state, and hides it from the LLM."""
    if tool.name == "search_vault":
        try:
            # The MCP tool returns a JSON string in 'text' (or similar based on how the tool is mapped)
            # Assuming the response is a standard dict when it comes back from the tool
            # If the tool response has a 'text' field containing JSON:
            result_str = tool_response.get("text", "")
            if result_str:
                data = json.loads(result_str)
                token_map = data.get("token_map", {})
                
                # Store the token_map in the session state via EventActions.state_delta
                tool_context.actions.state_delta = {"token_map": token_map}
                
                # We return only the redacted text so the LLM doesn't see the real values!
                return {"text": data.get("redacted_text", "")}
        except Exception:
            pass
    return None

# We define the QueryAgent here as a standard Agent.
# It will be wrapped in an AgentTool inside the Orchestrator with skip_summarization=True
# so that the raw bracketed output is passed back to the Orchestrator for de-anonymization.

from src.core.safety import hitl_tool

query_agent = Agent(
    name="query_agent",
    model="gemini-flash-latest",
    description="Queries the vault via semantic search and applies local PII redaction. Use for answering questions about the user's data.",
    instruction="""You are the Sovereign Vault Query Agent.
Your focus is executing semantic searches and formulating answers based on retrieved context.
- Use the `search_vault` MCP tool (bound via query_vault skill) to retrieve context.
- Before returning the final answer, YOU MUST use the `request_redaction_approval` tool to ask the human administrator if the redaction is acceptable. Pass the raw preview and the redacted preview.
- Formulate your answer using ONLY the retrieved chunks.
- Respect the local boundary rule (redact_doc skill): never bypass or attempt to reverse redaction placeholders (e.g., [PERSON_1]).
- Keep the bracketed tokens exactly as provided so the orchestrator can de-anonymize them later.""",
    after_tool_callback=extract_token_map,
    tools=[hitl_tool]
)
