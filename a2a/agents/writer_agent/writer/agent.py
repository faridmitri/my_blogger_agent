"""Writer specialist — structured BlogDraft generator.

Reads a `selected_trend` JSON object and produces a `BlogDraft`. Uses ADK
structured output: output_schema=BlogDraft forces Gemini to emit JSON matching
the schema, which ADK validates. This replaces fragile JSON parsing.

Two production-critical details (per Google ADK guidance):
  1. output_schema disables tools AND agent transfer. To keep the structured
     response here (instead of transferring control), set
     disallow_transfer_to_parent/peers=True. The writer needs no tools anyway.
  2. ADK raises pydantic.ValidationError if the output doesn't match the
     schema. The field descriptions below steer generation.

This module defines `root_agent`, exposed over A2A by ../agent.py.
"""

from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field

from common import DEFAULT_MODEL
from common.prompts import WRITER_PROMPT


class BlogDraft(BaseModel):
    """Structured blog post. Every field is required; ADK validates on output."""

    title: str = Field(
        description="SEO title, 50-65 characters, primary keyword near the start. Plain text, no quotes."
    )
    meta_description: str = Field(
        description="SEO meta description, 140-160 characters, includes the primary keyword. Plain text."
    )
    slug: str = Field(
        description="URL slug: lowercase, hyphen-separated, ASCII only, 3-6 words, no leading/trailing slash."
    )
    html: str = Field(
        description="Full post body as HTML. No <html>/<head>/<body> tags. 1000-2000 words following the required structure."
    )
    image_prompt: str = Field(
        description="One concrete sentence describing a cover image for this post, suitable for an image generator."
    )
    labels: list[str] = Field(
        description="3-5 topic tags as short strings, e.g. ['AI', 'Google Cloud', 'Vertex AI']."
    )


root_agent = LlmAgent(
    name="writer_agent",
    model=DEFAULT_MODEL,
    description=(
        "Writes a structured, SEO-optimized 1000-2000 word HTML blog post from a "
        "selected_trend topic. Returns a validated BlogDraft JSON object."
    ),
    instruction=WRITER_PROMPT,
    output_schema=BlogDraft,
    output_key="blog_draft",
    # Required with output_schema so the agent returns structured output
    # instead of trying to transfer control.
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
