"""BlogWriter — reads `selected_trend` from session state and writes a blog post.

Uses ADK structured output: output_schema=BlogDraft forces Gemini to emit JSON
matching the schema, which ADK validates and writes to state["blog_draft"] as a
dict. This replaces the old DraftSplitter stage entirely.

Two production-critical details (per Google ADK guidance):
  1. output_schema disables tools AND agent transfer. Inside a SequentialAgent
     we must set disallow_transfer_to_parent/peers=True, or the agent may try
     to transfer control instead of returning structured output, bypassing the
     schema. The writer needs no tools anyway (pure text transformation).
  2. ADK raises pydantic.ValidationError if the model's output doesn't match
     the schema. The field descriptions below are part of the prompt — they
     steer generation — and WRITER_PROMPT must demand raw JSON with no fences.
"""

from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field

from ..prompts import WRITER_PROMPT


class BlogDraft(BaseModel):
    """Structured blog post. Every field is required; ADK validates on output."""

    title: str = Field(
        description="SEO title, 50-65 characters, primary keyword near the start. Plain text, no quotes."
    )
    meta_description: str = Field(
        description="SEO meta description, 140-160 characters, includes the primary keyword. Plain text."
    )
    slug: str = Field(
        description="URL slug: lowercase, words separated by hyphens, ASCII only, 3-6 words, no leading/trailing slash."
    )
    html: str = Field(
        description="Full post body as HTML. No <html>/<head>/<body> tags. 700-1000 words following the required structure."
    )
    image_prompt: str = Field(
        description="One concrete sentence describing a cover image for this post, suitable for an image generator."
    )
    labels: list[str] = Field(
        description="3-5 topic tags as short strings, e.g. ['AI', 'Google Cloud', 'Vertex AI']."
    )


writer_agent = LlmAgent(
    name="blog_writer",
    model="gemini-2.5-flash",
    description="Writes a structured 700-1000 word HTML blog post from the selected trend.",
    instruction=WRITER_PROMPT,
    output_schema=BlogDraft,
    output_key="blog_draft",
    # Required when output_schema is used inside a SequentialAgent: keep the
    # structured response here instead of transferring control elsewhere.
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)