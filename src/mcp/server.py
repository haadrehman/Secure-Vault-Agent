import os
import uuid
import mcp.server.stdio
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.types as types

from src.core.redactor import PIIRedactor
from src.core.database import VaultDatabase

# The MCP server requires an async environment
mcp_server = Server("sovereign-vault-mcp")

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Initialize engines
db = VaultDatabase(workspace_dir=WORKSPACE_DIR)
redactor = PIIRedactor()

def chunk_text(text: str, chunk_size=500, overlap=100) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

@mcp_server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="ingest_document",
            description="Parses a local document, chunks it, generates embeddings, and saves to local ChromaDB.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the document file"}
                },
                "required": ["path"]
            }
        ),
        types.Tool(
            name="search_vault",
            description="Searches ChromaDB for relevant text chunks, redacts PII locally, and returns redacted results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="list_vault_documents",
            description="Lists the names of all documents currently indexed in the vault.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@mcp_server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if name == "ingest_document":
        path = arguments.get("path")
        if not path:
            raise ValueError("Path argument is required")
            
        # Path traversal safety check
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(WORKSPACE_DIR):
            raise ValueError("Security Violation: Cannot ingest files outside the workspace directory.")
            
        if not os.path.exists(abs_path):
            raise ValueError(f"File not found: {abs_path}")
            
        try:
            # Simple text parsing for now. pypdf could be used for PDFs.
            with open(abs_path, 'r', encoding='utf-8') as f: # nosemgrep: unvalidated-file-read
                content = f.read()
                
            chunks = chunk_text(content)
            filename = os.path.basename(abs_path)
            doc_id = str(uuid.uuid4())
            db.add_document_chunks(doc_id=doc_id, chunks=chunks, metadata={"filename": filename})
            return [types.TextContent(type="text", text=f"Successfully ingested {filename} into {len(chunks)} chunks.")]
        except Exception as e:
            raise ValueError(f"Failed to ingest document: {str(e)}")
            
    elif name == "search_vault":
        query = arguments.get("query")
        if not query:
            raise ValueError("Query argument is required")
            
        results = db.query_documents(query)
        if not results:
            return [types.TextContent(type="text", text="No relevant documents found.")]
            
        combined_text = "\n\n".join(results)
        
        # Redact locally
        redacted_text, token_map = redactor.redact_text(combined_text)
        
        return [types.TextContent(type="text", text=redacted_text)]
        
    elif name == "list_vault_documents":
        names = db.get_document_names()
        return [types.TextContent(type="text", text=", ".join(names) if names else "No documents found.")]
        
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="sovereign-vault-mcp",
                server_version="0.1.0",
                capabilities=mcp_server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
