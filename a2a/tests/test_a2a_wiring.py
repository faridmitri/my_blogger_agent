"""Offline structural tests for the A2A wiring.

Asserts that each specialist builds a valid AgentCard with at least one skill,
and that the orchestrator is wired with three RemoteA2aAgent sub-agents
pointing at the well-known card path. No servers are started; no network.
"""

from google.adk.agents.remote_a2a_agent import (
    RemoteA2aAgent,
    AGENT_CARD_WELL_KNOWN_PATH,
)


def test_researcher_card():
    from agents.researcher_agent.agent import agent_card, root_agent

    assert agent_card.name == "researcher_agent"
    assert root_agent.name == "researcher_agent"
    assert len(agent_card.skills) >= 1
    assert agent_card.skills[0].id == "discover_blog_topic"
    # Internal pipeline: parallel discovery then finalizer.
    assert [a.name for a in root_agent.sub_agents] == [
        "parallel_discovery",
        "trend_finalizer",
    ]


def test_writer_card():
    from agents.writer_agent.agent import agent_card, root_agent

    assert agent_card.name == "writer_agent"
    assert agent_card.skills[0].id == "write_blog_post"
    # Writer uses structured output.
    assert root_agent.output_schema is not None
    assert root_agent.output_schema.__name__ == "BlogDraft"


def test_publisher_card_and_stages():
    from agents.publisher_agent.agent import agent_card, root_agent

    assert agent_card.name == "publisher_agent"
    assert agent_card.skills[0].id == "publish_blog_post"
    # Internal pipeline: image -> blogger -> facebook.
    assert [a.name for a in root_agent.sub_agents] == [
        "image_creator",
        "blogger_publisher",
        "facebook_poster",
    ]
    # Indexing ping runs after the stages.
    assert root_agent.after_agent_callback is not None


def test_orchestrator_consumes_three_remote_agents():
    from orchestrator.agent import root_agent

    assert root_agent.name == "orchestrator"
    assert len(root_agent.sub_agents) == 3
    for sub in root_agent.sub_agents:
        assert isinstance(sub, RemoteA2aAgent)
    names = {s.name for s in root_agent.sub_agents}
    assert names == {"researcher_agent", "writer_agent", "publisher_agent"}


def test_card_path_constant():
    # Guards against silent drift in the well-known path the orchestrator uses.
    assert AGENT_CARD_WELL_KNOWN_PATH.endswith("agent-card.json")
