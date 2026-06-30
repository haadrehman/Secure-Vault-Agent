import pytest
import os
import json
from unittest.mock import patch, mock_open, MagicMock

# Import the actual handlers. 
# We need to test the tools registered on the MCP server.
from src.mcp_server.server import handle_list_tools, handle_call_tool, WORKSPACE_DIR

@pytest.mark.asyncio
async def test_list_tools():
    tools = await handle_list_tools()
    tool_names = [tool.name for tool in tools]
    assert "ingest_document" in tool_names
    assert "search_vault" in tool_names
    assert "list_vault_documents" in tool_names

@pytest.mark.asyncio
@patch('src.mcp_server.server.db')
@patch('builtins.open', new_callable=mock_open, read_data="Mock document content for testing ingestion.")
@patch('os.path.exists', return_value=True)
async def test_ingest_document(mock_exists, mock_file, mock_db):
    # Test successful ingestion
    valid_path = os.path.join(WORKSPACE_DIR, "test_doc.txt")
    result = await handle_call_tool("ingest_document", {"path": valid_path})
    
    assert len(result) == 1
    assert "Successfully ingested test_doc.txt" in result[0].text
    mock_db.add_document_chunks.assert_called_once()

@pytest.mark.asyncio
@patch('src.mcp_server.server.db')
@patch('src.mcp_server.server.redactor')
async def test_search_vault(mock_redactor, mock_db):
    # Setup mocks
    mock_db.query_documents.return_value = ["Mock chunk with John Doe inside."]
    mock_redactor.redact_text.return_value = ("Mock chunk with [PERSON_1] inside.", {"[PERSON_1]": "John Doe"})
    
    result = await handle_call_tool("search_vault", {"query": "Who is John?"})
    
    assert len(result) == 1
    response_json = json.loads(result[0].text)
    
    assert "Mock chunk with [PERSON_1] inside." in response_json["redacted_text"]
    assert response_json["token_map"]["[PERSON_1]"] == "John Doe"
    mock_db.query_documents.assert_called_once_with("Who is John?")

@pytest.mark.asyncio
@patch('src.mcp_server.server.db')
async def test_list_vault_documents(mock_db):
    mock_db.get_document_names.return_value = ["doc1.txt", "doc2.txt"]
    
    result = await handle_call_tool("list_vault_documents", {})
    
    assert len(result) == 1
    assert "doc1.txt" in result[0].text
    assert "doc2.txt" in result[0].text
