"""Offline unit tests for the policy_gate before_tool_callback.

No API keys, no network. We pass a tiny fake `tool` object (only needs a
`.name`) and an args dict, and assert whether the gate blocks (returns a dict)
or allows (returns None).
"""

from common.callbacks import policy_gate


class _FakeTool:
    def __init__(self, name):
        self.name = name


def test_clean_content_passes():
    tool = _FakeTool("publish_post")
    args = {
        "title": "Cloud Run GPU Support Is Now GA",
        "html_content": "<p>A practical guide to the new feature.</p>",
        "meta_description": "Cloud Run now supports GPUs in GA.",
    }
    assert policy_gate(tool, args, None) is None


def test_banned_phrase_blocks_publish():
    tool = _FakeTool("publish_post")
    args = {
        "title": "How to get rich with this one trick",
        "html_content": "<p>Guaranteed returns, risk-free!</p>",
        "meta_description": "Double your money fast.",
    }
    result = policy_gate(tool, args, None)
    assert isinstance(result, dict)
    assert "blocked" in result["result"].lower()


def test_non_publish_tool_is_ignored():
    # Read-only tools are never gated, even with banned text present.
    tool = _FakeTool("list_recent_posts")
    args = {"title": "guaranteed returns get rich financial advice"}
    assert policy_gate(tool, args, None) is None


def test_facebook_message_is_checked():
    tool = _FakeTool("post_to_page")
    args = {"message": "This stock will go to the moon, you can't lose!"}
    result = policy_gate(tool, args, None)
    assert isinstance(result, dict)


def test_legitimate_pricing_mention_passes():
    # "pricing" / "cost" are fine — only the hype/finance patterns are banned.
    tool = _FakeTool("publish_post")
    args = {
        "title": "Understanding Cloud Run Pricing in 2026",
        "html_content": "<p>Cloud Run costs are based on usage. Here is how billing works.</p>",
        "meta_description": "A clear breakdown of Cloud Run pricing and cost factors.",
    }
    assert policy_gate(tool, args, None) is None
