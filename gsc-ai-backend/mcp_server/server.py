"""
server.py

Entry point for the GSC Delivery MCP server.

Responsibilities:
  1. Redirect all logging to stderr (stdout is reserved for MCP JSON-RPC)
  2. Instantiate the FastMCP application
  3. Initialise the SQLite database inside a lifespan context
     (runs after stdio transport is set up, never before)
  4. Register all tools from the tools/ modules
  5. Start the server (stdio transport — the standard for MCP)

Run with:
    python -m mcp_server.server

Or via the MCP CLI (useful for inspection / testing):
    mcp run mcp_server/server.py

The AI Orchestrator connects to this process over stdio and discovers
available tools automatically through the MCP protocol handshake.
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# When this file is loaded directly by `mcp dev mcp_server/server.py`, the
# project root (gsc-ai-backend/) is not on sys.path, so package-relative
# imports like `from mcp_server.database.connection import ...` would fail.
# Inserting the project root ensures the server is importable both ways:
#   python -m mcp_server.server   (normal module invocation)
#   mcp dev mcp_server/server.py  (MCP CLI / inspector)
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP

from mcp_server.database.connection import init_db
from mcp_server.tools import driver, stops, products

# ---------------------------------------------------------------------------
# Logging — must be stderr only.
# The MCP stdio transport owns stdout; anything else written there is
# received by the client as a broken JSON-RPC message.
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

# ---------------------------------------------------------------------------
# Lifespan — database initialisation
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app):
    """
    Runs init_db() inside the MCP event loop, after the stdio transport
    is fully set up. This ensures SQLite never touches stdout during the
    critical period before the JSON-RPC handshake completes.
    """
    init_db()
    yield

# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

# The name is sent to the AI client during the MCP handshake and appears
# in logs — keep it descriptive.
mcp = FastMCP("GSC Delivery MCP Server", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

# Each module's register() function decorates its tools with @mcp.tool()
# and attaches them to this FastMCP instance.

driver.register(mcp)    # get_driver_profile
stops.register(mcp)     # get_stops_for_driver, get_stop_details
products.register(mcp)  # get_products, reconcile_inventory

# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # mcp.run() defaults to stdio transport, which is what AI orchestrators
    # expect when spawning an MCP server as a subprocess.
    mcp.run()
