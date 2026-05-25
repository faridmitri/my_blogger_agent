import asyncio
import logging

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types as genai_types

from ..prompts import FACEBOOK_POSTER_PROMPT
from ..tools import post_to_facebook

logger = logging.getLogger(__name__)

_QUOTA_COOLDOWN_S = 10  # same pacing pattern as blogger_publisher


async def _quota_cooldown(callback_context: CallbackContext) -> genai_types.Content | None:
    """Pause briefly before the agent's LLM call to spread Vertex AI RPM.

    Uses asyncio.sleep so we yield to ADK's event loop instead of blocking it.
    Returning None tells ADK to proceed with normal agent execution.
    """
    logger.info(
        "facebook_poster: waiting %ds before LLM call …",
        _QUOTA_COOLDOWN_S,
    )
    await asyncio.sleep(_QUOTA_COOLDOWN_S)
    return None


facebook_poster_agent = LlmAgent(
    name="facebook_poster",
    model="gemini-2.5-flash",
    description="Composes and publishes a Facebook Page post linking to the new Blogger article.",
    instruction=FACEBOOK_POSTER_PROMPT,
    tools=[post_to_facebook],
    output_key="facebook_post_url",
    before_agent_callback=_quota_cooldown,
)