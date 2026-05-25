"""TrendResearcher — uses SerpAPI's multi-engine MCP to find a rising trend."""
import logging
import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams

from ..prompts import RESEARCHER_PROMPT
from ..tools import get_recent_blog_topics


# ---------------------------------------------------------------------------
# Logging hygiene — quiet noisy libraries AND redact the SerpAPI key
# ---------------------------------------------------------------------------
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class _RedactSerpapiKey(logging.Filter):
    """Replaces the SerpAPI key with '***SERPAPI_KEY***' in any log record."""
    def filter(self, record: logging.LogRecord) -> bool:
        key = os.environ.get("SERPAPI_KEY")
        if key:
            if isinstance(record.msg, str) and key in record.msg:
                record.msg = record.msg.replace(key, "***SERPAPI_KEY***")
            if record.args:
                record.args = tuple(
                    a.replace(key, "***SERPAPI_KEY***") if isinstance(a, str) and key in a else a
                    for a in record.args
                )
        return True


logging.getLogger().addFilter(_RedactSerpapiKey())


# ---------------------------------------------------------------------------
# Toolset — one connection to SerpAPI's MCP server
# ---------------------------------------------------------------------------
serpapi_toolset = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=f"https://mcp.serpapi.com/{os.environ['SERPAPI_KEY']}/mcp",
    ),
    tool_filter=["search"],
)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
researcher_agent = LlmAgent(
    name="trend_researcher",
    model="gemini-2.5-flash",
    description="Finds one validated rising trend across tech, AI, Google news, and Google certifications.",
    instruction=RESEARCHER_PROMPT,
    tools=[serpapi_toolset, get_recent_blog_topics],
    output_key="selected_trend",
)