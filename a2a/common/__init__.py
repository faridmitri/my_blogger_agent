"""Shared library for the A2A blog pipeline.

Holds the reusable pieces that every specialist agent depends on:
  - servers/  : MCP servers (feed, blogger, facebook) + McpToolset helpers
  - tools/    : Imagen cover-image tool + Google Indexing tool
  - callbacks : policy_gate safety gate + retry_on_quota
  - prompts   : all agent instructions

Importing this package loads .env so local runs and `adk web` pick up
credentials automatically.
"""

from dotenv import load_dotenv

load_dotenv()

# Model split, centralized so every specialist agrees.
DISCOVERER_MODEL = "gemini-2.5-flash-lite"
DEFAULT_MODEL = "gemini-2.5-flash"
