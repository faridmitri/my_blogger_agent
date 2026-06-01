"""Remote A2A connection helper.

Wraps the a2a-sdk client so the orchestrator can hold one connection object
per specialist and call `send_message` against it. 

Each RemoteAgentConnections instance owns:
  - the specialist's AgentCard (fetched at startup)
  - an A2A client bound to that card

The orchestrator builds one of these per specialist, then its send_message
tool routes a task to the right one by name.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    Message,
    Part,
    Role,
    TextPart,
)


class _GoogleIdTokenAuth(httpx.Auth):
    """httpx auth that attaches a Google-signed ID token to each request.

    Cloud Run services deployed with --no-allow-unauthenticated require the
    caller to present an ID token whose `audience` is the target service URL.
    This handler fetches that token (from the Cloud Run metadata server, or
    from local ADC) and sets the Authorization header.

    The token is cached and refreshed when it nears expiry.
    """

    def __init__(self, audience: str):
        # Audience must be the bare service origin, e.g. https://researcher-...run.app
        self._audience = audience.rstrip("/")
        self._token: str | None = None

    def _fetch_token(self) -> str:
        # Imported lazily so local runs that never call this don't need the dep.
        import google.auth.transport.requests
        from google.oauth2 import id_token

        request = google.auth.transport.requests.Request()
        return id_token.fetch_id_token(request, self._audience)

    def auth_flow(self, request: httpx.Request):
        if self._token is None:
            self._token = self._fetch_token()
        request.headers["Authorization"] = f"Bearer {self._token}"
        response = yield request
        # If the token was rejected, refresh once and retry.
        if response.status_code in (401, 403):
            self._token = self._fetch_token()
            request.headers["Authorization"] = f"Bearer {self._token}"
            yield request


def _make_httpx_client(agent_url: str) -> httpx.AsyncClient:
    """Build the HTTP client for talking to a specialist.

    On Cloud Run (USE_CLOUD_RUN_AUTH=true) we attach a Google ID token whose
    audience is the specialist's URL. Locally we use a plain client — no auth,
    since the services run on localhost without authentication.
    """
    use_auth = os.environ.get("USE_CLOUD_RUN_AUTH", "").lower() in ("1", "true", "yes")
    if use_auth:
        return httpx.AsyncClient(timeout=600, auth=_GoogleIdTokenAuth(agent_url))
    return httpx.AsyncClient(timeout=600)


class RemoteAgentConnections:
    """Holds a live A2A client for one remote specialist agent."""

    def __init__(self, agent_card: AgentCard, agent_url: str):
        self._card = agent_card
        self._url = agent_url
        self._httpx = _make_httpx_client(agent_url)
        config = ClientConfig(httpx_client=self._httpx, streaming=False)
        factory = ClientFactory(config)
        self._client = factory.create(agent_card)

    @property
    def card(self) -> AgentCard:
        return self._card

    async def send_message(self, message_text: str) -> str:
        """Send a text task to this remote agent and return its text reply."""
        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=message_text))],
            message_id=uuid.uuid4().hex,
        )

        collected: list[str] = []
        async for event in self._client.send_message(message):
            text = _extract_text(event)
            if text:
                collected.append(text)

        # The last non-empty chunk is the agent's final answer.
        return collected[-1] if collected else ""

    async def aclose(self) -> None:
        await self._httpx.aclose()


def _extract_text(event: Any) -> str | None:
    """Pull text out of whatever the A2A client streaming iterator yields."""
    # Events are (Task, update) tuples or Message objects depending on SDK.
    if isinstance(event, tuple):
        task = event[0]
        # Final artifact text
        artifacts = getattr(task, "artifacts", None)
        if artifacts:
            for artifact in artifacts:
                for part in artifact.parts:
                    root = getattr(part, "root", part)
                    text = getattr(root, "text", None)
                    if text:
                        return text
        # Status message text
        status = getattr(task, "status", None)
        if status is not None:
            msg = getattr(status, "message", None)
            if msg and getattr(msg, "parts", None):
                for part in msg.parts:
                    root = getattr(part, "root", part)
                    text = getattr(root, "text", None)
                    if text:
                        return text
    elif hasattr(event, "parts"):
        for part in event.parts:
            root = getattr(part, "root", part)
            text = getattr(root, "text", None)
            if text:
                return text
    return None


async def fetch_agent_card(agent_url: str) -> AgentCard:
    """Fetch a specialist's agent card from its well-known URL.

    Uses the same auth policy as message calls: ID token on Cloud Run, none
    locally (so the card endpoint is reachable even when the service requires
    authentication).
    """
    async with _make_httpx_client(agent_url) as http:
        resolver = A2ACardResolver(http, agent_url)
        return await resolver.get_agent_card()
