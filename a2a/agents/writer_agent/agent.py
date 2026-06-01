"""Writer specialist — A2A server entrypoint.

Wraps the writer `root_agent` with `to_a2a()` and an explicit AgentCard so
the orchestrator can discover its single skill: turning a selected_trend into
a structured BlogDraft.

Run locally:
    uvicorn agents.writer_agent.agent:a2a_app --host 0.0.0.0 --port 8002

Agent card:
    http://localhost:8002/.well-known/agent-card.json
"""

import os

from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from .writer import root_agent

_PORT = int(os.environ.get("PORT", "8002"))
_PUBLIC_URL = os.environ.get("WRITER_PUBLIC_URL", f"http://localhost:{_PORT}")

writer_skill = AgentSkill(
    id="write_blog_post",
    name="Write Blog Post",
    description=(
        "Writes a complete, SEO-optimized 1000-2000 word HTML blog post from a "
        "selected_trend topic. Produces a structured BlogDraft JSON object with "
        "title, meta_description, slug, html body, image_prompt, and labels."
    ),
    tags=["writing", "seo", "content", "html", "blog"],
    examples=[
        "Write a blog post for this selected_trend JSON.",
        "Turn this topic into a publish-ready HTML post.",
    ],
)

agent_card = AgentCard(
    name="writer_agent",
    description=(
        "Writer specialist for the Cloud Edify blog pipeline. Turns a "
        "selected_trend topic into a structured, SEO-optimized BlogDraft."
    ),
    url=_PUBLIC_URL,
    version="1.0.0",
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(streaming=True),
    skills=[writer_skill],
)

a2a_app = to_a2a(root_agent, port=_PORT, agent_card=agent_card)
