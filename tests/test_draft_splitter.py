"""Unit tests for the draft_splitter JSON extraction.

The writer agent is told to emit a prose summary followed by strict JSON on
the last line. draft_splitter must robustly recover that JSON across several
real-world LLM output shapes. We test the static `_extract_json` helper in
isolation — it has no ADK dependency.

Run with:  python -m pytest tests/ -q
"""
import importlib.util
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_draft_splitter():
    """Import draft_splitter with the ADK agent base classes stubbed out.

    draft_splitter imports google.adk.* at module load. We only want the
    pure-Python `DraftSplitter._extract_json`, so we inject lightweight stub
    modules for the ADK imports before loading the file.
    """
    adk = types.ModuleType("google.adk")
    agents = types.ModuleType("google.adk.agents")
    inv = types.ModuleType("google.adk.agents.invocation_context")
    events = types.ModuleType("google.adk.events")

    class _BaseAgent:  # minimal stand-in; we never instantiate the agent here
        def __init__(self, *a, **k):
            pass

    agents.BaseAgent = _BaseAgent
    inv.InvocationContext = object
    events.Event = object
    events.EventActions = object

    google_pkg = sys.modules.setdefault("google", types.ModuleType("google"))
    google_pkg.adk = adk
    sys.modules["google.adk"] = adk
    sys.modules["google.adk.agents"] = agents
    sys.modules["google.adk.agents.invocation_context"] = inv
    sys.modules["google.adk.events"] = events

    spec = importlib.util.spec_from_file_location(
        "draft_splitter", ROOT / "trend_agent/sub_agents/draft_splitter.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


draft_splitter = _load_draft_splitter()
extract = draft_splitter.DraftSplitter._extract_json


def test_pure_json():
    assert extract('{"title": "Hello"}') == {"title": "Hello"}


def test_summary_then_json_on_last_line():
    raw = "Here is a summary of the post.\n{\"title\": \"Hello\", \"slug\": \"hello\"}"
    assert extract(raw)["slug"] == "hello"


def test_json_wrapped_in_code_fences():
    raw = '```json\n{"title": "Hi"}\n```'
    assert extract(raw) == {"title": "Hi"}


def test_already_parsed_dict_passes_through():
    assert extract({"title": "x"}) == {"title": "x"}


def test_garbage_returns_none():
    assert extract("no json here at all") is None


def test_empty_returns_none():
    assert extract("") is None


def test_multiline_json_after_prose():
    raw = 'Summary paragraph.\n{\n  "title": "Multi",\n  "labels": ["a", "b"]\n}'
    parsed = extract(raw)
    assert parsed["title"] == "Multi"
    assert parsed["labels"] == ["a", "b"]
