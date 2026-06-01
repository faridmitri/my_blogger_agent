"""Researcher specialist — internal 2-stage pipeline.

Stage 1 (ParallelAgent): four discoverers run CONCURRENTLY. Each is given a
        single MCP tool from the feed server via tool_filter, so the LLM picks
        a TOOL (e.g. read_gcp_releases) and never supplies a URL.
Stage 2 (LlmAgent): finalizer dedups against blog history, picks the best
        survivor (Google Cloud topics prioritized), emits selected_trend.

All four candidate state keys are seeded to "[]" by a before_agent_callback on
the researcher root, so the finalizer's instruction template always renders
cleanly even if a discoverer returns nothing.

Per Google ADK docs, McpToolset is created SYNCHRONOUSLY at module load.
"""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from common import DISCOVERER_MODEL, DEFAULT_MODEL
from common.prompts import (
    TECH_TRENDS_DISCOVERER_PROMPT,
    GOOGLE_NEWS_DISCOVERER_PROMPT,
    GOOGLE_RELEASES_DISCOVERER_PROMPT,
    GOOGLE_LEARNING_DISCOVERER_PROMPT,
    TREND_FINALIZER_PROMPT,
)
from common.servers import feed_toolset, blogger_toolset


# Candidate keys the discoverers populate. They run in parallel; seed all four
# to "[]" before the pipeline starts so the finalizer's instruction template
# always renders cleanly even if one discoverer returns nothing.
_CANDIDATE_KEYS = (
    "tech_trends_candidates",
    "gcp_news_candidates",
    "gcp_releases_candidates",
    "gcp_learning_candidates",
)


def _seed_missing_candidates(callback_context):
    """before_agent_callback on the researcher root: ensure all candidate keys exist."""
    try:
        state = callback_context.state
        for key in _CANDIDATE_KEYS:
            if key not in state or state.get(key) in (None, ""):
                state[key] = "[]"
    except Exception:  # noqa: BLE001 - never block the pipeline over seeding
        pass
    return None


# --- Discoverers: each gets ONE filtered MCP tool -------------------------
tech_trends_discoverer = LlmAgent(
    name="tech_trends_discoverer",
    model=DISCOVERER_MODEL,
    description="Finds rising AI/tech topics via Google News search.",
    instruction=TECH_TRENDS_DISCOVERER_PROMPT,
    tools=[feed_toolset("search_google_news")],
    output_key="tech_trends_candidates",
)

gcp_news_discoverer = LlmAgent(
    name="gcp_news_discoverer",
    model=DISCOVERER_MODEL,
    description="Finds recent posts from the official Google Cloud blog feed.",
    instruction=GOOGLE_NEWS_DISCOVERER_PROMPT,
    tools=[feed_toolset("read_gcp_blog")],
    output_key="gcp_news_candidates",
)

gcp_releases_discoverer = LlmAgent(
    name="gcp_releases_discoverer",
    model=DISCOVERER_MODEL,
    description="Finds recent entries from the Google Cloud release-notes feed.",
    instruction=GOOGLE_RELEASES_DISCOVERER_PROMPT,
    tools=[feed_toolset("read_gcp_releases")],
    output_key="gcp_releases_candidates",
)

gcp_learning_discoverer = LlmAgent(
    name="gcp_learning_discoverer",
    model=DISCOVERER_MODEL,
    description="Finds recent items from the Google Cloud Training & Certifications feed.",
    instruction=GOOGLE_LEARNING_DISCOVERER_PROMPT,
    tools=[feed_toolset("read_gcp_learning")],
    output_key="gcp_learning_candidates",
)

# True parallel discovery: all four discoverers run concurrently.
parallel_discovery = ParallelAgent(
    name="parallel_discovery",
    description="Runs the news + three Google Cloud feed discoverers concurrently.",
    sub_agents=[
        tech_trends_discoverer,
        gcp_news_discoverer,
        gcp_releases_discoverer,
        gcp_learning_discoverer,
    ],
)

trend_finalizer = LlmAgent(
    name="trend_finalizer",
    model=DEFAULT_MODEL,
    description="Selects the single best candidate topic, prioritizing fresh Google Cloud items.",
    instruction=TREND_FINALIZER_PROMPT,
    tools=[blogger_toolset("list_recent_posts")],
    output_key="selected_trend",
)

# Researcher specialist root agent, exposed over A2A in ../agent.py.
root_agent = SequentialAgent(
    name="researcher_agent",
    description=(
        "Discovers one timely Google Cloud blog topic by running four feed/news "
        "discoverers in parallel (fault-isolated), then deduplicating against "
        "blog history and selecting the single best candidate. Returns a "
        "selected_trend JSON object."
    ),
    sub_agents=[parallel_discovery, trend_finalizer],
    before_agent_callback=_seed_missing_candidates,
)
