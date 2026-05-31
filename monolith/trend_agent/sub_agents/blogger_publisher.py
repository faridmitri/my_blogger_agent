from google.adk.agents import LlmAgent

from ..callbacks import policy_gate
from ..prompts import BLOGGER_PUBLISHER_PROMPT
from ..servers import blogger_toolset

blogger_publisher_agent = LlmAgent(
    name="blogger_publisher",
    model="gemini-2.5-flash",
    description="Publishes the finished blog post to Blogger and returns the live post URL.",
    instruction=BLOGGER_PUBLISHER_PROMPT,
    tools=[blogger_toolset("publish_post")],
    output_key="published_url",
    # Code-enforced content policy: blocks a live publish if the draft trips
    # a banned-phrase rule, regardless of what the prompt allowed through.
    before_tool_callback=policy_gate,
)