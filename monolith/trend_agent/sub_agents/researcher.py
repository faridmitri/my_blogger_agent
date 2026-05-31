"""Researcher: 2-stage sub-pipeline (MCP via McpToolset — Google-canonical).

Stage 1 (ParallelAgent): four discoverers run concurrently. Each is given a
        single MCP tool from the feed server via tool_filter, so the LLM picks
        a TOOL (e.g. read_gcp_releases) and never supplies a URL.
        - tech_trends:  search_google_news
        - gcp_news:     read_gcp_blog
        - gcp_releases: read_gcp_releases
        - gcp_learning: read_gcp_learning
Stage 2 (LlmAgent): finalizer dedups against blog history, picks the best
        survivor (Google Cloud topics prioritized), emits selected_trend.

Per Google's ADK docs, McpToolset is defined SYNCHRONOUSLY at module load
(required for Cloud Run / Agent Engine deployment — async agent factories do
not work there). Each McpToolset spawns the feed server over stdio, discovers
its tools, and tool_filter narrows the visible surface to one tool.
"""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from ..prompts import (
    TECH_TRENDS_DISCOVERER_PROMPT,
    GOOGLE_NEWS_DISCOVERER_PROMPT,
    GOOGLE_RELEASES_DISCOVERER_PROMPT,
    GOOGLE_LEARNING_DISCOVERER_PROMPT,
    TREND_FINALIZER_PROMPT,
)
from ..servers import feed_toolset, blogger_toolset

_DISCOVERER_MODEL = "gemini-2.5-flash-lite"
_FINALIZER_MODEL = "gemini-2.5-flash"


# --- Discoverers: each gets ONE filtered MCP tool -------------------------
tech_trends_discoverer = LlmAgent(
    name="tech_trends_discoverer",
    model=_DISCOVERER_MODEL,
    description="Finds rising AI/tech topics via Google News search.",
    instruction=TECH_TRENDS_DISCOVERER_PROMPT,
    tools=[feed_toolset("search_google_news")],
    output_key="tech_trends_candidates",
)

gcp_news_discoverer = LlmAgent(
    name="gcp_news_discoverer",
    model=_DISCOVERER_MODEL,
    description="Finds recent posts from the official Google Cloud blog feed.",
    instruction=GOOGLE_NEWS_DISCOVERER_PROMPT,
    tools=[feed_toolset("read_gcp_blog")],
    output_key="gcp_news_candidates",
)

gcp_releases_discoverer = LlmAgent(
    name="gcp_releases_discoverer",
    model=_DISCOVERER_MODEL,
    description="Finds recent entries from the Google Cloud release-notes feed.",
    instruction=GOOGLE_RELEASES_DISCOVERER_PROMPT,
    tools=[feed_toolset("read_gcp_releases")],
    output_key="gcp_releases_candidates",
)

gcp_learning_discoverer = LlmAgent(
    name="gcp_learning_discoverer",
    model=_DISCOVERER_MODEL,
    description="Finds recent items from the Google Cloud Training & Certifications feed.",
    instruction=GOOGLE_LEARNING_DISCOVERER_PROMPT,
    tools=[feed_toolset("read_gcp_learning")],
    output_key="gcp_learning_candidates",
)


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
    model=_FINALIZER_MODEL,
    description="Selects the single best candidate topic, prioritizing fresh Google Cloud items.",
    instruction=TREND_FINALIZER_PROMPT,
    tools=[blogger_toolset("list_recent_posts")],
    output_key="selected_trend",
)


researcher_agent = SequentialAgent(
    name="researcher",
    description="Two-stage research pipeline: parallel discovery then finalization.",
    sub_agents=[parallel_discovery, trend_finalizer],
)