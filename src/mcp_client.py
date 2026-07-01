import os
import sys
import shutil
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MCP_SERVER_SCRIPT = os.path.join(WORKSPACE_DIR, "src", "mcp_server", "server.py")

if shutil.which("uv"):
    # Use full uv run python to inherit the correct virtual environment and dependencies
    command = "uv"
    args = ["run", "python", "-m", "src.mcp_server.server"]
else:
    # Fallback to sys.executable which points to the currently running Python interpreter
    command = sys.executable
    args = ["-m", "src.mcp_server.server"]

# Note: The installed ADK version's McpToolset API does not support async context manager 
# initialization (e.g. `async with McpToolset(...) as t`). 
# We are instantiating it directly here. For stdio, each instance spawns its own server process.
def get_mcp_toolset(tool_filter: list[str] | None = None) -> McpToolset:
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=command,
                args=args,
            )
        ),
        tool_filter=tool_filter
    )
