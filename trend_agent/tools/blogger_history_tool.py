"""
trend_agent/tools/blogger_history_tool.py

Blogger-as-memory tool.

Returns the most recently published posts from our Blogger blog so the
researcher can avoid repeating itself. Reuses the same OAuth refresh
token already in .env for blogger_tool.py — no new credentials needed.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def _build_blogger_service():
    """Build an authenticated Blogger API v3 client.

    Same auth pattern as blogger_tool.py — refresh-token flow, no
    interactive consent needed at runtime.
    """
    creds = Credentials(
        token=None,
        refresh_token=os.environ["BLOGGER_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["BLOGGER_CLIENT_ID"],
        client_secret=os.environ["BLOGGER_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/blogger"],
    )
    creds.refresh(Request())
    return build("blogger", "v3", credentials=creds, cache_discovery=False)


def get_recent_blog_topics(max_posts: int = 10) -> dict:
    """Return titles and labels of recently published blog posts.

    Call this BEFORE picking a new trend. If a candidate trend's topic
    clearly overlaps with one of these recent posts (same subject or
    heavily-shared keywords), skip it and pick a different trend.
    This prevents publishing near-duplicate content.

    Args:
        max_posts: How many recent posts to fetch. Clamped to 1..20.

    Returns:
        On success:
            {
                "recent_posts": [
                    {
                        "title": "...",
                        "labels": ["ai", "google"],
                        "published": "2026-05-20T10:00:00-07:00",
                        "days_ago": 3,
                        "url": "https://yourblog.blogspot.com/..."
                    },
                    ...
                ],
                "count": <int>
            }
        On error:
            {"error": "<message>"}
    """
    try:
        # Clamp to a sane range so the LLM can't ask for 5000 posts.
        max_posts = max(1, min(int(max_posts), 20))

        service = _build_blogger_service()

        response = (
            service.posts()
            .list(
                blogId=os.environ["BLOGGER_BLOG_ID"],
                maxResults=max_posts,
                orderBy="PUBLISHED",       # newest first
                fetchBodies=False,         # we only need metadata
                status="LIVE",             # skip drafts
                fields="items(title,labels,published,url)",
            )
            .execute()
        )

        items = response.get("items", [])
        now = datetime.now(timezone.utc)

        recent_posts = []
        for item in items:
            published_str = item.get("published", "")
            # Blogger returns RFC 3339 with offset, e.g. "2026-05-20T10:00:00-07:00".
            # Python 3.11+ fromisoformat handles this natively.
            try:
                published_dt = datetime.fromisoformat(published_str)
                days_ago = (now - published_dt).days
            except (ValueError, TypeError):
                days_ago = -1  # unknown; researcher should still see the title

            recent_posts.append({
                "title": item.get("title", ""),
                "labels": item.get("labels", []),
                "published": published_str,
                "days_ago": days_ago,
                "url": item.get("url", ""),
            })

        return {"recent_posts": recent_posts, "count": len(recent_posts)}

    except Exception as e:
        # FunctionTool convention from your handoff: never raise, always
        # return a dict with an "error" key. Uncaught exceptions crash
        # the agent loop.
        return {"error": f"Failed to fetch recent blog topics: {e!r}"}