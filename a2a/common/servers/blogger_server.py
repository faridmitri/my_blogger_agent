"""MCP Blogger server (stdio transport).

Exposes two Blogger tools that any ADK agent (this pipeline, or a future
commentIntel project) can use via McpToolset + tool_filter:

    list_recent_posts   -> recent post metadata (dedup memory; read-only)
    publish_post        -> publishes a finished post to Blogger (DESTRUCTIVE)

Auth: reads the same OAuth refresh-token env vars the rest of the project
uses (BLOGGER_CLIENT_ID / _SECRET / _REFRESH_TOKEN / _BLOG_ID). Because this
runs as a stdio SUBPROCESS of the agent, it inherits the agent's environment,
so no new credential plumbing is needed. The credentials never reach the LLM.

Safety: publish_post is a live, side-effecting action. The CONSUMER agent
should gate it with a before_tool_callback (content-policy check) per Google's
ADK guidance — the server stays a thin, reusable capability.

Run standalone to debug:
    python -m trend_agent.servers.blogger_server
"""

import logging
import os
from dotenv import load_dotenv
load_dotenv() 
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP

from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("BloggerMCPServer")

mcp = FastMCP("Blogger")

_BLOGGER_SCOPES = ["https://www.googleapis.com/auth/blogger"]


def _build_service():
    """Build an authenticated Blogger API v3 client from env-var creds.

    Raises ValueError on missing env vars so each tool's try/except can
    return a clean {"error": ...} string instead of crashing.
    """
    client_id = os.environ.get("BLOGGER_CLIENT_ID")
    client_secret = os.environ.get("BLOGGER_CLIENT_SECRET")
    refresh_token = os.environ.get("BLOGGER_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError(
            "Missing Blogger env vars: BLOGGER_CLIENT_ID, "
            "BLOGGER_CLIENT_SECRET, or BLOGGER_REFRESH_TOKEN"
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=_BLOGGER_SCOPES,
    )
    creds.refresh(Request())
    return build("blogger", "v3", credentials=creds, cache_discovery=False)


@mcp.tool()
def list_recent_posts(max_posts: int = 10) -> str:
    """List titles, labels, and dates of recently published blog posts.

    Call this BEFORE picking a new topic so you can avoid republishing
    something similar to a recent post.

    Args:
        max_posts: How many recent posts to fetch (clamped to 1-20).

    Returns:
        A formatted text list of recent posts, or an error string.
    """
    logger.info("list_recent_posts: max_posts=%s", max_posts)
    try:
        max_posts = max(1, min(int(max_posts), 20))
        blog_id = os.environ.get("BLOGGER_BLOG_ID")
        if not blog_id:
            return "ERROR: Missing BLOGGER_BLOG_ID env var"

        service = _build_service()
        response = (
            service.posts()
            .list(
                blogId=blog_id,
                maxResults=max_posts,
                orderBy="PUBLISHED",
                fetchBodies=False,
                status="LIVE",
                fields="items(title,labels,published,url)",
            )
            .execute()
        )

        items = response.get("items", [])
        if not items:
            return "No recent posts found."

        now = datetime.now(timezone.utc)
        lines = [f"Recent posts ({len(items)}):"]
        for i, item in enumerate(items, 1):
            published_str = item.get("published", "")
            try:
                days_ago = (now - datetime.fromisoformat(published_str)).days
                age = f"{days_ago}d ago"
            except (ValueError, TypeError):
                age = "date unknown"
            labels = ", ".join(item.get("labels", [])) or "none"
            lines.append(
                f"\n{i}. {item.get('title', '')}\n"
                f"   Published: {published_str} ({age})\n"
                f"   Labels: {labels}\n"
                f"   URL: {item.get('url', '')}"
            )
        return "\n".join(lines)

    except Exception as e:
        logger.exception("list_recent_posts failed")
        return f"ERROR: failed to fetch recent posts: {e!r}"


@mcp.tool()
def publish_post(
    title: str,
    html_content: str,
    cover_image_url: str,
    labels: list[str],
    meta_description: str = "",
    slug: str = "",
) -> str:
    """Publish a finished post to Blogger and return its live URL.

    DESTRUCTIVE: this publishes immediately to the live blog. The cover
    image URL is prepended to the HTML as a responsive <img> tag.

    Args:
        title: Post title, plain text (aim for 50-65 chars).
        html_content: Post body HTML (no <html>/<head>/<body> tags).
        cover_image_url: Public https URL of the cover image.
        labels: List of tag strings (e.g. ["AI", "Trends"]).
        meta_description: 140-160 char SEO summary (optional). Requires
            "Enable search description" ON in Blogger settings.
        slug: Lowercase hyphenated URL slug (optional).

    Returns:
        "PUBLISHED <url> (id: <id>)" on success, or "ERROR: <reason>".
    """
    logger.info("publish_post: title=%r", title[:60])
    try:
        blog_id = os.environ.get("BLOGGER_BLOG_ID")
        if not blog_id:
            return "ERROR: Missing BLOGGER_BLOG_ID env var"

        service = _build_service()



        # NOTE on meta_description: the Blogger API's customMetaData field does
        # NOT set a post's Search Description — Blogger ignores it for that
        # purpose. The reliable way to get a meta description into the rendered
        # page is to embed a <meta> tag in the post body itself.
        meta_html = ""
        if meta_description:
            safe_desc = meta_description.replace('"', "&quot;")
            meta_html = f'<meta name="description" content="{safe_desc}" />\n'

        cover_img_html = (
            f'<img src="{cover_image_url}" '
            f'alt="{title}" '
            f'style="width:100%;height:auto;display:block;margin-bottom:1.5em;" />'
        )
        full_html = meta_html + cover_img_html + html_content

        post_body: dict = {
            "kind": "blogger#post",
            "title": title,
            "content": full_html,
            "labels": labels or [],
        }
        
        if slug:
            clean_slug = slug.strip().strip("/").lower().replace(" ", "-")
            post_body["permalink"] = f"/{clean_slug}.html"

        result = (
            service.posts()
            .insert(blogId=blog_id, body=post_body, isDraft=False, fetchBody=False)
            .execute()
        )
        return f"PUBLISHED {result.get('url', '')} (id: {result.get('id', '')})"

    except HttpError as e:
        logger.exception("Blogger API call failed")
        return f"ERROR: Blogger API HTTP error: {e}"
    except Exception as e:
        logger.exception("Unexpected error during publish")
        return f"ERROR: unexpected error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")