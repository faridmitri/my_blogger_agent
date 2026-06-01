"""Safety callbacks shared across agents.

policy_gate is a `before_tool_callback`. ADK calls it right before a tool
runs. If it returns a dict, ADK SKIPS the real tool call and uses the dict as
the tool result (nothing is published). If it returns None, the tool runs
normally.

This is CODE-ENFORCED content policy, not prompt-enforced — the model cannot
argue its way around it. It protects against the AdSense-policy incident in
the project's history (a hype-heavy post got flagged). It is attached to the
publish tools inside the Publisher specialist agent.

retry_on_quota is provided for future use on rate-limited calls (Imagen,
Gemini). It is not wired in by default.
"""

import re
import time
import logging

logger = logging.getLogger("callbacks")

# Finance / hype patterns that have historically tripped ad-network policies.
_BANNED_PATTERNS = [
    r"\bguaranteed returns?\b",
    r"\bget rich\b",
    r"\bfinancial advice\b",
    r"\brisk[- ]free\b",
    r"\bdouble your (money|investment)\b",
    r"\b\d{2,}%\s*(gains?|returns?|profit)\b",
    r"\bto the moon\b",
    r"\bcan'?t lose\b",
]
_BANNED_RE = re.compile("|".join(_BANNED_PATTERNS), re.IGNORECASE)

# Only these tools publish to the outside world. Other tools (list_recent_posts,
# search_google_news, etc.) are read-only and don't need the content gate.
_PUBLISH_TOOLS = {"publish_post", "post_to_page"}

# Tool argument keys whose text we should scan.
_TEXT_ARG_KEYS = ("title", "html_content", "meta_description", "message")


def policy_gate(tool, args, tool_context):
    """Block a live publish if the content trips a banned-phrase rule.

    Args:
        tool: the ADK tool about to be called (has a `.name`).
        args: the dict of arguments the model produced for that tool.
        tool_context: ADK tool context (unused here).

    Returns:
        None to allow the call, or a dict to block it (becomes the tool result).
    """
    tool_name = getattr(tool, "name", "")
    if tool_name not in _PUBLISH_TOOLS:
        return None  # read-only or non-publishing tool: allow.

    blob = " ".join(
        str(args.get(k, "")) for k in _TEXT_ARG_KEYS if args.get(k)
    )
    match = _BANNED_RE.search(blob)
    if match:
        phrase = match.group(0)
        logger.warning(
            "policy_gate BLOCKED %s — banned phrase %r", tool_name, phrase
        )
        return {
            "result": (
                f"ERROR: content policy gate blocked this publish — "
                f"banned phrase detected: {phrase!r}. Nothing was published."
            )
        }
    return None


def retry_on_quota(max_retries: int = 3, base_delay: float = 2.0):
    """Decorator: retry a callable on 429/quota errors with exponential backoff.

    Only retries on actual rate-limit / quota errors, not on every failure.
    Not wired in by default; available for Imagen / Gemini calls if needed.
    """

    def decorator(fn):
        def wrapper(*a, **kw):
            attempt = 0
            while True:
                try:
                    return fn(*a, **kw)
                except Exception as e:  # noqa: BLE001
                    msg = str(e).lower()
                    is_quota = "429" in msg or "quota" in msg or "rate limit" in msg
                    if not is_quota or attempt >= max_retries:
                        raise
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "retry_on_quota: attempt %d hit quota, sleeping %.1fs",
                        attempt + 1, delay,
                    )
                    time.sleep(delay)
                    attempt += 1

        return wrapper

    return decorator
