"""Researcher: 2-stage sub-pipeline.

Stage 1 (ParallelAgent): four discoverers run concurrently.
        - tech_trends:  Reddit r/artificial (engagement velocity)
        - gcp_news:     Google Cloud blog feed (official product news)
        - gcp_releases: Google Cloud release-notes feed (what shipped)
        - gcp_learning: Training & Certifications feed (courses, exams)
Stage 2 (LlmAgent): finalizer dedups against blog history, picks the best
        survivor (Google Cloud topics prioritized), and emits selected_trend.

Each discoverer writes a JSON array to its own state key via output_key.
The finalizer reads all four arrays through prompt-template injection.
"""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from ..prompts import (
    TECH_TRENDS_DISCOVERER_PROMPT,
    GOOGLE_NEWS_DISCOVERER_PROMPT,
    GOOGLE_RELEASES_DISCOVERER_PROMPT,
    GOOGLE_LEARNING_DISCOVERER_PROMPT,
    TREND_FINALIZER_PROMPT,
)
from ..tools import (
    fetch_rising_posts,
    fetch_feed_items,
    get_recent_blog_topics,
)

_DISCOVERER_MODEL = "gemini-2.5-flash-lite"
_FINALIZER_MODEL = "gemini-2.5-flash"


# --- Reddit discoverer (velocity signal) ---------------------------------
tech_trends_discoverer = LlmAgent(
    name="tech_trends_discoverer",
    model=_DISCOVERER_MODEL,
    description="Finds rising AI posts from Reddit r/artificial.",
    instruction=TECH_TRENDS_DISCOVERER_PROMPT,
    tools=[fetch_rising_posts],
    output_key="tech_trends_candidates",
)


# --- Google Cloud feed discoverers (freshness signal) --------------------
gcp_news_discoverer = LlmAgent(
    name="gcp_news_discoverer",
    model=_DISCOVERER_MODEL,
    description="Finds recent posts from the official Google Cloud blog feed.",
    instruction=GOOGLE_NEWS_DISCOVERER_PROMPT,
    tools=[fetch_feed_items],
    output_key="gcp_news_candidates",
)

gcp_releases_discoverer = LlmAgent(
    name="gcp_releases_discoverer",
    model=_DISCOVERER_MODEL,
    description="Finds recent entries from the Google Cloud release-notes feed.",
    instruction=GOOGLE_RELEASES_DISCOVERER_PROMPT,
    tools=[fetch_feed_items],
    output_key="gcp_releases_candidates",
)

gcp_learning_discoverer = LlmAgent(
    name="gcp_learning_discoverer",
    model=_DISCOVERER_MODEL,
    description="Finds recent items from the Google Cloud Training & Certifications feed.",
    instruction=GOOGLE_LEARNING_DISCOVERER_PROMPT,
    tools=[fetch_feed_items],
    output_key="gcp_learning_candidates",
)


parallel_discovery = ParallelAgent(
    name="parallel_discovery",
    description="Runs the Reddit + three Google Cloud feed discoverers concurrently.",
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
    tools=[get_recent_blog_topics],
    output_key="selected_trend",
)


researcher_agent = SequentialAgent(
    name="researcher",
    description="Two-stage research pipeline: parallel discovery then finalization.",
    sub_agents=[parallel_discovery, trend_finalizer],
)