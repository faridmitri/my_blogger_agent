"""Headless entrypoint for orchestrator.

The orchestrator is a single LlmAgent whose `send_message` tool makes A2A
calls to the three specialists. We run it with one Runner; the LLM drives all
three delegations internally via its tool.

Run (with the three specialist services up on 8001/8002/8003):
    python -m orchestrator.run
"""

import asyncio
import sys

from dotenv import load_dotenv
load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

APP_NAME = "trend_orchestrator"
USER_ID = "pipeline_runner"


async def run_pipeline():
    import warnings
    warnings.filterwarnings("ignore")

    from orchestrator.agent import root_agent

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, state={}
    )
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    trigger = Content(
        role="user",
        parts=[Part(text=(
            "Run the full publish pipeline now. Delegate to researcher_agent, "
            "then writer_agent, then publisher_agent, in that order, using your "
            "send_message tool. Complete all three before answering."
        ))],
    )

    print("=" * 60)
    print("Orchestrator (InstaVibe pattern: LlmAgent + send_message tool)")
    print("=" * 60)
    print("Delegating: researcher -> writer -> publisher")
    print("This takes 2-4 minutes.\n")

    final_response = None
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=trigger,
    ):
        # Log tool calls so you can watch each delegation happen
        if event.content and event.content.parts:
            for part in event.content.parts:
                fc = getattr(part, "function_call", None)
                if fc:
                    args = dict(fc.args) if fc.args else {}
                    target = args.get("agent_name", "?")
                    print(f"  → send_message('{target}', ...)")
                fr = getattr(part, "function_response", None)
                if fr:
                    resp = fr.response
                    preview = str(resp)[:90].replace("\n", " ")
                    print(f"  ← reply: {preview}...")
                text = getattr(part, "text", None)
                if text and text.strip():
                    if event.is_final_response():
                        final_response = text

    print("\n" + "=" * 60)
    if final_response:
        print("✅ PIPELINE COMPLETE")
        print("=" * 60)
        print(final_response)
    else:
        print("Pipeline finished — no final text captured.")
        print("Check your Blogger dashboard and the service logs.")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_pipeline())
