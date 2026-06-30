# Sovereign Vault - Secure AI Concierge Agent

Sovereign Vault is a privacy-first Concierge Agent designed to help users interact with their highly sensitive personal documents (tax forms, medical records, legal contracts) without leaking Personally Identifiable Information (PII) to cloud AI models. By implementing a strict local boundary using local ChromaDB and Presidio-based tokenization, the agent seamlessly intercepts, redacts, and restores PII locally. The LLM processes queries securely using surrogate tokens (e.g., `[PERSON_1]`), ensuring maximum data privacy.

## Architecture Overview

The system runs on the **Google ADK 2.0 (a2a)** framework and employs a strict triad of specialized agents:
- **OrchestratorAgent**: The entry coordinator running in an Agent-as-a-Tool pattern. It routes queries dynamically and maintains full conversational context.
- **IngestionAgent**: A strict, sandboxed agent that validates file paths and ingests local documents securely into a local vector database.
- **QueryAgent**: Responsible for answering user questions. It performs semantic search locally and ensures all PII is redacted before the prompt hits the cloud.

The agents interface with local capabilities via a custom **Model Context Protocol (MCP)** Server (`src/mcp/server.py`). The MCP server exposes tools like `ingest_document` and `search_vault`, strictly isolating data parsing and vector database (ChromaDB) access from the LLM logic.

## Setup Instructions

1. **Python Environment**: Ensure you are using Python 3.12+.
2. **Install Dependencies**: We use `uv` for lightning-fast package management.
   ```bash
   uv pip install "google-adk[a2a]" chromadb presidio-analyzer pydantic pytest
   ```
3. **Environment Variables**: Create a `.env` file in the root directory and add your API keys. **Note: No API keys or secrets are committed to this repository.** The `.env` file is explicitly ignored in `.gitignore`.
   ```bash
   GEMINI_API_KEY="your_api_key_here"
   ```
4. **Run the Project**: The verified, direct launch command for our specialized agent runner is:
   ```bash
   uv run python src/main.py
   ```

## Testing

To run the full Red/Blue/Green security test suite:
```bash
uv run pytest tests/
```

## Security Design

This project strictly adheres to Day 4's Red/Blue/Green triad security guidelines for AI agents:
- **Local-Only PII Redaction**: Microsoft Presidio runs locally within the MCP server boundary, ensuring PII is stripped out *before* the data payload leaves your machine.
- **Zero-Leakage Boundary**: The `QueryAgent` is restricted to using bracketed placeholder tokens (e.g., `[US_SSN_1]`). The token mapping never enters the LLM's context window.
- **Human-in-the-Loop (HITL) Gate**: All redactions require manual confirmation. A `LongRunningFunctionTool` pauses execution, displaying the raw vs. redacted payload for explicit human approval before the LLM can generate a response.
- **Path Traversal Guards**: The MCP server strictly validates that any ingested document path resolves within the explicit `WORKSPACE_DIR`. Any attempt to access `/etc/passwd` or outside folders is blocked.
- **Fallback Resilience**: A local `ollama` model (`gemma2:2b`) is configured to seamlessly take over if cloud inference fails or rate limits are reached, emitting OpenTelemetry telemetry warnings.
