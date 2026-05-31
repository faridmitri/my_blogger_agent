import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from google.adk.runners import Runner

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from trend_agent import root_agent
from trend_agent.tools.indexing_tool import request_google_indexing


async def run_pipeline():
    session_service = InMemorySessionService()

    session = await session_service.create_session(
        app_name="trend_agent",
        user_id="cloud_scheduler",
        state={
            "tech_trends_candidates": [],
            "gcp_news_candidates": [],
            "gcp_releases_candidates": [],
            "gcp_learning_candidates": [],
        }
    )

    runner = Runner(
        agent=root_agent,
        app_name="trend_agent",
        session_service=session_service,
    )

    trigger = Content(
        role="user",
        parts=[Part(text="Run the full pipeline now.")],
    )

    print("Pipeline starting...")

    final_response = None
    async for event in runner.run_async(
        user_id="cloud_scheduler",
        session_id=session.id,
        new_message=trigger,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                text = event.content.parts[0].text
                if text and text.strip():
                    final_response = text
                    print(f"  ✓ Stage complete: {text[:80]}...")

    if not final_response:
        print("ERROR: Pipeline produced no final response.")
        sys.exit(1)

    print("\nPipeline complete:", final_response)

    # --- Indexing ping (no LLM, no extra cost) ---
    current_session = await session_service.get_session(
        app_name="trend_agent",
        user_id="cloud_scheduler",
        session_id=session.id,
    )
    published_url = current_session.state.get("published_url")

    # The publisher writes its text output here. On success that's the live
    # URL; on failure it's an "ERROR: ..." string (see prompts.py). Only ping
    # the Indexing API with a real http(s) URL — otherwise we'd send the error
    # string as a URL and get a 400 back (handoff gotcha #22).
    if published_url and str(published_url).startswith(("http://", "https://")):
        print(f"\n↳ Requesting Google indexing for: {published_url}")
        result = request_google_indexing(published_url)
        if result.get("success"):
            print(f"✓ Indexing ping sent — {result.get('notify_time')}")
        else:
            print(f"⚠ Indexing ping failed: {result.get('error')}")
    elif published_url:
        print(f"⚠ Publish did not return a URL ({published_url!r}) — skipping indexing ping")
    else:
        print("⚠ No published_url in session state — skipping indexing ping")

    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_pipeline())