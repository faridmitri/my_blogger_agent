"""Publisher specialist — internal 3-stage publishing pipeline.

Given a BlogDraft, this specialist runs three stages in order inside its own
service:
  1. image_creator   : Imagen 4 -> GCS public URL  (cover_image_url)
  2. blogger_publisher: publish to Blogger          (published_url)  [policy_gate]
  3. facebook_poster : cross-post to Facebook Page  (facebook_post_url) [policy_gate]

After the LLM stages finish, an after_agent_callback pings the Google Indexing
API for the published URL (pure Python, no LLM, no extra token cost). This
keeps the indexing logic co-located with publishing instead of in a top-level
runner, which the A2A architecture no longer has.

policy_gate is a CODE-ENFORCED before_tool_callback on both publish tools:
the model cannot bypass it.

This module defines `root_agent`, exposed over A2A by ../agent.py.
"""

import json
import logging

from google.adk.agents import LlmAgent, SequentialAgent

from common import DEFAULT_MODEL
from common.callbacks import policy_gate
from common.prompts import (
    IMAGE_CREATOR_PROMPT,
    BLOGGER_PUBLISHER_PROMPT,
    FACEBOOK_POSTER_PROMPT,
)
from common.servers import blogger_toolset, facebook_toolset
from common.tools import generate_cover_image, request_google_indexing

logger = logging.getLogger("publisher")


def _capture_blog_draft(callback_context):
    """before_agent_callback: capture the incoming BlogDraft into state.

    When this specialist is called over A2A, the BlogDraft arrives as the user
    MESSAGE, not as session state. The internal stages, however, read it via
    the {blog_draft} state placeholder. This callback bridges the gap: it pulls
    the BlogDraft JSON out of the incoming message and writes it to
    state['blog_draft'] before the pipeline runs.
    Returns None so the pipeline proceeds normally.
    """
    try:
        # Find the latest user message text in the invocation.
        user_text = None
        contents = getattr(callback_context, "user_content", None)
        if contents and getattr(contents, "parts", None):
            for part in contents.parts:
                t = getattr(part, "text", None)
                if t and t.strip():
                    user_text = t
                    break

        if not user_text:
            logger.warning("publisher: no incoming message text found")
            return None

        # Extract a JSON object from the message (it may have surrounding text
        # or ```json fences). Find the outermost {...}.
        text = user_text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            # Validate it parses; store the clean JSON string.
            json.loads(candidate)
            callback_context.state["blog_draft"] = candidate
            logger.info("publisher: captured blog_draft (%d chars)", len(candidate))
        else:
            logger.warning("publisher: no JSON object found in incoming message")
    except Exception as e:  # noqa: BLE001
        logger.warning("publisher: failed to capture blog_draft: %s", e)
    return None


# --- Stage 1: cover image -------------------------------------------------
image_creator_agent = LlmAgent(
    name="image_creator",
    model=DEFAULT_MODEL,
    description="Generates a blog cover image with Imagen 4 Fast and returns its public URL.",
    instruction=IMAGE_CREATOR_PROMPT,
    tools=[generate_cover_image],
    output_key="cover_image_url",
)

# --- Stage 2: publish to Blogger (gated) ----------------------------------
blogger_publisher_agent = LlmAgent(
    name="blogger_publisher",
    model=DEFAULT_MODEL,
    description="Publishes the finished blog post to Blogger and returns the live post URL.",
    instruction=BLOGGER_PUBLISHER_PROMPT,
    tools=[blogger_toolset("publish_post")],
    output_key="published_url",
    before_tool_callback=policy_gate,
)

# --- Stage 3: cross-post to Facebook (gated) ------------------------------
facebook_poster_agent = LlmAgent(
    name="facebook_poster",
    model=DEFAULT_MODEL,
    description="Composes and publishes a Facebook Page post linking to the new article.",
    instruction=FACEBOOK_POSTER_PROMPT,
    tools=[facebook_toolset("post_to_page")],
    output_key="facebook_post_url",
    before_tool_callback=policy_gate,
)


def _ping_indexing_after_publish(callback_context):
    """after_agent_callback: ping Google Indexing API for the published URL.

    Runs once, after all three stages complete, reading published_url from
    session state. Only fires on a real http(s) URL (the publisher writes an
    "ERROR: ..." string on failure). No LLM, no extra token cost.
    Returns None so the pipeline's own output is preserved.
    """
    try:
        state = callback_context.state
        published_url = state.get("published_url")
    except Exception:  # noqa: BLE001
        published_url = None

    if published_url and str(published_url).startswith(("http://", "https://")):
        logger.info("Requesting Google indexing for: %s", published_url)
        result = request_google_indexing(published_url)
        if result.get("success"):
            logger.info("Indexing ping sent — %s", result.get("notify_time"))
        else:
            logger.warning("Indexing ping failed: %s", result.get("error"))
    else:
        logger.info("No valid published_url — skipping indexing ping (%r)", published_url)
    return None


# Publisher specialist root agent. Exposed over A2A in ../agent.py.
root_agent = SequentialAgent(
    name="publisher_agent",
    description=(
        "Publishes a finished BlogDraft: generates a cover image with Imagen 4, "
        "publishes the post to Blogger, cross-posts to the Facebook Page, and "
        "pings the Google Indexing API. Content policy is code-enforced via a "
        "before-tool gate on both publish actions."
    ),
    sub_agents=[
        image_creator_agent,
        blogger_publisher_agent,
        facebook_poster_agent,
    ],
    before_agent_callback=_capture_blog_draft,
    after_agent_callback=_ping_indexing_after_publish,
)
