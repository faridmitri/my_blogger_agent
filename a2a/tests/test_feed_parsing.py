"""Offline unit tests for the feed MCP server's _parse_feed helper.

feedparser is monkeypatched so no network is touched. We import the private
helper directly from the server module.
"""

import importlib

import pytest

feed_server = importlib.import_module("common.servers.feed_server")


class _FakeFeedMeta(dict):
    pass


class _FakeParsed:
    def __init__(self, title, entries):
        self.feed = _FakeFeedMeta(title=title)
        self.entries = entries


def _entry(title, link, published):
    return {"title": title, "link": link, "published": published}


def test_formats_entries(monkeypatch):
    parsed = _FakeParsed(
        "GCP Blog",
        [
            _entry("Post A", "https://x/a", "Mon, 01 Jan 2026"),
            _entry("Post B", "https://x/b", "Tue, 02 Jan 2026"),
        ],
    )
    monkeypatch.setattr(feed_server.feedparser, "parse", lambda url: parsed)
    out = feed_server._parse_feed("https://x/rss", max_items=5)
    assert "GCP Blog" in out
    assert "Post A" in out and "Post B" in out
    assert "https://x/a" in out


def test_respects_max_items(monkeypatch):
    entries = [_entry(f"Post {i}", f"https://x/{i}", "date") for i in range(10)]
    parsed = _FakeParsed("Feed", entries)
    monkeypatch.setattr(feed_server.feedparser, "parse", lambda url: parsed)
    out = feed_server._parse_feed("https://x/rss", max_items=3)
    # Only 3 numbered entries should appear.
    assert "Post 0" in out and "Post 2" in out
    assert "Post 3" not in out


def test_handles_empty_feed(monkeypatch):
    parsed = _FakeParsed("Empty", [])
    monkeypatch.setattr(feed_server.feedparser, "parse", lambda url: parsed)
    out = feed_server._parse_feed("https://x/rss", max_items=5)
    assert "No articles found" in out


def test_handles_exception(monkeypatch):
    def boom(url):
        raise RuntimeError("network down")

    monkeypatch.setattr(feed_server.feedparser, "parse", boom)
    out = feed_server._parse_feed("https://x/rss", max_items=5)
    assert out.startswith("Error reading feed")
