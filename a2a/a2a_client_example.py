"""Standalone A2A client — updated for current a2a-sdk (ClientFactory pattern).

Calls any specialist agent directly over A2A, without the orchestrator.
Useful for testing each specialist in isolation before running the full pipeline.

Usage (from a2a/ with venv active, services running):
    python a2a_client_example.py http://127.0.0.1:8001 "Find today's best Google Cloud blog topic."
    python a2a_client_example.py http://127.0.0.1:8002 "Write a post about Gemini 2.5 Flash."
"""

import asyncio
import sys

from a2a.client import ClientFactory
from a2a.types import Message, MessageSendParams, SendMessageRequest, TextPart


def _extract_text(event) -> str | None:
    """Pull text out of whatever the streaming iterator yields."""
    # Each event is (Task, UpdateEvent|None) or a Message.
    if isinstance(event, tuple):
        task, update = event
        # Final artifact text
        if hasattr(task, "artifacts") and task.artifacts:
            for artifact in task.artifacts:
                for part in artifact.parts:
                    root = getattr(part, "root", part)
                    text = getattr(root, "text", None)
                    if text:
                        return text
        # Status message text
        if hasattr(task, "status") and task.status:
            msg = getattr(task.status, "message", None)
            if msg and hasattr(msg, "parts"):
                for part in msg.parts:
                    root = getattr(part, "root", part)
                    text = getattr(root, "text", None)
                    if text:
                        return text
    elif hasattr(event, "parts"):
        # It's a Message
        for part in event.parts:
            root = getattr(part, "root", part)
            text = getattr(root, "text", None)
            if text:
                return text
    return None


async def call_agent(base_url: str, prompt: str) -> None:
    # ClientFactory.connect fetches the card and wires the transport in one call.
    async with ClientFactory.connect(base_url) as client:
        card = getattr(client, "_card", None) or getattr(client, "card", None)
        agent_name = card.name if card else base_url
        print(f"→ Agent: {agent_name}")
        print(f"  Prompt: {prompt}\n")

        message = Message(
            role="user",
            parts=[{"root": TextPart(text=prompt)}],
            message_id=__import__("uuid").uuid4().hex,
        )

        last_text = None
        async for event in client.send_message(message):
            text = _extract_text(event)
            if text:
                last_text = text   # keep the last non-empty text (the final answer)

        if last_text:
            print("← Agent reply:\n")
            # Strip markdown code fences if the model wrapped JSON in them
            text = last_text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            print(text)
        else:
            print("← No text reply received. The agent may still be running.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: python a2a_client_example.py <agent_base_url> \"<prompt>\"\n"
            "Example:\n"
            "  python a2a_client_example.py http://127.0.0.1:8001 "
            "\"Find today's best Google Cloud blog topic.\""
        )
        sys.exit(1)

    asyncio.run(call_agent(sys.argv[1], sys.argv[2]))
