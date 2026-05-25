import asyncio
import logging

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types as genai_types

from ..prompts import BLOGGER_PUBLISHER_PROMPT
from ..tools import publish_blog_post

logger = logging.getLogger(__name__)

_QUOTA_COOLDOWN_S = 10  # seconds to wait before firing the LLM call


async def _quota_cooldown(callback_context: CallbackContext) -> genai_types.Content | None:
    """Pause briefly before the agent's LLM call to spread Vertex AI RPM.

    Uses asyncio.sleep so we yield to ADK's event loop instead of blocking it.
    Returning None tells ADK to proceed with normal agent execution.
    """
    logger.info(
        "blogger_publisher: waiting %ds before LLM call …",
        _QUOTA_COOLDOWN_S,
    )
    await asyncio.sleep(_QUOTA_COOLDOWN_S)
    return None


blogger_publisher_agent = LlmAgent(
    name="blogger_publisher",
    model="gemini-2.5-flash",
    description="Publishes the finished blog post to Blogger and returns the live post URL.",
    instruction=BLOGGER_PUBLISHER_PROMPT,
    tools=[publish_blog_post],
    output_key="published_url",
    before_agent_callback=_quota_cooldown,
)