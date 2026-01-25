"""Integration tests for subagent execution with mock LLM responses."""

from unittest.mock import MagicMock, patch

import pytest

from backend.models.subagent_models import SubagentResponse
from backend.services.subagents.base import (
    RulesSubagent,
    StateSubagent,
    ActionSpaceSubagent,
    ScenarioSubagent,
    SubagentConfig,
    create_subagent,
)


# =============================================================================
# Mock LLM Fixtures
# =============================================================================


@pytest.fixture
def mock_llm_config():
    """Mock the LLM configuration."""
    with patch("backend.services.subagents.base.get_llm_config") as mock:
        mock.return_value = MagicMock(
            subagent_model="gpt-4o-mini",
            api_key="test-api-key",
        )
        yield mock


@pytest.fixture
def mock_chat_openai():
    """Mock the ChatOpenAI class."""
    with patch("backend.services.subagents.base.ChatOpenAI") as mock:
        yield mock


def create_mock_llm_response(content: str) -> MagicMock:
    """Create a mock LLM response with the given content."""
    mock_response = MagicMock()
    mock_response.content = content
    return mock_response


# =============================================================================
# RulesSubagent Integration Tests
# =============================================================================


class TestRulesSubagentIntegration:
    """Integration tests for RulesSubagent with mock LLM."""

    def test_query_returns_structured_response(self, mock_llm_config, mock_chat_openai):
        """Query should return a SubagentResponse."""
        # Setup mock LLM response
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = create_mock_llm_response(
            "According to the rules, Roland Banks can include Guardian cards "
            "level 0-5 and Seeker cards level 0-2. Shrivelling is a Mystic card "
            "and is NOT legal for Roland Banks."
        )
        mock_chat_openai.return_value = mock_llm

        agent = RulesSubagent()
        response = agent.query(
            "Can Roland Banks include Shrivelling?",
            context={"investigator_name": "Roland Banks"},
        )

        assert isinstance(response, SubagentResponse)
        assert "Roland Banks" in response.content
        assert response.metadata.agent_type == "rules"
        assert response.confidence > 0.5

    def test_query_uses_correct_system_prompt(self, mock_llm_config, mock_chat_openai):
        """Query should use the rules agent system prompt."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = create_mock_llm_response("Test response")
        mock_chat_openai.return_value = mock_llm

        agent = RulesSubagent()
        agent.query("Test query")

        # Verify invoke was called
        assert mock_llm.invoke.called

        # Check that system message contains rules agent content
        call_args = mock_llm.invoke.call_args[0][0]  # First positional arg
        system_message = call_args[0]
        assert "Rules Agent" in system_message.content

    def test_query_with_full_context(self, mock_llm_config, mock_chat_openai):
        """Query should pass all context to prompt formatting."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = create_mock_llm_response("Test response")
        mock_chat_openai.return_value = mock_llm

        agent = RulesSubagent()
        response = agent.query(
            "Is this card legal?",
            context={
                "investigator_name": "Jenny Barnes",
                "deck_id": "deck_123",
                "upgrade_xp": 5,
                "campaign_name": "The Dunwich Legacy",
            },
        )

        # Verify context was used in metadata
        assert response.metadata.context_used.get("investigator_name") == "Jenny Barnes"
        assert response.metadata.context_used.get("deck_id") == "deck_123"


# =============================================================================
# StateSubagent Integration Tests
# =============================================================================


class TestStateSubagentIntegration:
    """Integration tests for StateSubagent with mock LLM."""

    def test_query_returns_structured_response(self, mock_llm_config, mock_chat_openai):
        """Query should return a SubagentResponse with analysis."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = create_mock_llm_response(
            "The deck has a well-balanced cost curve with 40% cards at 0-1 cost, "
            "35% at 2-3 cost, and 25% at 4+ cost. The deck includes 15 assets (50%), "
            "10 events (33%), and 5 skills (17%)."
        )
        mock_chat_openai.return_value = mock_llm

        agent = StateSubagent()
        response = agent.query(
            "Analyze the deck composition",
            context={"deck_id": "deck_456"},
        )

        assert isinstance(response, SubagentResponse)
        assert response.metadata.agent_type == "state"
        # High confidence due to percentages
        assert response.confidence >= 0.9

    def test_query_extracts_deck_sources(self, mock_llm_config, mock_chat_openai):
        """Query should extract deck info as sources."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = create_mock_llm_response("Analysis complete.")
        mock_chat_openai.return_value = mock_llm

        agent = StateSubagent()
        response = agent.query(
            "Analyze",
            context={
                "deck_id": "deck_789",
                "deck_summary": {"deck_name": "Roland's Combat Deck"},
            },
        )

        assert any("deck_789" in s for s in response.sources)


# =============================================================================
# ActionSpaceSubagent Integration Tests
# =============================================================================


class TestActionSpaceSubagentIntegration:
    """Integration tests for ActionSpaceSubagent with mock LLM."""

    def test_query_returns_card_recommendations(self, mock_llm_config, mock_chat_openai):
        """Query should return card recommendations."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = create_mock_llm_response(
            "I recommend the following cards for damage dealing:\n"
            "- Machete (level 0) - Excellent for engaged enemies\n"
            "- .45 Automatic (level 0) - Reliable ranged option\n"
            "- Vicious Blow (level 0) - Great for skill commits"
        )
        mock_chat_openai.return_value = mock_llm

        agent = ActionSpaceSubagent()
        response = agent.query(
            "Find cards that deal damage",
            context={"investigator_name": "Roland Banks"},
        )

        assert isinstance(response, SubagentResponse)
        assert response.metadata.agent_type == "action_space"
        assert "recommend" in response.content.lower()


# =============================================================================
# ScenarioSubagent Integration Tests
# =============================================================================


class TestScenarioSubagentIntegration:
    """Integration tests for ScenarioSubagent with mock LLM."""

    def test_query_returns_scenario_analysis(self, mock_llm_config, mock_chat_openai):
        """Query should return scenario analysis."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = create_mock_llm_response(
            "The Gathering is the first scenario of the Night of the Zealot campaign. "
            "Key threats include Ghoul Priest (boss enemy) and Rotting Remains "
            "(treachery with willpower test). The encounter deck focuses on "
            "willpower tests and combat challenges."
        )
        mock_chat_openai.return_value = mock_llm

        agent = ScenarioSubagent()
        response = agent.query(
            "What threats should I prepare for?",
            context={
                "scenario_name": "The Gathering",
                "campaign_name": "Night of the Zealot",
            },
        )

        assert isinstance(response, SubagentResponse)
        assert response.metadata.agent_type == "scenario"
        assert any("The Gathering" in s for s in response.sources)


# =============================================================================
# Error Handling Integration Tests
# =============================================================================


class TestSubagentErrorHandling:
    """Integration tests for error handling."""

    def test_handles_llm_exception(self, mock_llm_config, mock_chat_openai):
        """Should handle LLM invocation errors gracefully."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("Rate limit exceeded")
        mock_chat_openai.return_value = mock_llm

        agent = RulesSubagent(config=SubagentConfig(retry_attempts=0), use_cache=False)
        response = agent.query("Test query")

        assert isinstance(response, SubagentResponse)
        assert response.confidence == 0.0
        assert "failed" in response.content.lower() or "rate limit" in response.content.lower()
        assert response.metadata.query_type == "error"

    def test_retries_on_failure(self, mock_llm_config, mock_chat_openai):
        """Should retry on transient failures."""
        mock_llm = MagicMock()
        # First call fails, second succeeds
        mock_llm.invoke.side_effect = [
            Exception("Temporary error"),
            create_mock_llm_response("Success after retry"),
        ]
        mock_chat_openai.return_value = mock_llm

        agent = RulesSubagent(config=SubagentConfig(retry_attempts=1), use_cache=False)
        response = agent.query("Test query")

        assert "Success after retry" in response.content
        assert mock_llm.invoke.call_count == 2

    def test_returns_error_after_max_retries(self, mock_llm_config, mock_chat_openai):
        """Should return error response after exhausting retries."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("Persistent error")
        mock_chat_openai.return_value = mock_llm

        agent = RulesSubagent(config=SubagentConfig(retry_attempts=2), use_cache=False)
        response = agent.query("Test query")

        assert response.confidence == 0.0
        assert "error" in response.metadata.query_type.lower()
        # Should have tried 3 times (initial + 2 retries)
        assert mock_llm.invoke.call_count == 3


# =============================================================================
# Factory Integration Tests
# =============================================================================


class TestFactoryIntegration:
    """Integration tests for create_subagent factory."""

    def test_factory_creates_working_agents(self, mock_llm_config, mock_chat_openai):
        """Factory should create agents that can execute queries."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = create_mock_llm_response("Factory test response")
        mock_chat_openai.return_value = mock_llm

        for agent_type in ["rules", "state", "action_space", "scenario"]:
            agent = create_subagent(agent_type)
            response = agent.query("Test query")

            assert isinstance(response, SubagentResponse)
            assert response.metadata.agent_type == agent_type

    def test_factory_applies_config(self, mock_llm_config, mock_chat_openai):
        """Factory should apply provided config."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = create_mock_llm_response("Config test")
        mock_chat_openai.return_value = mock_llm

        config = SubagentConfig(temperature=0.7, max_tokens=512)
        agent = create_subagent("rules", config=config)

        assert agent.config.temperature == 0.7
        assert agent.config.max_tokens == 512


# =============================================================================
# Graph Execution Integration Tests
# =============================================================================


class TestGraphExecution:
    """Integration tests for LangGraph execution."""

    def test_graph_prepares_prompt_with_context(self, mock_llm_config, mock_chat_openai):
        """Graph should prepare prompt with full context."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = create_mock_llm_response("Context test")
        mock_chat_openai.return_value = mock_llm

        agent = RulesSubagent()
        agent.query(
            "Test",
            context={
                "investigator_name": "Daisy Walker",
                "deck_id": "deck_999",
                "scenario_name": "The House Always Wins",
            },
        )

        # Check system message contains context
        call_args = mock_llm.invoke.call_args[0][0]
        system_message = call_args[0]
        assert "Daisy Walker" in system_message.content
        assert "deck_999" in system_message.content

    def test_graph_passes_query_as_human_message(self, mock_llm_config, mock_chat_openai):
        """Graph should pass query as HumanMessage."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = create_mock_llm_response("Query test")
        mock_chat_openai.return_value = mock_llm

        agent = RulesSubagent()
        agent.query("Can Roland include Shrivelling?")

        call_args = mock_llm.invoke.call_args[0][0]
        human_message = call_args[1]
        assert "Shrivelling" in human_message.content
