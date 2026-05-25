"""Blogger publisher tool.

Publishes a post to Blogger via Blogger API v3 using an OAuth refresh
token. Designed to be called by an LlmAgent as a FunctionTool.

SEO fields supported:
  - meta_description -> Blogger's "Search Description" (shown under the
    title in Google search results).
  - slug             -> custom URL slug for the post. If omitted,
    Blogger auto-generates one from the title.

Note on the Search Description field:
  The Blogger blog must have "Enable search description" turned ON in
  Settings -> Meta tags, or the meta_description will be silently
  ignored. This is a one-time, per-blog toggle in the Blogger dashboard.
"""
import os
import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

BLOGGER_SCOPES = ["https://www.googleapis.com/auth/blogger"]


def publish_blog_post(
    title: str,
    html_content: str,
    cover_image_url: str,
    labels: list[str],
    meta_description: str = "",
    slug: str = "",
) -> dict:
    """Publish a post to Blogger and return its public URL.

    The cover image URL is prepended to the HTML as a responsive <img>
    tag, so callers do NOT need to embed it themselves.

    Args:
        title: Post title, plain text. Aim for 50-65 characters for SEO.
        html_content: Post body as HTML. Do not include <html>, <head>,
            or <body> tags — Blogger wraps it for you.
        cover_image_url: Public https URL of the cover image (from GCS).
        labels: List of tag strings for the post (e.g. ["AI", "Trends"]).
        meta_description: 140-160 character SEO summary shown under the
            title in Google search results. Optional but strongly
            recommended. Requires "Enable search description" to be ON
            in the Blogger dashboard's Settings -> Meta tags.
        slug: Lowercase hyphenated URL slug for the post (e.g.
            "gemini-3-launch-features"). Optional — Blogger generates
            one from the title if omitted.

    Returns:
        On success: {"published_url": "<https URL of the live post>",
                     "post_id": "<blogger post id>"}
        On failure: {"error": "<reason>"}
    """
    client_id = os.environ.get("BLOGGER_CLIENT_ID")
    client_secret = os.environ.get("BLOGGER_CLIENT_SECRET")
    refresh_token = os.environ.get("BLOGGER_REFRESH_TOKEN")
    blog_id = os.environ.get("BLOGGER_BLOG_ID")

    if not all([client_id, client_secret, refresh_token, blog_id]):
        return {
            "error": "Missing Blogger env vars "
                     "(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN, or BLOG_ID)"
        }

    # Build credentials from the refresh token. The google-auth library
    # will automatically exchange this for an access token on first use
    # and refresh transparently when it expires.
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=BLOGGER_SCOPES,
    )

    # Prepend the cover image. style is inline because Blogger themes
    # strip <style> blocks from post bodies.
    # The alt attribute also feeds Google Image Search — using the title
    # gives the image a meaningful, keyword-rich description.
    cover_img_html = (
        f'<img src="{cover_image_url}" '
        f'alt="{title}" '
        f'style="width:100%;height:auto;display:block;margin-bottom:1.5em;" />'
    )
    full_html = cover_img_html + html_content

    post_body: dict = {
        "kind": "blogger#post",
        "title": title,
        "content": full_html,
        "labels": labels or [],
    }

    # Blogger API v3 takes the search description as `customMetaData`
    # on the post resource. The blog must have search descriptions
    # enabled in its settings or this is silently dropped.
    if meta_description:
        post_body["customMetaData"] = meta_description

    # Blogger API supports a custom URL path via the `permalink` field.
    # Format must be "/YYYY/MM/<slug>.html". If omitted, Blogger derives
    # the slug from the title automatically.
    if slug:
        # Defensive cleanup in case the LLM included whitespace, slashes
        # or uppercase. We DON'T transliterate non-ASCII here — let it
        # through; Blogger handles unicode slugs.
        clean_slug = slug.strip().strip("/").lower().replace(" ", "-")
        post_body["permalink"] = f"/{clean_slug}.html"

    try:
        service = build("blogger", "v3", credentials=creds, cache_discovery=False)
        # isDraft=False -> publish immediately. Flip to True if you want
        # to review in the Blogger dashboard before going live.
        # fetchBody=False reduces the response payload — we only need
        # the URL and ID back, not the full HTML echoed.
        result = service.posts().insert(
            blogId=blog_id,
            body=post_body,
            isDraft=False,
            fetchBody=False,
        ).execute()
    except HttpError as e:
        logger.exception("Blogger API call failed")
        return {"error": f"Blogger API HTTP error: {e}"}
    except Exception as e:
        logger.exception("Unexpected error during Blogger publish")
        return {"error": f"Unexpected error: {e}"}

    return {
        "published_url": result.get("url", ""),
        "post_id": result.get("id", ""),
    }