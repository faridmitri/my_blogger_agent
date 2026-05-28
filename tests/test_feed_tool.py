"""Unit tests for trend_agent.tools.feed_tool.

Run with:  python -m pytest tests/ -q
These tests stub feedparser.parse with a local fixture, so they make no
network calls and run anywhere.
"""
import time
from unittest import mock

import feedparser
import pytest

from tests.conftest import load_module

# Capture the genuine parser BEFORE any patching so our fake fixtures can use
# it without recursing into the mock.
_REAL_PARSE = feedparser.parse

feed_tool = load_module("trend_agent/tools/feed_tool.py", "feed_tool")


def _rss(*, fresh_hours=1, include_old=True):
    now = time.time()
    fresh = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(now - fresh_hours * 3600))
    old = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(now - 200 * 3600))
    old_item = (
        f"<item><title>Old announcement</title>"
        f"<link>https://cloud.google.com/blog/old</link>"
        f"<description>stale</description><pubDate>{old}</pubDate></item>"
        if include_old else ""
    )
    return f"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>GCP Blog</title>
<item><title>Vertex AI adds new models</title>
<link>https://cloud.google.com/blog/vertex-new</link>
<description>&lt;p&gt;Today we are &lt;b&gt;expanding&lt;/b&gt;   choices.&lt;/p&gt;</description>
<pubDate>{fresh}</pubDate></item>
{old_item}
</channel></rss>"""


def _patch(xml):
    return mock.patch.object(
        feed_tool.feedparser, "parse", side_effect=lambda u, agent=None: _REAL_PARSE(xml)
    )


def test_recency_filter_drops_old_entries():
    with _patch(_rss()):
        result = feed_tool.fetch_feed_items("gcp_blog", max_age_hours=72)
    assert result["count"] == 1
    assert result["items"][0]["title"] == "Vertex AI adds new models"


def test_summary_is_stripped_of_html_and_whitespace():
    with _patch(_rss()):
        result = feed_tool.fetch_feed_items("gcp_blog", max_age_hours=72)
    summary = result["items"][0]["summary"]
    assert "<" not in summary and ">" not in summary
    assert "  " not in summary  # collapsed runs of whitespace
    assert summary == "Today we are expanding choices."


def test_published_is_iso_utc():
    with _patch(_rss()):
        result = feed_tool.fetch_feed_items("gcp_blog", max_age_hours=72)
    assert result["items"][0]["published"].endswith("Z")


def test_unknown_feed_key_returns_error():
    result = feed_tool.fetch_feed_items("not_a_real_feed")
    assert "error" in result
    assert "gcp_blog" in result["error"]  # lists the valid keys


def test_max_results_is_clamped_and_old_kept_when_window_is_wide():
    with _patch(_rss()):
        result = feed_tool.fetch_feed_items(
            "gcp_blog", max_results=999, max_age_hours=100_000
        )
    assert result["count"] == 2  # both entries within the wide window


def test_malformed_feed_with_no_entries_returns_error():
    with _patch("<<<not valid xml"):
        result = feed_tool.fetch_feed_items("gcp_blog")
    assert "error" in result


@pytest.mark.parametrize("key", ["gcp_blog", "gcp_releases", "gcp_learning"])
def test_all_registered_keys_resolve(key):
    assert key in feed_tool._FEEDS
    assert feed_tool._FEEDS[key].startswith("https://")
