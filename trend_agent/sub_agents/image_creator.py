from google.adk.agents import LlmAgent
from ..prompts import IMAGE_CREATOR_PROMPT
from ..tools import generate_cover_image

image_creator_agent = LlmAgent(
    name="image_creator",
    model="gemini-2.5-flash",
    description="Generates a blog cover image with Imagen 4 Fast and returns its public URL.",
    instruction=IMAGE_CREATOR_PROMPT,
    tools=[generate_cover_image],
    output_key="cover_image_url",
)