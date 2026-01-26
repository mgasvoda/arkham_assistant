"""Unit tests for the Orchestrator Core Loop with LangGraph."""

import os
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from backend.models.subagent_models import SubagentMetadata, SubagentResponse
from backend.services.orchestrator import (
    Orchestrator,
    OrchestratorConfig,
    OrchestratorRequest,
    OrchestratorResponse,
    OrchestratorState,
    SubagentResult,
    SubagentType,
    ROUTING_KEYWORDS,
    create_orchestrator,
    process_chat_message,
)


# =============================================================================
# OrchestratorRequest Tests
# =============================================================================


class TestOrchestratorRequest:
    """Tests for OrchestratorRequest input schema."""

    def test_minimal_request(self):
        """Should accept just a message."""
        request = OrchestratorRequest(message="What cards should I include?")
        assert request.message == "What cards should I include?"
        assert request.investigator_id is None
        assert request.deck_id is None
        assert request.scenario_name is None

    def test_full_request(self):
        """Should accept all fields."""
        request = OrchestratorRequest(
            message="What cards should I add?",
            investigator_id="01001",
            investigator_name="Roland Banks",
            deck_id="deck_123",
            deck_cards=["01016", "01017"],
            scenario_name="The Gathering",
            campaign_name="Night of the Zealot",
            upgrade_xp=5,
            owned_sets=["Core Set", "Dunwich Legacy"],
        )
        assert request.message == "What cards should I add?"
        assert request.investigator_id == "01001"
        assert request.investigator_name == "Roland Banks"
        assert request.deck_id == "deck_123"
        assert request.deck_cards == ["01016", "01017"]
        assert request.scenario_name == "The Gathering"
        assert request.campaign_name == "Night of the Zealot"
        assert request.upgrade_xp == 5
        assert request.owned_sets == ["Core Set", "Dunwich Legacy"]

    def test_requires_message(self):
        """Should require message field."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OrchestratorRequest()

    def test_deck_cards_as_dict(self):
        """Should accept deck_cards as a dict mapping."""
        request = OrchestratorRequest(
            message="Analyze my deck",
            deck_cards={"01016": 2, "01017": 1},
        )
        assert request.deck_cards == {"01016": 2, "01017": 1}

    def test_upgrade_xp_non_negative(self):
        """Should reject negative XP values."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OrchestratorRequest(message="test", upgrade_xp=-1)


# =============================================================================
# SubagentResult Tests
# =============================================================================


class TestSubagentResult:
    """Tests for SubagentResult model."""

    def test_successful_result(self):
        """Should create a successful result."""
        response = SubagentResponse(
            content="Test response",
            confidence=0.8,
            metadata=SubagentMetadata(agent_type="rules"),
        )
        result = SubagentResult(
            agent_type="rules",
            query="test query",
            response=response,
            success=True,
        )
        assert result.agent_type == "rules"
        assert result.query == "test query"
        assert result.response is not None
        assert result.success is True
        assert result.error is None

    def test_failed_result(self):
        """Should create a failed result."""
        result = SubagentResult(
            agent_type="state",
            query="test query",
            response=None,
            success=False,
            error="Connection timeout",
        )
        assert result.agent_type == "state"
        assert result.response is None
        assert result.success is False
        assert result.error == "Connection timeout"


# =============================================================================
# OrchestratorResponse Tests
# =============================================================================


class TestOrchestratorResponse:
    """Tests for OrchestratorResponse output schema."""

    def test_minimal_response(self):
        """Should create with required fields."""
        response = OrchestratorResponse(content="Your deck looks good.")
        assert response.content == "Your deck looks good."
        assert response.recommendation is None
        assert response.confidence == 0.5
        assert response.subagent_results == []
        assert response.agents_consulted == []

    def test_full_response(self):
        """Should include all fields."""
        subagent_result = SubagentResult(
            agent_type="rules",
            query="test",
            response=SubagentResponse(
                content="Rules response",
                metadata=SubagentMetadata(agent_type="rules"),
            ),
            success=True,
        )
        response = OrchestratorResponse(
            content="Full response content",
            recommendation="Add Machete to your deck",
            confidence=0.85,
            subagent_results=[subagent_result],
            agents_consulted=["rules", "state"],
            metadata={"routing_reasoning": "rules: matched keywords"},
        )
        assert response.recommendation == "Add Machete to your deck"
        assert response.confidence == 0.85
        assert len(response.subagent_results) == 1
        assert response.agents_consulted == ["rules", "state"]
        assert "routing_reasoning" in response.metadata

    def test_error_response(self):
        """Should create error response."""
        response = OrchestratorResponse.error_response(
            error_message="Something went wrong",
            agents_consulted=["rules"],
        )
        assert response.content == "Something went wrong"
        assert response.confidence == 0.0
        assert response.agents_consulted == ["rules"]
        assert response.metadata.get("error") is True


# =============================================================================
# OrchestratorState Tests
# =============================================================================


class TestOrchestratorState:
    """Tests for OrchestratorState LangGraph state."""

    def test_initial_state(self):
        """Should create initial state with request."""
        request = OrchestratorRequest(message="test")
        state = OrchestratorState(request=request)

        assert state.request == request
        assert state.context == {}
        assert state.agents_to_consult == []
        assert state.routing_reasoning == ""
        assert state.subagent_results == []
        assert state.response is None
        assert state.error is None

    def test_state_with_routing(self):
        """Should hold routing information."""
        request = OrchestratorRequest(message="test")
        state = OrchestratorState(
            request=request,
            agents_to_consult=[SubagentType.RULES, SubagentType.STATE],
            routing_reasoning="rules: keyword match; state: deck context",
        )

        assert len(state.agents_to_consult) == 2
        assert SubagentType.RULES in state.agents_to_consult
        assert "keyword match" in state.routing_reasoning


# =============================================================================
# OrchestratorConfig Tests
# =============================================================================


class TestOrchestratorConfig:
    """Tests for OrchestratorConfig."""

    def test_default_config(self):
        """Should have sensible defaults."""
        config = OrchestratorConfig()

        assert config.temperature == 0.0
        assert config.max_tokens == 4096
        assert config.timeout_seconds == 60.0
        assert config.parallel_dispatch is True

    def test_custom_config(self):
        """Should accept custom values."""
        config = OrchestratorConfig(
            temperature=0.5,
            max_tokens=2048,
            timeout_seconds=30.0,
            parallel_dispatch=False,
        )

        assert config.temperature == 0.5
        assert config.max_tokens == 2048
        assert config.timeout_seconds == 30.0
        assert config.parallel_dispatch is False


# =============================================================================
# SubagentType Tests
# =============================================================================


class TestSubagentType:
    """Tests for SubagentType enum."""

    def test_all_types_defined(self):
        """Should have all expected subagent types."""
        assert SubagentType.RULES.value == "rules"
        assert SubagentType.STATE.value == "state"
        assert SubagentType.ACTION_SPACE.value == "action_space"
        assert SubagentType.SCENARIO.value == "scenario"

    def test_routing_keywords_defined_for_all_types(self):
        """Should have routing keywords for all types."""
        for agent_type in SubagentType:
            assert agent_type in ROUTING_KEYWORDS
            assert len(ROUTING_KEYWORDS[agent_type]) > 0


# =============================================================================
# Routing Logic Tests
# =============================================================================


class TestRoutingLogic:
    """Tests for the routing decision logic."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI"):
                return Orchestrator()

    def test_routes_to_rules_for_legality_questions(self, orchestrator):
        """Should route to rules agent for legality questions."""
        request = OrchestratorRequest(message="Can Roland include Shrivelling?")
        state = OrchestratorState(request=request)

        result = orchestrator._route_to_subagents_node(state)

        assert SubagentType.RULES in result["agents_to_consult"]

    def test_routes_to_state_for_deck_analysis(self, orchestrator):
        """Should route to state agent for deck analysis."""
        request = OrchestratorRequest(message="Analyze my deck for gaps")
        state = OrchestratorState(request=request)

        result = orchestrator._route_to_subagents_node(state)

        assert SubagentType.STATE in result["agents_to_consult"]

    def test_routes_to_action_space_for_card_search(self, orchestrator):
        """Should route to action space for card searches."""
        request = OrchestratorRequest(message="Find cards that deal damage")
        state = OrchestratorState(request=request)

        result = orchestrator._route_to_subagents_node(state)

        assert SubagentType.ACTION_SPACE in result["agents_to_consult"]

    def test_routes_to_scenario_for_scenario_prep(self, orchestrator):
        """Should route to scenario agent for preparation questions."""
        request = OrchestratorRequest(message="How should I prepare for The Gathering?")
        state = OrchestratorState(request=request)

        result = orchestrator._route_to_subagents_node(state)

        assert SubagentType.SCENARIO in result["agents_to_consult"]

    def test_adds_state_when_deck_context_provided(self, orchestrator):
        """Should add state agent when deck context is provided."""
        request = OrchestratorRequest(
            message="What do you think?",
            deck_cards=["01016", "01017"],
        )
        state = OrchestratorState(
            request=request,
            context={"deck_cards": ["01016", "01017"]},
        )

        result = orchestrator._route_to_subagents_node(state)

        assert SubagentType.STATE in result["agents_to_consult"]

    def test_adds_scenario_when_scenario_context_provided(self, orchestrator):
        """Should add scenario agent when scenario name is provided."""
        request = OrchestratorRequest(
            message="What cards should I add?",
            scenario_name="The Gathering",
        )
        state = OrchestratorState(
            request=request,
            context={"scenario_name": "The Gathering"},
        )

        result = orchestrator._route_to_subagents_node(state)

        assert SubagentType.SCENARIO in result["agents_to_consult"]

    def test_adds_action_space_when_xp_provided(self, orchestrator):
        """Should add action space when upgrade XP is provided."""
        request = OrchestratorRequest(
            message="What should I upgrade?",
            upgrade_xp=5,
        )
        state = OrchestratorState(
            request=request,
            context={"upgrade_xp": 5},
        )

        result = orchestrator._route_to_subagents_node(state)

        assert SubagentType.ACTION_SPACE in result["agents_to_consult"]

    def test_defaults_to_rules_for_generic_questions(self, orchestrator):
        """Should default to rules agent for generic questions."""
        request = OrchestratorRequest(message="Hello, help me please")
        state = OrchestratorState(request=request)

        result = orchestrator._route_to_subagents_node(state)

        assert SubagentType.RULES in result["agents_to_consult"]

    def test_routes_to_multiple_agents(self, orchestrator):
        """Should route to multiple agents when multiple keywords match."""
        request = OrchestratorRequest(
            message="Can I include cards that deal damage for The Gathering scenario?",
        )
        state = OrchestratorState(request=request)

        result = orchestrator._route_to_subagents_node(state)

        # Should match rules (include), action_space (cards that), and scenario
        assert len(result["agents_to_consult"]) >= 2

    def test_provides_routing_reasoning(self, orchestrator):
        """Should explain routing decisions."""
        request = OrchestratorRequest(message="Is Machete on the taboo list?")
        state = OrchestratorState(request=request)

        result = orchestrator._route_to_subagents_node(state)

        assert "taboo" in result["routing_reasoning"].lower()


# =============================================================================
# Context Analysis Tests
# =============================================================================


class TestContextAnalysis:
    """Tests for request analysis and context building."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI"):
                return Orchestrator()

    def test_builds_context_from_request(self, orchestrator):
        """Should build context dict from request fields."""
        request = OrchestratorRequest(
            message="Analyze my deck",
            investigator_id="01001",
            investigator_name="Roland Banks",
            deck_id="deck_123",
            scenario_name="The Gathering",
        )
        state = OrchestratorState(request=request)

        result = orchestrator._analyze_request_node(state)

        assert result["context"]["investigator_id"] == "01001"
        assert result["context"]["investigator_name"] == "Roland Banks"
        assert result["context"]["deck_id"] == "deck_123"
        assert result["context"]["scenario_name"] == "The Gathering"

    def test_excludes_none_values_from_context(self, orchestrator):
        """Should exclude None values from context."""
        request = OrchestratorRequest(
            message="Test",
            investigator_name="Roland Banks",
            # Other fields are None
        )
        state = OrchestratorState(request=request)

        result = orchestrator._analyze_request_node(state)

        assert "investigator_name" in result["context"]
        assert "deck_id" not in result["context"]
        assert "scenario_name" not in result["context"]


# =============================================================================
# Subagent Query Formatting Tests
# =============================================================================


class TestSubagentQueryFormatting:
    """Tests for subagent query formatting."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI"):
                return Orchestrator()

    def test_formats_state_query_for_gaps(self, orchestrator):
        """Should add gap analysis context for state queries."""
        request = OrchestratorRequest(message="What am I missing?")
        query = orchestrator._format_subagent_query(SubagentType.STATE, request)

        assert "gap" in query.lower() or "missing" in query.lower()

    def test_formats_action_space_query_with_xp(self, orchestrator):
        """Should include XP context for action space queries."""
        request = OrchestratorRequest(message="What should I upgrade?", upgrade_xp=5)
        query = orchestrator._format_subagent_query(SubagentType.ACTION_SPACE, request)

        assert "5 XP" in query or "5 xp" in query.lower()

    def test_formats_scenario_query_with_name(self, orchestrator):
        """Should include scenario name in scenario queries."""
        request = OrchestratorRequest(
            message="How should I prepare?",
            scenario_name="The Gathering",
        )
        query = orchestrator._format_subagent_query(SubagentType.SCENARIO, request)

        assert "The Gathering" in query

    def test_passes_through_rules_query(self, orchestrator):
        """Should pass through rules queries without modification."""
        request = OrchestratorRequest(message="Can Roland include Shrivelling?")
        query = orchestrator._format_subagent_query(SubagentType.RULES, request)

        assert query == request.message


# =============================================================================
# Synthesis Tests
# =============================================================================


class TestSynthesis:
    """Tests for response synthesis."""

    @pytest.fixture
    def mock_llm_response(self):
        """Create a mock LLM synthesis response."""
        mock_response = MagicMock()
        mock_response.content = """Based on my analysis, I recommend adding Machete to your deck.

**Recommendation**: Add 2x Machete for reliable combat damage.

The rules allow this card, and it synergizes well with your existing Guardian cards."""
        return mock_response

    @pytest.fixture
    def orchestrator(self, mock_llm_response):
        """Create orchestrator with mocked synthesis LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI") as mock_chat:
                mock_llm = MagicMock()
                mock_llm.invoke.return_value = mock_llm_response
                mock_chat.return_value = mock_llm
                return Orchestrator()

    def test_synthesizes_subagent_responses(self, orchestrator):
        """Should synthesize multiple subagent responses."""
        request = OrchestratorRequest(message="What cards should I add?")
        subagent_results = [
            SubagentResult(
                agent_type="rules",
                query="rules query",
                response=SubagentResponse(
                    content="You can include Guardian cards level 0-5.",
                    confidence=0.9,
                    metadata=SubagentMetadata(agent_type="rules"),
                ),
                success=True,
            ),
            SubagentResult(
                agent_type="state",
                query="state query",
                response=SubagentResponse(
                    content="Your deck lacks combat cards.",
                    confidence=0.85,
                    metadata=SubagentMetadata(agent_type="state"),
                ),
                success=True,
            ),
        ]
        state = OrchestratorState(
            request=request,
            agents_to_consult=[SubagentType.RULES, SubagentType.STATE],
            subagent_results=subagent_results,
            context={"investigator_name": "Roland Banks"},
        )

        result = orchestrator._synthesize_node(state)

        assert result["response"] is not None
        assert result["response"].content != ""

    def test_calculates_average_confidence(self, orchestrator):
        """Should average confidence from subagents."""
        request = OrchestratorRequest(message="test")
        subagent_results = [
            SubagentResult(
                agent_type="rules",
                query="query",
                response=SubagentResponse(
                    content="response",
                    confidence=0.8,
                    metadata=SubagentMetadata(agent_type="rules"),
                ),
                success=True,
            ),
            SubagentResult(
                agent_type="state",
                query="query",
                response=SubagentResponse(
                    content="response",
                    confidence=0.6,
                    metadata=SubagentMetadata(agent_type="state"),
                ),
                success=True,
            ),
        ]
        state = OrchestratorState(
            request=request,
            agents_to_consult=[SubagentType.RULES, SubagentType.STATE],
            subagent_results=subagent_results,
        )

        result = orchestrator._synthesize_node(state)

        # Average of 0.8 and 0.6 = 0.7
        assert result["response"].confidence == pytest.approx(0.7, rel=0.1)

    def test_extracts_recommendation(self, orchestrator):
        """Should extract recommendation from synthesized content."""
        request = OrchestratorRequest(message="test")
        subagent_results = [
            SubagentResult(
                agent_type="rules",
                query="query",
                response=SubagentResponse(
                    content="response",
                    confidence=0.8,
                    metadata=SubagentMetadata(agent_type="rules"),
                ),
                success=True,
            ),
        ]
        state = OrchestratorState(
            request=request,
            agents_to_consult=[SubagentType.RULES],
            subagent_results=subagent_results,
        )

        result = orchestrator._synthesize_node(state)

        # The mock response contains a recommendation
        assert result["response"].recommendation is not None
        assert "Machete" in result["response"].recommendation

    def test_includes_failed_subagents_in_metadata(self, orchestrator):
        """Should track failed subagent queries in metadata."""
        request = OrchestratorRequest(message="test")
        subagent_results = [
            SubagentResult(
                agent_type="rules",
                query="query",
                response=SubagentResponse(
                    content="response",
                    confidence=0.8,
                    metadata=SubagentMetadata(agent_type="rules"),
                ),
                success=True,
            ),
            SubagentResult(
                agent_type="state",
                query="query",
                response=None,
                success=False,
                error="Timeout",
            ),
        ]
        state = OrchestratorState(
            request=request,
            agents_to_consult=[SubagentType.RULES, SubagentType.STATE],
            subagent_results=subagent_results,
            routing_reasoning="test reasoning",
        )

        result = orchestrator._synthesize_node(state)

        assert result["response"].metadata["subagents_successful"] == 1
        assert result["response"].metadata["subagents_failed"] == 1


# =============================================================================
# Recommendation Extraction Tests
# =============================================================================


class TestRecommendationExtraction:
    """Tests for recommendation extraction from synthesized content."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI"):
                return Orchestrator()

    def test_extracts_recommendation_bold_format(self, orchestrator):
        """Should extract recommendation in bold format."""
        content = "Some text. **Recommendation**: Add Machete. More text."
        result = orchestrator._extract_recommendation(content)

        assert result is not None
        assert "Machete" in result

    def test_extracts_i_recommend_format(self, orchestrator):
        """Should extract 'I recommend' format."""
        content = "Based on my analysis, I recommend adding two copies of Machete."
        result = orchestrator._extract_recommendation(content)

        assert result is not None
        assert "Machete" in result

    def test_returns_none_when_no_recommendation(self, orchestrator):
        """Should return None when no recommendation found."""
        content = "Your deck looks balanced. No changes needed."
        result = orchestrator._extract_recommendation(content)

        assert result is None


# =============================================================================
# Full Process Tests
# =============================================================================


class TestOrchestratorProcess:
    """Tests for the full orchestration process."""

    @pytest.fixture
    def mock_subagents(self):
        """Create mock subagent responses."""
        rules_response = SubagentResponse(
            content="Roland can include Guardian cards level 0-5.",
            confidence=0.9,
            metadata=SubagentMetadata(agent_type="rules"),
        )
        state_response = SubagentResponse(
            content="Your deck has good combat coverage.",
            confidence=0.85,
            metadata=SubagentMetadata(agent_type="state"),
        )
        return {
            "rules": rules_response,
            "state": state_response,
        }

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    @patch("backend.services.orchestrator.create_rules_agent")
    @patch("backend.services.orchestrator.create_state_agent")
    def test_full_process_flow(
        self, mock_state_agent, mock_rules_agent, mock_chat, mock_subagents
    ):
        """Should execute full orchestration flow."""
        # Setup mocks
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Synthesized response."
        mock_chat.return_value = mock_llm

        mock_rules = MagicMock()
        mock_rules.query.return_value = mock_subagents["rules"]
        mock_rules_agent.return_value = mock_rules

        mock_state = MagicMock()
        mock_state.query.return_value = mock_subagents["state"]
        mock_state_agent.return_value = mock_state

        # Create orchestrator and process request
        orchestrator = Orchestrator()
        request = OrchestratorRequest(
            message="Can Roland include Shrivelling? Also analyze my deck.",
            investigator_name="Roland Banks",
            deck_cards=["01016", "01017"],
        )

        response = orchestrator.process(request)

        assert isinstance(response, OrchestratorResponse)
        assert response.content != ""
        assert len(response.agents_consulted) > 0

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    def test_handles_synthesis_error(self, mock_chat):
        """Should return error response on synthesis failure."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("API Error")
        mock_chat.return_value = mock_llm

        orchestrator = Orchestrator()
        request = OrchestratorRequest(message="Test question")

        # Mock subagent to avoid actual calls
        with patch.object(orchestrator, "_get_subagent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.query.return_value = SubagentResponse(
                content="response",
                metadata=SubagentMetadata(agent_type="rules"),
            )
            mock_get.return_value = mock_agent

            response = orchestrator.process(request)

        # Should still return a response (error response)
        assert isinstance(response, OrchestratorResponse)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    def test_handles_subagent_error(self, mock_chat):
        """Should handle subagent query errors gracefully."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Partial synthesis."
        mock_chat.return_value = mock_llm

        orchestrator = Orchestrator()
        request = OrchestratorRequest(message="Test question")

        # Mock subagent to raise an error
        with patch.object(orchestrator, "_get_subagent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.query.side_effect = Exception("Subagent error")
            mock_get.return_value = mock_agent

            response = orchestrator.process(request)

        # Should still return a response
        assert isinstance(response, OrchestratorResponse)
        # Should have recorded the failed subagent
        failed_results = [r for r in response.subagent_results if not r.success]
        assert len(failed_results) > 0


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    def test_create_orchestrator_default(self, mock_chat):
        """Should create orchestrator with default config."""
        orchestrator = create_orchestrator()

        assert isinstance(orchestrator, Orchestrator)
        assert orchestrator.config.temperature == 0.0

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    def test_create_orchestrator_with_config(self, mock_chat):
        """Should accept custom config."""
        config = OrchestratorConfig(temperature=0.5, max_tokens=2048)
        orchestrator = create_orchestrator(config=config)

        assert orchestrator.config.temperature == 0.5
        assert orchestrator.config.max_tokens == 2048


# =============================================================================
# process_chat_message Function Tests
# =============================================================================


class TestProcessChatMessage:
    """Tests for the process_chat_message entry point."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    @patch("backend.services.orchestrator.create_rules_agent")
    def test_process_chat_message_minimal(self, mock_rules, mock_chat):
        """Should process a simple message."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Here's my response."
        mock_chat.return_value = mock_llm

        mock_agent = MagicMock()
        mock_agent.query.return_value = SubagentResponse(
            content="Rules response",
            metadata=SubagentMetadata(agent_type="rules"),
        )
        mock_rules.return_value = mock_agent

        result = process_chat_message("Can Roland include Shrivelling?")

        assert "reply" in result
        assert "structured_data" in result
        assert "agents_consulted" in result
        assert result["reply"] != ""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    @patch("backend.services.orchestrator.create_rules_agent")
    def test_process_chat_message_with_context(self, mock_rules, mock_chat):
        """Should process message with context."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Response with context."
        mock_chat.return_value = mock_llm

        mock_agent = MagicMock()
        mock_agent.query.return_value = SubagentResponse(
            content="Rules response",
            metadata=SubagentMetadata(agent_type="rules"),
        )
        mock_rules.return_value = mock_agent

        result = process_chat_message(
            message="What cards can I add?",
            deck_id="deck_123",
            context={
                "investigator_name": "Roland Banks",
                "upgrade_xp": 5,
            },
        )

        assert "reply" in result
        assert result["structured_data"]["agents_consulted"]

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    @patch("backend.services.orchestrator.create_rules_agent")
    def test_process_chat_message_returns_structured_data(self, mock_rules, mock_chat):
        """Should include structured response data."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Detailed response."
        mock_chat.return_value = mock_llm

        mock_agent = MagicMock()
        mock_agent.query.return_value = SubagentResponse(
            content="Rules response",
            confidence=0.9,
            metadata=SubagentMetadata(agent_type="rules"),
        )
        mock_rules.return_value = mock_agent

        result = process_chat_message("Is Machete legal for Roland?")

        structured = result["structured_data"]
        assert "content" in structured
        assert "confidence" in structured
        assert "subagent_results" in structured


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Tests for backward compatibility with agent_orchestrator.py."""

    def test_imports_from_agent_orchestrator(self):
        """Should be able to import from agent_orchestrator."""
        from backend.services.agent_orchestrator import (
            Orchestrator,
            OrchestratorConfig,
            OrchestratorRequest,
            OrchestratorResponse,
            SubagentResult,
            SubagentType,
            create_orchestrator,
            process_chat_message,
        )

        assert Orchestrator is not None
        assert OrchestratorConfig is not None
        assert OrchestratorRequest is not None
        assert OrchestratorResponse is not None
        assert SubagentResult is not None
        assert SubagentType is not None
        assert create_orchestrator is not None
        assert process_chat_message is not None


# =============================================================================
# Async Tests
# =============================================================================


class TestAsyncOrchestrator:
    """Tests for async orchestrator methods."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI") as mock_chat:
                mock_llm = MagicMock()
                mock_llm.invoke.return_value.content = "Async response."
                mock_chat.return_value = mock_llm
                return Orchestrator()

    def test_aprocess_returns_response(self, orchestrator):
        """Should return response from async process."""
        import asyncio

        request = OrchestratorRequest(message="Test async")

        with patch.object(orchestrator, "_get_subagent") as mock_get:
            mock_agent = MagicMock()
            mock_agent.query.return_value = SubagentResponse(
                content="response",
                metadata=SubagentMetadata(agent_type="rules"),
            )
            mock_get.return_value = mock_agent

            response = asyncio.get_event_loop().run_until_complete(
                orchestrator.aprocess(request)
            )

        assert isinstance(response, OrchestratorResponse)

    def test_aprocess_method_exists(self, orchestrator):
        """Should have aprocess method for async operation."""
        assert hasattr(orchestrator, "aprocess")
        assert callable(orchestrator.aprocess)
