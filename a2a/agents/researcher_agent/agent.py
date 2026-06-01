"""Researcher specialist — A2A server entrypoint.

Wraps the researcher `root_agent` with `to_a2a()` so it is reachable over the
A2A protocol. We pass an EXPLICIT AgentCard (rather than letting to_a2a
auto-generate one) so the advertised skills are stable and meaningful to the
orchestrator's planner — this is the "digital business card" other agents
read at /.well-known/agent-card.json.

Run locally:
    uvicorn agents.researcher_agent.agent:a2a_app --host 0.0.0.0 --port 8001

The agent card is then visible at:
    http://localhost:8001/.well-known/agent-card.json
"""

import os

from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from .researcher import root_agent

# Public URL of THIS service. On Cloud Run set RESEARCHER_PUBLIC_URL to the
# service URL; locally it defaults to the uvicorn address.
_PORT = int(os.environ.get("PORT", "8001"))
_PUBLIC_URL = os.environ.get("RESEARCHER_PUBLIC_URL", f"http://localhost:{_PORT}")

researcher_skill = AgentSkill(
    id="discover_blog_topic",
    name="Discover Blog Topic",
    description=(
        "Discovers one timely, non-duplicate Google Cloud blog topic. Reads "
        "the Google Cloud blog, release notes, and training feeds plus Google "
        "News, deduplicates against recently published posts, and returns the "
        "single best topic as a selected_trend JSON object."
    ),
    tags=["research", "trends", "google-cloud", "seo", "rss"],
    examples=[
        "Find today's best Google Cloud blog topic.",
        "What should we write about today?",
        "Discover a fresh, non-duplicate topic for the blog.",
    ],
)

agent_card = AgentCard(
    name="researcher_agent",
    description=(
        "Researcher specialist for the Cloud Edify blog pipeline. Finds one "
        "timely Google Cloud topic and returns it as selected_trend JSON."
    ),
    url=_PUBLIC_URL,
    version="1.0.0",
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(streaming=True),
    skills=[researcher_skill],
)

# `to_a2a` builds the Starlette app, mounts the A2A routes, and serves the
# agent card above at /.well-known/agent-card.json on startup.
a2a_app = to_a2a(root_agent, port=_PORT, agent_card=agent_card)
