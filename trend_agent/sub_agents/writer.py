"""BlogWriter — reads `selected_trend` from session state and writes a blog post."""
from google.adk.agents import LlmAgent

from ..prompts import WRITER_PROMPT

writer_agent = LlmAgent(
    name="blog_writer",
    model="gemini-2.5-flash",
    description="Writes a 700-1000 word HTML blog post from a researched trend.",
    instruction=WRITER_PROMPT,
    tools=[],  # No tools — pure text transformation
    output_key="blog_draft",
)