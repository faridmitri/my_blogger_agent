"""Orchestrator

An LlmAgent with a single custom tool, `send_message`, that routes a task to
one of the remote specialist agents over A2A:

  - On construction, fetch each specialist's AgentCard and build a
    RemoteAgentConnections object per agent ("meeting the team").
  - Expose ONE tool: send_message(agent_name, task) -> the agent's reply.
  - The LLM reads the available agents + skills from its instruction and
    decides which agent to call, in what order, feeding each result into the
    next call — all within one agent turn.

Unlike the RemoteA2aAgent-as-sub-agent approach, here the remote calls are a
*tool* the LLM invokes, so the LLM stays in control across the whole sequence
and won't terminate after the first delegation.
"""

import os

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext

from common import DEFAULT_MODEL
from .remote_agent_connection import RemoteAgentConnections, fetch_agent_card

# Specialist service URLs (localhost defaults; Cloud Run URLs in prod).
_AGENT_URLS = {
    "researcher_agent": os.environ.get("RESEARCHER_AGENT_URL", "http://localhost:8001"),
    "writer_agent":     os.environ.get("WRITER_AGENT_URL",     "http://localhost:8002"),
    "publisher_agent":  os.environ.get("PUBLISHER_AGENT_URL",  "http://localhost:8003"),
}

# Populated lazily on first send_message call by _ensure_connections().
_connections: dict[str, RemoteAgentConnections] = {}
_agent_descriptions: dict[str, str] = {}
_init_done = False


async def _ensure_connections() -> None:
    """Fetch every specialist's agent card and build a connection for each.

    Lazy: runs on the first send_message call, inside the running event loop.
    This avoids import-time asyncio.run() conflicts (e.g. under adk web) and
    means the orchestrator module imports cleanly even if services are down.
    """
    global _init_done
    if _init_done:
        return
    for name, url in _AGENT_URLS.items():
        try:
            card = await fetch_agent_card(url)
            _connections[name] = RemoteAgentConnections(card, url)
            skill = card.skills[0].description if card.skills else card.description
            _agent_descriptions[name] = skill or card.description or name
        except Exception as e:  # noqa: BLE001
            _agent_descriptions[name] = f"(unavailable at {url}: {e})"
    _init_done = True


async def send_message(agent_name: str, task: str, tool_context: ToolContext) -> str:
    """Send a task to a remote specialist agent over A2A and return its reply.

    Args:
        agent_name: One of "researcher_agent", "writer_agent", "publisher_agent".
        task: The full instruction/payload to send to that agent. When passing
              JSON from a previous step, include the COMPLETE JSON verbatim.
        tool_context: ADK-injected context (unused, required by signature).

    Returns:
        The remote agent's text response (usually a JSON string).
    """
    await _ensure_connections()
    conn = _connections.get(agent_name)
    if conn is None:
        available = ", ".join(_connections.keys()) or "(none connected)"
        return (
            f"ERROR: unknown or unavailable agent '{agent_name}'. "
            f"Available agents: {available}."
        )
    try:
        reply = await conn.send_message(task)
        return reply or f"ERROR: {agent_name} returned an empty response."
    except Exception as e:  # noqa: BLE001
        return f"ERROR calling {agent_name}: {e}"


def _build_instruction() -> str:
    return "\n".join([
        "You are the Orchestrator for an autonomous blog pipeline. You do NOT",
        "do the work yourself — you delegate to remote specialist agents by",
        "calling the `send_message(agent_name, task)` tool.",
        "",
        "AVAILABLE AGENTS:",
        "  - researcher_agent: discovers one timely Google Cloud blog topic and",
        "    returns a selected_trend JSON object.",
        "  - writer_agent: turns a selected_trend into a structured BlogDraft",
        "    JSON object (title, meta_description, slug, html, image_prompt, labels).",
        "  - publisher_agent: publishes a BlogDraft — cover image, Blogger post,",
        "    Facebook cross-post, indexing — and returns the live URLs.",
        "",
        "YOUR JOB — execute these three delegations in order, one per tool call:",
        "",
        "1. Call send_message('researcher_agent', 'Find today\\'s best Google Cloud",
        "   blog topic. Return only the selected_trend JSON.').",
        "   Keep the returned selected_trend JSON.",
        "",
        "2. Call send_message('writer_agent', '<a message that includes the FULL",
        "   selected_trend JSON from step 1 and asks for a BlogDraft>').",
        "   Keep the returned BlogDraft JSON.",
        "",
        "3. Call send_message('publisher_agent', '<a message that includes the FULL",
        "   BlogDraft JSON from step 2 and asks to publish>').",
        "   Keep the returned result (published_url, facebook_post_url).",
        "",
        "RULES:",
        "- You MUST complete all three calls before giving your final answer.",
        "- Getting the researcher result is NOT done — proceed to the writer.",
        "- Getting the writer result is NOT done — proceed to the publisher.",
        "- Pass the COMPLETE JSON from each step into the next, verbatim.",
        "- If send_message returns a string starting with 'ERROR', stop and",
        "  report which step failed and the error text.",
        "",
        "FINAL ANSWER (only after step 3): report the published_url and the",
        "facebook_post_url.",
    ])


# The orchestrator: an LlmAgent whose ONLY tool is send_message.
root_agent = LlmAgent(
    name="orchestrator",
    model=DEFAULT_MODEL,
    description=(
        "Central coordinator. Delegates to the researcher, writer, and "
        "publisher specialist agents over A2A using the send_message tool."
    ),
    instruction=_build_instruction(),
    tools=[send_message],
)
