"""MCP Facebook server (stdio transport).

Exposes one tool that any ADK agent (this pipeline, or a future commentIntel
project) can use via McpToolset + tool_filter:

    post_to_page  -> publishes a Page post linking to an article (DESTRUCTIVE)

Auth: reads the same Graph API env vars the rest of the project uses
(FACEBOOK_PAGE_ID / _PAGE_ACCESS_TOKEN / optional _API_VERSION). Because this
runs as a stdio SUBPROCESS of the agent, it inherits the agent's environment,
so no new credential plumbing is needed. The token never reaches the LLM.

Safety: post_to_page is a live, side-effecting action. The CONSUMER agent
should gate it with a before_tool_callback if needed — the server stays a
thin, reusable capability.

Run standalone to debug:
    python -m trend_agent.servers.facebook_server
"""

import json
import logging
import os
import re
import time
from dotenv import load_dotenv
load_dotenv() 
import requests
from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("FacebookMCPServer")

mcp = FastMCP("Facebook")


def _sanitize_message(text: str) -> str:
    """Make a caption safe for the Graph API form-encoded /feed POST.

    Removes characters that can trip Facebook's generic 'code 1 / reduce the
    amount of data' error: control characters and lone surrogates. Keeps normal
    Unicode (accents, etc.) but drops anything that can't encode cleanly.
    Clamps length to a feed-friendly 600 chars.
    """
    if not text:
        return ""
    # Drop control chars except newline.
    text = "".join(ch for ch in text if ch == "\n" or ord(ch) >= 32)
    # Encode round-trip to strip lone surrogates / invalid sequences.
    text = text.encode("utf-8", "ignore").decode("utf-8", "ignore")
    # Collapse 3+ blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # Facebook truncates long feed text anyway; keep it well under any limit.
    return text[:600]


@mcp.tool()
def post_to_page(message: str, link_url: str) -> str:
    """Publish a post to the configured Facebook Page.

    DESTRUCTIVE: this posts immediately to the live Page. Facebook
    auto-renders a link preview card from the URL's Open Graph tags.

    Args:
        message: The post text. Keep under ~200 characters for best feed
            engagement — a conversational hook, not a formal title.
        link_url: The URL the post links to (must be a real http(s) URL).

    Returns:
        "POSTED <url> (id: <id>)" on success, or "ERROR: <reason>".
    """
    logger.info("post_to_page: link=%s", link_url)
    page_id = os.environ.get("FACEBOOK_PAGE_ID")
    page_token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    api_version = os.environ.get("FACEBOOK_API_VERSION", "v21.0")

    if not page_id or not page_token:
        return "ERROR: Missing FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN env var"

    if not link_url or link_url.startswith("ERROR:"):
        return "ERROR: cannot post to Facebook without a valid link URL"

    # Sanitize the caption so odd characters can't trigger Facebook's generic
    # code-1 error. The link is sent separately and untouched.
    message = _sanitize_message(message)
    link_url = link_url.strip()

    endpoint = f"https://graph.facebook.com/{api_version}/{page_id}/feed"
    payload = {"message": message, "link": link_url, "access_token": page_token}

    # Up to 2 attempts: code 1 is Facebook's transient catch-all and often
    # succeeds on a quick retry.
    last_error = None
    for attempt in range(2):
        try:
            response = requests.post(endpoint, data=payload, timeout=30)
        except requests.exceptions.RequestException as e:
            logger.exception("Facebook API network error")
            return f"ERROR: Facebook API network error: {e}"

        try:
            body = response.json()
        except json.JSONDecodeError:
            return f"ERROR: Facebook API returned non-JSON: HTTP {response.status_code}"

        if response.ok:
            post_id = body.get("id")
            if not post_id:
                return f"ERROR: Facebook returned no post id; body: {body}"
            if "_" in post_id:
                suffix = post_id.split("_", 1)[1]
                post_url = f"https://www.facebook.com/{page_id}/posts/{suffix}"
            else:
                post_url = f"https://www.facebook.com/{post_id}"
            return f"POSTED {post_url} (id: {post_id})"

        fb_error = body.get("error", {})
        msg = fb_error.get("message", "unknown error")
        code = fb_error.get("code", "unknown")
        last_error = f"Facebook API error (code {code}): {msg}"
        logger.warning("post_to_page attempt %d failed: %s", attempt + 1, last_error)

        # Retry only the transient generic code-1; other codes won't self-heal.
        if code == 1 and attempt == 0:
            time.sleep(3)
            continue
        break

    return f"ERROR: {last_error}"


if __name__ == "__main__":
    mcp.run(transport="stdio")