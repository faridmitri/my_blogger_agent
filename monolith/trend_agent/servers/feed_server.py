"""MCP feed-ingestion server (stdio transport).

Exposes one named tool per feed plus a Google News search tool. ADK's
McpToolset spawns this file, discovers these tools, and each discoverer
agent is given exactly ONE of them via tool_filter — so the LLM picks a
tool, never a URL. That keeps URL choice on the trusted server side
(no hallucinated endpoints) while staying fully MCPToolset-canonical.

Reusable: the feed registry below is the only project-specific part. Another
project points McpToolset at this file and filters to the tools it wants.

Run standalone to debug:
    python -m trend_agent.servers.feed_server
"""

import logging
import urllib.parse

import feedparser
from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("FeedMCPServer")

mcp = FastMCP("RSS and News Ingestion")

# --- Feed registry: the only project-specific config -----------------------
GCP_BLOG_URL = "https://cloudblog.withgoogle.com/rss"
GCP_RELEASES_URL = "https://cloud.google.com/feeds/gcp-release-notes.xml"
GCP_LEARNING_URL = "https://cloudblog.withgoogle.com/topics/training-certifications/rss/"


def _parse_feed(url: str, max_items: int) -> str:
    """Core logic to parse any RSS feed (private helper, not an MCP tool)."""
    try:
        feed = feedparser.parse(url)
        if not feed.entries:
            return f"No articles found at {url}."

        result_lines = [f"Feed: {feed.feed.get('title', 'Unknown')}"]
        for i, entry in enumerate(feed.entries[:max_items], 1):
            title = entry.get("title", "No Title")
            link = entry.get("link", "No Link")
            date = entry.get("published", "Unknown Date")
            result_lines.append(f"\n{i}. {title}\n   Date: {date}\n   Link: {link}")
        return "\n".join(result_lines)
    except Exception as e:
        logger.error(f"Error parsing {url}: {e}")
        return f"Error reading feed: {str(e)}"


# --- One named tool per feed. The LLM picks a tool; the URL stays here. -----
@mcp.tool()
def read_gcp_blog(max_items: int = 5) -> str:
    """Read the latest posts from the official Google Cloud blog."""
    logger.info("read_gcp_blog")
    return _parse_feed(GCP_BLOG_URL, max_items)


@mcp.tool()
def read_gcp_releases(max_items: int = 5) -> str:
    """Read the latest entries from the Google Cloud release-notes feed."""
    logger.info("read_gcp_releases")
    return _parse_feed(GCP_RELEASES_URL, max_items)


@mcp.tool()
def read_gcp_learning(max_items: int = 5) -> str:
    """Read the latest items from the Google Cloud Training & Certifications feed."""
    logger.info("read_gcp_learning")
    return _parse_feed(GCP_LEARNING_URL, max_items)


@mcp.tool()
def search_google_news(query: str, max_items: int = 5) -> str:
    """Search Google News for a topic over the last 24 hours.

    Args:
        query: A simple search term (e.g., "Agentic AI", "Google Cloud").
        max_items: How many results to return.
    """
    logger.info(f"search_google_news: {query}")
    encoded = urllib.parse.quote(f"{query} when:24h")
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    return _parse_feed(url, max_items)


if __name__ == "__main__":
    mcp.run(transport="stdio")