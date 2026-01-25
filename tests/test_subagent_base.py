"""Unit tests for the base subagent pattern."""

import os
from unittest.mock import MagicMock, patch

import pytest

from backend.models.subagent_models import SubagentResponse
from backend.services.subagents.base import (
    ActionSpaceSubagent,
    BaseSubagent,
    RulesSubagent,
    ScenarioSubagent,
    StateSubagent,
    SubagentConfig,
    SubagentError,
    SubagentState,
    SubagentTimeoutError,
    create_subagent,
)


# =============================================================================
# SubagentConfig Tests
# =============================================================================


class TestSubagentConfig:
    """Tests for SubagentConfig dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = SubagentConfig()
        assert config.temperature == 0.0
        assert config.max_tokens == 2048
        assert config.timeout_seconds == 30.0
        assert config.retry_attempts == 2

    def test_custom_values(self):
        """Should accept custom values."""
        config = SubagentConfig(
            temperature=0.7,
            max_tokens=1024,
            timeout_seconds=60.0,
            retry_attempts=3,
        )
        assert config.temperature == 0.7
        assert config.max_tokens == 1024
        assert config.timeout_seconds == 60.0
        assert config.retry_attempts == 3

    def test_config_is_frozen(self):
        """Config should be immutable."""
        config = SubagentConfig()
        with pytest.raises(AttributeError):
            config.temperature = 0.5

    def test_from_env_with_defaults(self):
        """from_env should use defaults when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = SubagentConfig.from_env()
            assert config.temperature == 0.0
            assert config.max_tokens == 2048
            assert config.timeout_seconds == 30.0
            assert config.retry_attempts == 2

    def test_from_env_with_custom_values(self):
        """from_env should read from environment variables."""
        env_vars = {
            "SUBAGENT_TEMPERATURE": "0.5",
            "SUBAGENT_MAX_TOKENS": "4096",
            "SUBAGENT_TIMEOUT": "45.0",
            "SUBAGENT_RETRY_ATTEMPTS": "5",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            config = SubagentConfig.from_env()
            assert config.temperature == 0.5
            assert config.max_tokens == 4096
            assert config.timeout_seconds == 45.0
            assert config.retry_attempts == 5


# =============================================================================
# SubagentState Tests
# =============================================================================


class TestSubagentState:
    """Tests for SubagentState Pydantic model."""

    def test_requires_query(self):
        """Should require query field."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SubagentState()

    def test_accepts_minimal_state(self):
        """Should accept just query."""
        state = SubagentState(query="Can Roland include Shrivelling?")
        assert state.query == "Can Roland include Shrivelling?"
        assert state.context == {}
        assert state.system_prompt == ""
        assert state.error is None
        assert state.response is None

    def test_accepts_full_state(self):
        """Should accept all fields."""
        from backend.models.subagent_models import SubagentMetadata, SubagentResponse

        mock_response = SubagentResponse(
            content="Test",
            metadata=SubagentMetadata(agent_type="rules"),
        )
        state = SubagentState(
            query="Test query",
            context={"investigator_name": "Roland Banks"},
            system_prompt="You are a rules expert.",
            error=None,
            response=mock_response,
        )
        assert state.context["investigator_name"] == "Roland Banks"
        assert "rules expert" in state.system_prompt


# =============================================================================
# Base Subagent Tests
# =============================================================================


class TestBaseSubagentInstantiation:
    """Tests for BaseSubagent instantiation."""

    def test_rejects_invalid_agent_type(self):
        """Should reject unknown agent types."""
        with pytest.raises(ValueError) as exc_info:
            # Need to use a concrete subclass since BaseSubagent is abstract
            create_subagent("invalid_type")
        assert "Unknown agent type" in str(exc_info.value)
        assert "invalid_type" in str(exc_info.value)

    def test_accepts_valid_agent_types(self):
        """Should accept all valid agent types."""
        with patch("backend.services.subagents.base.get_llm_config") as mock_config:
            mock_config.return_value = MagicMock(
                subagent_model="gpt-4o-mini",
                api_key="test-key",
            )

            for agent_type in ["rules", "state", "action_space", "scenario"]:
                agent = create_subagent(agent_type)
                assert agent.agent_type == agent_type

    def test_uses_custom_config(self):
        """Should use provided config."""
        config = SubagentConfig(temperature=0.5, max_tokens=1024)

        with patch("backend.services.subagents.base.get_llm_config") as mock_config:
            mock_config.return_value = MagicMock(
                subagent_model="gpt-4o-mini",
                api_key="test-key",
            )

            agent = RulesSubagent(config=config)
            assert agent.config.temperature == 0.5
            assert agent.config.max_tokens == 1024

    def test_raises_without_api_key(self):
        """Should raise when OPENAI_API_KEY is not set."""
        with patch("backend.services.subagents.base.get_llm_config") as mock_config:
            mock_config.return_value = MagicMock(
                subagent_model="gpt-4o-mini",
                api_key=None,
            )

            with pytest.raises(ValueError) as exc_info:
                RulesSubagent()
            assert "OPENAI_API_KEY" in str(exc_info.value)


# =============================================================================
# Concrete Subagent Tests
# =============================================================================


class TestRulesSubagent:
    """Tests for RulesSubagent."""

    @pytest.fixture
    def agent(self):
        """Create a RulesSubagent with mocked LLM."""
        with patch("backend.services.subagents.base.get_llm_config") as mock_config:
            mock_config.return_value = MagicMock(
                subagent_model="gpt-4o-mini",
                api_key="test-key",
            )
            return RulesSubagent()

    def test_agent_type_is_rules(self, agent):
        """Should have rules agent type."""
        assert agent.agent_type == "rules"

    def test_calculate_confidence_high_for_definitive(self, agent):
        """Should return high confidence for definitive language."""
        state = SubagentState(query="test")
        confidence = agent._calculate_confidence(
            "According to the rules, Roland Banks is legal for this card.",
            state,
        )
        assert confidence >= 0.9

    def test_calculate_confidence_medium_for_partial(self, agent):
        """Should return medium confidence for partial certainty."""
        state = SubagentState(query="test")
        confidence = agent._calculate_confidence(
            "Roland Banks can include Guardian cards.",
            state,
        )
        assert 0.7 <= confidence <= 0.8

    def test_determine_query_type_legality(self, agent):
        """Should identify legality check queries."""
        query_type = agent._determine_query_type("Can Roland include Shrivelling?")
        assert query_type == "legality_check"

    def test_determine_query_type_xp(self, agent):
        """Should identify XP queries."""
        query_type = agent._determine_query_type("How much XP does this upgrade cost?")
        assert query_type == "xp_rules"

    def test_extract_sources_includes_investigator(self, agent):
        """Should extract investigator as source."""
        state = SubagentState(
            query="test",
            context={"investigator_name": "Roland Banks"},
        )
        sources = agent._extract_sources(
            "Roland Banks can include this card.",
            state,
        )
        assert any("Roland Banks" in s for s in sources)


class TestStateSubagent:
    """Tests for StateSubagent."""

    @pytest.fixture
    def agent(self):
        """Create a StateSubagent with mocked LLM."""
        with patch("backend.services.subagents.base.get_llm_config") as mock_config:
            mock_config.return_value = MagicMock(
                subagent_model="gpt-4o-mini",
                api_key="test-key",
            )
            return StateSubagent()

    def test_agent_type_is_state(self, agent):
        """Should have state agent type."""
        assert agent.agent_type == "state"

    def test_calculate_confidence_high_for_quantitative(self, agent):
        """Should return high confidence for quantitative analysis."""
        state = SubagentState(query="test")
        confidence = agent._calculate_confidence(
            "The deck has 45% assets, 30% events, and 25% skills.",
            state,
        )
        assert confidence >= 0.9

    def test_determine_query_type_curve(self, agent):
        """Should identify resource curve queries."""
        query_type = agent._determine_query_type("What is the cost curve?")
        assert query_type == "resource_curve"

    def test_determine_query_type_gaps(self, agent):
        """Should identify gap analysis queries."""
        query_type = agent._determine_query_type("What is missing from this deck?")
        assert query_type == "coverage_gaps"


class TestActionSpaceSubagent:
    """Tests for ActionSpaceSubagent."""

    @pytest.fixture
    def agent(self):
        """Create an ActionSpaceSubagent with mocked LLM."""
        with patch("backend.services.subagents.base.get_llm_config") as mock_config:
            mock_config.return_value = MagicMock(
                subagent_model="gpt-4o-mini",
                api_key="test-key",
            )
            return ActionSpaceSubagent()

    def test_agent_type_is_action_space(self, agent):
        """Should have action_space agent type."""
        assert agent.agent_type == "action_space"

    def test_determine_query_type_upgrade(self, agent):
        """Should identify upgrade queries."""
        query_type = agent._determine_query_type("What should I upgrade to?")
        assert query_type == "upgrade_search"

    def test_determine_query_type_synergy(self, agent):
        """Should identify synergy queries."""
        query_type = agent._determine_query_type("What cards synergize with Machete?")
        assert query_type == "synergy_search"


class TestScenarioSubagent:
    """Tests for ScenarioSubagent."""

    @pytest.fixture
    def agent(self):
        """Create a ScenarioSubagent with mocked LLM."""
        with patch("backend.services.subagents.base.get_llm_config") as mock_config:
            mock_config.return_value = MagicMock(
                subagent_model="gpt-4o-mini",
                api_key="test-key",
            )
            return ScenarioSubagent()

    def test_agent_type_is_scenario(self, agent):
        """Should have scenario agent type."""
        assert agent.agent_type == "scenario"

    def test_calculate_confidence_high_for_specific(self, agent):
        """Should return high confidence for specific scenario knowledge."""
        state = SubagentState(query="test")
        confidence = agent._calculate_confidence(
            "The encounter deck contains several dangerous enemies.",
            state,
        )
        assert confidence >= 0.75

    def test_determine_query_type_threat(self, agent):
        """Should identify threat analysis queries."""
        query_type = agent._determine_query_type("What are the dangerous enemies and threats?")
        assert query_type == "threat_analysis"

    def test_extract_sources_includes_scenario(self, agent):
        """Should extract scenario as source."""
        state = SubagentState(
            query="test",
            context={"scenario_name": "The Gathering"},
        )
        sources = agent._extract_sources("Prepare for the Gathering.", state)
        assert any("The Gathering" in s for s in sources)


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateSubagent:
    """Tests for create_subagent factory function."""

    def test_creates_rules_subagent(self):
        """Should create RulesSubagent for 'rules' type."""
        with patch("backend.services.subagents.base.get_llm_config") as mock_config:
            mock_config.return_value = MagicMock(
                subagent_model="gpt-4o-mini",
                api_key="test-key",
            )
            agent = create_subagent("rules")
            assert isinstance(agent, RulesSubagent)

    def test_creates_state_subagent(self):
        """Should create StateSubagent for 'state' type."""
        with patch("backend.services.subagents.base.get_llm_config") as mock_config:
            mock_config.return_value = MagicMock(
                subagent_model="gpt-4o-mini",
                api_key="test-key",
            )
            agent = create_subagent("state")
            assert isinstance(agent, StateSubagent)

    def test_creates_action_space_subagent(self):
        """Should create ActionSpaceSubagent for 'action_space' type."""
        with patch("backend.services.subagents.base.get_llm_config") as mock_config:
            mock_config.return_value = MagicMock(
                subagent_model="gpt-4o-mini",
                api_key="test-key",
            )
            agent = create_subagent("action_space")
            assert isinstance(agent, ActionSpaceSubagent)

    def test_creates_scenario_subagent(self):
        """Should create ScenarioSubagent for 'scenario' type."""
        with patch("backend.services.subagents.base.get_llm_config") as mock_config:
            mock_config.return_value = MagicMock(
                subagent_model="gpt-4o-mini",
                api_key="test-key",
            )
            agent = create_subagent("scenario")
            assert isinstance(agent, ScenarioSubagent)

    def test_passes_config_to_subagent(self):
        """Should pass config to created subagent."""
        config = SubagentConfig(temperature=0.8)
        with patch("backend.services.subagents.base.get_llm_config") as mock_config:
            mock_config.return_value = MagicMock(
                subagent_model="gpt-4o-mini",
                api_key="test-key",
            )
            agent = create_subagent("rules", config=config)
            assert agent.config.temperature == 0.8

    def test_raises_for_invalid_type(self):
        """Should raise ValueError for invalid agent type."""
        with pytest.raises(ValueError) as exc_info:
            create_subagent("invalid")
        assert "Unknown agent type" in str(exc_info.value)


# =============================================================================
# Exception Tests
# =============================================================================


class TestSubagentExceptions:
    """Tests for subagent exception classes."""

    def test_subagent_error_is_exception(self):
        """SubagentError should be an Exception."""
        error = SubagentError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_timeout_error_is_subagent_error(self):
        """SubagentTimeoutError should inherit from SubagentError."""
        error = SubagentTimeoutError("Timeout")
        assert isinstance(error, SubagentError)
        assert isinstance(error, Exception)
