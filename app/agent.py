from src.agents.orchestrator import orchestrator_agent

# ADK requires a top-level `root_agent` to be exported from the app module.
# The orchestrator is the entry point that routes to the specialized sub-agents.
root_agent = orchestrator_agent
