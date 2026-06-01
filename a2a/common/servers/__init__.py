"""MCP server helpers shared by the A2A specialist agents.

Centralizes the McpToolset wiring so each consumer (researcher, publisher)
doesn't repeat the StdioConnectionParams boilerplate. Per Google's ADK docs,
toolsets are built SYNCHRONOUSLY at import time (required for deployment).

This package is the reusable "tool layer" of the system. In the A2A
architecture each specialist agent runs as its own Cloud Run service, but
they all share these same MCP servers by importing from `common.servers`.
The MCP servers themselves are spawned as stdio SUBPROCESSES of whichever
agent imports them, so credentials reach them via environment inheritance.
"""

import os
import sys
from pathlib import Path

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

_SERVERS_DIR = Path(__file__).resolve().parent

_FEED_SERVER = os.environ.get(
    "FEED_SERVER_PATH", str(_SERVERS_DIR / "feed_server.py")
)
_BLOGGER_SERVER = os.environ.get(
    "BLOGGER_SERVER_PATH", str(_SERVERS_DIR / "blogger_server.py")
)
_FACEBOOK_SERVER = os.environ.get(
    "FACEBOOK_SERVER_PATH", str(_SERVERS_DIR / "facebook_server.py")
)


def _stdio_toolset(server_path: str, tool_filter: list[str]) -> McpToolset:
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable, args=[server_path]
            ),
            timeout=60,
        ),
        tool_filter=tool_filter,
    )


def feed_toolset(tool_name: str) -> McpToolset:
    """One filtered tool from the feed server (read_gcp_* / search_google_news)."""
    return _stdio_toolset(_FEED_SERVER, [tool_name])


def blogger_toolset(tool_name: str) -> McpToolset:
    """One filtered tool from the blogger server (list_recent_posts / publish_post)."""
    return _stdio_toolset(_BLOGGER_SERVER, [tool_name])


def facebook_toolset(tool_name: str) -> McpToolset:
    """One filtered tool from the facebook server (post_to_page, and future
    comment-handling tools)."""
    return _stdio_toolset(_FACEBOOK_SERVER, [tool_name])
