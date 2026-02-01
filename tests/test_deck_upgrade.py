"""Unit tests for the Deck Upgrade Flow."""

import os
from unittest.mock import MagicMock, patch

import pytest

from backend.models.deck_builder_models import (
    DeckBuilderSubagentResult,
    UpgradeRecommendation,
    UpgradeResponse,
)
from backend.models.subagent_models import SubagentMetadata, SubagentResponse
from backend.services.orchestrator import (
    DECK_UPGRADE_KEYWORDS,
    DeckUpgradeState,
    Orchestrator,
    OrchestratorRequest,
    UpgradeGoals,
    process_chat_message,
)


# =============================================================================
# UpgradeRecommendation Model Tests
# =============================================================================


class TestUpgradeRecommendation:
    """Tests for UpgradeRecommendation model."""

    def test_minimal_recommendation(self):
        """Should create recommendation with required fields."""
        rec = UpgradeRecommendation(
            priority=1,
            action="upgrade",
            add_card="01020",
            add_card_name="Machete (2)",
            xp_cost=2,
            reason="Better combat",
        )
        assert rec.priority == 1
        assert rec.action == "upgrade"
        assert rec.remove_card is None
        assert rec.add_card == "01020"
        assert rec.xp_cost == 2

    def test_full_recommendation(self):
        """Should create recommendation with all fields."""
        rec = UpgradeRecommendation(
            priority=1,
            action="swap",
            remove_card="01016",
            remove_card_name="Machete",
            add_card="01020",
            add_card_name="Machete (2)",
            xp_cost=2,
            reason="Upgrade core combat card",
        )
        assert rec.remove_card == "01016"
        assert rec.remove_card_name == "Machete"
        assert rec.add_card_name == "Machete (2)"

    def test_priority_must_be_positive(self):
        """Should reject priority < 1."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UpgradeRecommendation(
                priority=0,
                action="upgrade",
                add_card="01020",
                add_card_name="Card",
                xp_cost=1,
                reason="Test",
            )

    def test_xp_cost_non_negative(self):
        """Should reject negative XP costs."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UpgradeRecommendation(
                priority=1,
                action="upgrade",
                add_card="01020",
                add_card_name="Card",
                xp_cost=-1,
                reason="Test",
            )


# =============================================================================
# UpgradeResponse Model Tests
# =============================================================================


class TestUpgradeResponse:
    """Tests for UpgradeResponse model."""

    def test_minimal_response(self):
        """Should create with defaults."""
        response = UpgradeResponse()
        assert response.recommendations == []
        assert response.total_xp_cost == 0
        assert response.remaining_xp == 0
        assert response.available_xp == 0
        assert response.confidence == 0.5

    def test_full_response(self):
        """Should create with all fields."""
        rec = UpgradeRecommendation(
            priority=1,
            action="upgrade",
            add_card="01020",
            add_card_name="Machete (2)",
            xp_cost=2,
            reason="Better combat",
        )
        response = UpgradeResponse(
            recommendations=[rec],
            total_xp_cost=2,
            remaining_xp=3,
            available_xp=5,
            deck_improvement_summary="Improved combat capabilities",
            investigator_id="01001",
            investigator_name="Roland Banks",
            warnings=[],
            confidence=0.85,
        )
        assert len(response.recommendations) == 1
        assert response.total_xp_cost == 2
        assert response.remaining_xp == 3
        assert response.available_xp == 5
        assert "combat" in response.deck_improvement_summary

    def test_error_response(self):
        """Should create error response."""
        response = UpgradeResponse.error_response(
            error_message="No deck provided",
            investigator_id="01001",
            available_xp=5,
        )
        assert response.recommendations == []
        assert response.confidence == 0.0
        assert response.available_xp == 5
        assert response.remaining_xp == 5
        assert "No deck provided" in response.deck_improvement_summary
        assert response.metadata.get("error") is True


# =============================================================================
# UpgradeGoals Model Tests
# =============================================================================


class TestUpgradeGoals:
    """Tests for UpgradeGoals model."""

    def test_default_goals(self):
        """Should create with defaults."""
        goals = UpgradeGoals()
        assert goals.primary_goal == "general improvement"
        assert goals.specific_requests == []
        assert goals.cards_to_upgrade == []
        assert goals.cards_to_remove == []
        assert goals.avoid_cards == []

    def test_custom_goals(self):
        """Should accept custom values."""
        goals = UpgradeGoals(
            primary_goal="better willpower",
            specific_requests=["horror protection", "treachery handling"],
            cards_to_upgrade=["Machete"],
            cards_to_remove=["Knife"],
            avoid_cards=["Expensive cards"],
        )
        assert goals.primary_goal == "better willpower"
        assert len(goals.specific_requests) == 2
        assert "Machete" in goals.cards_to_upgrade


# =============================================================================
# DeckUpgradeState Tests
# =============================================================================


class TestDeckUpgradeState:
    """Tests for DeckUpgradeState model."""

    def test_initial_state(self):
        """Should create initial state with request."""
        request = OrchestratorRequest(
            message="Upgrade my deck",
            deck_cards=["01016", "01017"],
            upgrade_xp=5,
        )
        state = DeckUpgradeState(request=request)

        assert state.request == request
        assert state.context == {}
        assert state.upgrade_goals is None
        assert state.current_deck_cards == []
        assert state.deck_weaknesses == []
        assert state.available_xp == 0  # Set during graph execution
        assert state.recommendations == []
        assert state.response is None

    def test_state_with_analysis(self):
        """Should hold analysis results."""
        request = OrchestratorRequest(
            message="Upgrade for combat",
            deck_cards=["01016"],
            upgrade_xp=5,
        )
        state = DeckUpgradeState(
            request=request,
            upgrade_goals=UpgradeGoals(primary_goal="combat"),
            deck_weaknesses=["Insufficient combat capability"],
            deck_strengths=["Good card draw"],
            available_xp=5,
            spent_xp=3,
        )

        assert state.upgrade_goals.primary_goal == "combat"
        assert len(state.deck_weaknesses) == 1
        assert state.available_xp == 5
        assert state.spent_xp == 3


# =============================================================================
# Upgrade Request Detection Tests
# =============================================================================


class TestUpgradeRequestDetection:
    """Tests for upgrade request detection."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI"):
                return Orchestrator()

    def test_detects_explicit_upgrade_keywords(self, orchestrator):
        """Should detect explicit upgrade keywords."""
        request = OrchestratorRequest(
            message="Upgrade my deck with the new XP",
            deck_cards=["01016", "01017"],
            upgrade_xp=5,
        )
        assert orchestrator._is_upgrade_request(request) is True

    def test_detects_spend_xp_intent(self, orchestrator):
        """Should detect 'spend xp' intent."""
        request = OrchestratorRequest(
            message="I want to spend my XP",
            deck_cards=["01016"],
            upgrade_xp=5,
        )
        assert orchestrator._is_upgrade_request(request) is True

    def test_detects_improve_deck_intent(self, orchestrator):
        """Should detect 'improve deck' intent."""
        request = OrchestratorRequest(
            message="How can I improve my deck?",
            deck_cards=["01016"],
            upgrade_xp=5,
        )
        assert orchestrator._is_upgrade_request(request) is True

    def test_requires_deck_context(self, orchestrator):
        """Should require deck context."""
        request = OrchestratorRequest(
            message="Upgrade my deck",
            upgrade_xp=5,
            # No deck_cards or deck_id
        )
        assert orchestrator._is_upgrade_request(request) is False

    def test_requires_xp_available(self, orchestrator):
        """Should require XP available."""
        request = OrchestratorRequest(
            message="Upgrade my deck",
            deck_cards=["01016"],
            # No upgrade_xp or upgrade_xp=0
        )
        assert orchestrator._is_upgrade_request(request) is False

    def test_zero_xp_is_not_upgrade(self, orchestrator):
        """Should not detect upgrade with 0 XP."""
        request = OrchestratorRequest(
            message="Upgrade my deck",
            deck_cards=["01016"],
            upgrade_xp=0,
        )
        assert orchestrator._is_upgrade_request(request) is False

    def test_deck_id_counts_as_context(self, orchestrator):
        """Should accept deck_id as deck context."""
        request = OrchestratorRequest(
            message="What should I upgrade?",
            deck_id="deck_123",
            upgrade_xp=5,
        )
        assert orchestrator._is_upgrade_request(request) is True

    def test_new_deck_request_not_upgrade(self, orchestrator):
        """Should not confuse new deck with upgrade."""
        request = OrchestratorRequest(
            message="Build me a new deck",
            investigator_id="01001",
            # No existing deck, even with XP
            upgrade_xp=5,
        )
        assert orchestrator._is_upgrade_request(request) is False

    def test_all_upgrade_keywords_work(self, orchestrator):
        """All defined upgrade keywords should trigger detection."""
        for keyword in DECK_UPGRADE_KEYWORDS:
            request = OrchestratorRequest(
                message=keyword,
                deck_cards=["01016"],
                upgrade_xp=5,
            )
            assert orchestrator._is_upgrade_request(request) is True, (
                f"Keyword '{keyword}' not detected"
            )


# =============================================================================
# Upgrade Pipeline Node Tests
# =============================================================================


class TestUpgradePipelineNodes:
    """Tests for individual upgrade pipeline nodes."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI") as mock_chat:
                mock_llm = MagicMock()
                mock_llm.invoke.return_value.content = '{"primary_goal": "combat", "specific_requests": [], "cards_to_upgrade": [], "cards_to_remove": [], "avoid_cards": []}'
                mock_chat.return_value = mock_llm
                return Orchestrator()

    def test_extract_upgrade_goals_basic(self, orchestrator):
        """Should extract basic upgrade goals."""
        request = OrchestratorRequest(
            message="I need better combat",
            investigator_name="Roland Banks",
            deck_cards=["01016"],
            upgrade_xp=5,
        )
        state = DeckUpgradeState(request=request)

        result = orchestrator._extract_upgrade_goals_node(state)

        assert "upgrade_goals" in result
        assert result["available_xp"] == 5
        assert result["investigator_name"] == "Roland Banks"

    def test_generate_recommendations_with_candidates(self, orchestrator):
        """Should generate recommendations from candidates."""
        request = OrchestratorRequest(
            message="Upgrade my deck",
            deck_cards=["01016"],
            upgrade_xp=5,
        )
        state = DeckUpgradeState(
            request=request,
            available_xp=5,
            upgrade_candidates=[
                {
                    "card_id": "01020",
                    "name": "Machete (2)",
                    "xp_cost": 2,
                    "relevance_score": 0.8,
                    "reason": "Combat upgrade",
                    "card_type": "Asset",
                },
                {
                    "card_id": "01021",
                    "name": "Beat Cop (2)",
                    "xp_cost": 2,
                    "relevance_score": 0.7,
                    "reason": "Ally upgrade",
                    "card_type": "Asset",
                },
            ],
            current_deck_cards=[
                {"code": "01016", "name": "Machete", "xp_cost": 0, "type_name": "Asset"},
            ],
        )

        result = orchestrator._generate_recommendations_node(state)

        assert "recommendations" in result
        assert len(result["recommendations"]) >= 1
        # Should respect XP budget (2+2 = 4 <= 5)
        total_spent = sum(r.xp_cost for r in result["recommendations"])
        assert total_spent <= 5

    def test_generate_recommendations_respects_budget(self, orchestrator):
        """Should not exceed XP budget."""
        request = OrchestratorRequest(
            message="Upgrade",
            deck_cards=["01016"],
            upgrade_xp=3,
        )
        state = DeckUpgradeState(
            request=request,
            available_xp=3,
            upgrade_candidates=[
                {"card_id": "01020", "name": "Card A", "xp_cost": 2, "relevance_score": 0.9},
                {"card_id": "01021", "name": "Card B", "xp_cost": 2, "relevance_score": 0.8},
                {"card_id": "01022", "name": "Card C", "xp_cost": 2, "relevance_score": 0.7},
            ],
            current_deck_cards=[],
        )

        result = orchestrator._generate_recommendations_node(state)

        total_spent = sum(r.xp_cost for r in result["recommendations"])
        # Can only fit one 2-XP card in 3 XP budget
        assert total_spent <= 3

    def test_generate_recommendations_zero_xp(self, orchestrator):
        """Should handle 0 XP gracefully."""
        request = OrchestratorRequest(
            message="Upgrade",
            deck_cards=["01016"],
            upgrade_xp=0,
        )
        state = DeckUpgradeState(
            request=request,
            available_xp=0,
            upgrade_candidates=[
                {"card_id": "01020", "name": "Card A", "xp_cost": 2, "relevance_score": 0.9},
            ],
            current_deck_cards=[],
        )

        result = orchestrator._generate_recommendations_node(state)

        assert result["recommendations"] == []
        assert "No XP available" in result["warnings"][0]

    def test_generate_recommendations_prioritizes_by_relevance(self, orchestrator):
        """Should prioritize high-relevance cards."""
        request = OrchestratorRequest(
            message="Upgrade",
            deck_cards=["01016"],
            upgrade_xp=10,
        )
        state = DeckUpgradeState(
            request=request,
            available_xp=10,
            upgrade_candidates=[
                {"card_id": "01020", "name": "Low Relevance", "xp_cost": 1, "relevance_score": 0.3},
                {
                    "card_id": "01021",
                    "name": "High Relevance",
                    "xp_cost": 1,
                    "relevance_score": 0.9,
                },
                {
                    "card_id": "01022",
                    "name": "Medium Relevance",
                    "xp_cost": 1,
                    "relevance_score": 0.6,
                },
            ],
            current_deck_cards=[],
        )

        result = orchestrator._generate_recommendations_node(state)

        # First recommendation should be the highest relevance
        assert result["recommendations"][0].add_card_name == "High Relevance"


# =============================================================================
# Full Upgrade Flow Tests
# =============================================================================


class TestFullUpgradeFlow:
    """Tests for the complete upgrade flow."""

    @pytest.fixture
    def mock_state_agent(self):
        """Create mock StateAgent response."""
        from backend.services.subagents.state_agent import StateResponse

        return StateResponse(
            content="Deck analysis complete",
            confidence=0.85,
            metadata=SubagentMetadata(agent_type="state"),
            identified_gaps=["Insufficient willpower"],
            strengths=["Strong combat"],
            upgrade_priority=["Machete"],
            total_cards=30,
        )

    @pytest.fixture
    def mock_action_space_response(self):
        """Create mock ActionSpaceAgent response."""
        from backend.services.subagents.action_space_agent import (
            ActionSpaceResponse,
            CardCandidate,
        )

        return ActionSpaceResponse(
            content="Found 2 cards",
            confidence=0.85,
            metadata=SubagentMetadata(agent_type="action_space"),
            candidates=[
                CardCandidate(
                    card_id="01020",
                    name="Machete (2)",
                    xp_cost=2,
                    relevance_score=0.85,
                    reason="Upgraded combat weapon",
                    card_type="Asset",
                ),
            ],
        )

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    @patch("backend.services.orchestrator.create_state_agent")
    @patch("backend.services.orchestrator.create_action_space_agent")
    def test_upgrade_flow_returns_upgrade_response(
        self,
        mock_action_agent,
        mock_state_agent_fn,
        mock_chat,
        mock_state_agent,
        mock_action_space_response,
    ):
        """Should return UpgradeResponse for upgrade requests."""
        # Setup mocks
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = '{"primary_goal": "combat", "specific_requests": [], "cards_to_upgrade": [], "cards_to_remove": [], "avoid_cards": []}'
        mock_chat.return_value = mock_llm

        mock_state = MagicMock()
        mock_state.analyze.return_value = mock_state_agent
        mock_state_agent_fn.return_value = mock_state

        mock_action = MagicMock()
        mock_action.search.return_value = mock_action_space_response
        mock_action_agent.return_value = mock_action

        # Process upgrade request
        orchestrator = Orchestrator()
        request = OrchestratorRequest(
            message="Upgrade my deck for better combat",
            investigator_id="01001",
            investigator_name="Roland Banks",
            deck_cards=["01016", "01017"],
            upgrade_xp=5,
        )

        # Mock ChromaClient for card lookup
        with patch("backend.services.chroma_client.ChromaClient") as mock_chroma:
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get_card.return_value = {
                "code": "01016",
                "name": "Machete",
                "xp_cost": 0,
                "type_name": "Asset",
            }
            mock_chroma_instance.get_character.return_value = {
                "name": "Roland Banks",
                "faction_name": "Guardian",
            }
            mock_chroma.return_value = mock_chroma_instance

            response = orchestrator.process(request)

        assert isinstance(response, UpgradeResponse)
        assert response.available_xp == 5

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    def test_upgrade_flow_handles_no_deck(self, mock_chat):
        """Should handle missing deck gracefully."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "{}"
        mock_chat.return_value = mock_llm

        orchestrator = Orchestrator()
        request = OrchestratorRequest(
            message="Upgrade my deck",
            investigator_id="01001",
            upgrade_xp=5,
            # Note: No deck_cards, so won't trigger upgrade flow
        )

        # Should not be detected as upgrade (missing deck)
        assert orchestrator._is_upgrade_request(request) is False


# =============================================================================
# process_chat_message Integration Tests
# =============================================================================


class TestProcessChatMessageUpgrade:
    """Tests for process_chat_message with upgrade requests."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    @patch("backend.services.orchestrator.create_state_agent")
    @patch("backend.services.orchestrator.create_action_space_agent")
    def test_process_chat_message_upgrade_flow(
        self, mock_action_agent, mock_state_agent, mock_chat
    ):
        """Should process upgrade request through chat interface."""
        from backend.services.subagents.action_space_agent import (
            ActionSpaceResponse,
            CardCandidate,
        )
        from backend.services.subagents.state_agent import StateResponse

        # Setup mocks
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = '{"primary_goal": "general improvement", "improvement_summary": "Deck will be stronger."}'
        mock_chat.return_value = mock_llm

        mock_state = MagicMock()
        mock_state.analyze.return_value = StateResponse(
            content="Analysis",
            confidence=0.8,
            metadata=SubagentMetadata(agent_type="state"),
            identified_gaps=[],
            strengths=[],
            upgrade_priority=[],
        )
        mock_state_agent.return_value = mock_state

        mock_action = MagicMock()
        mock_action.search.return_value = ActionSpaceResponse(
            content="Found cards",
            confidence=0.8,
            metadata=SubagentMetadata(agent_type="action_space"),
            candidates=[
                CardCandidate(
                    card_id="01020",
                    name="Upgrade Card",
                    xp_cost=2,
                    relevance_score=0.8,
                    reason="Good upgrade",
                ),
            ],
        )
        mock_action_agent.return_value = mock_action

        with patch("backend.services.chroma_client.ChromaClient") as mock_chroma:
            mock_chroma_instance = MagicMock()
            mock_chroma_instance.get_card.return_value = {"code": "01016", "name": "Basic Card"}
            mock_chroma_instance.get_character.return_value = {
                "name": "Roland Banks",
                "faction_name": "Guardian",
            }
            mock_chroma.return_value = mock_chroma_instance

            result = process_chat_message(
                message="Upgrade my deck",
                context={
                    "investigator_id": "01001",
                    "deck_cards": ["01016"],
                    "upgrade_xp": 5,
                },
            )

        assert "reply" in result
        assert "structured_data" in result
        # Should have recommendations in structured data
        structured = result["structured_data"]
        assert "recommendations" in structured


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestUpgradeEdgeCases:
    """Tests for edge cases in deck upgrade flow."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI") as mock_chat:
                mock_llm = MagicMock()
                mock_llm.invoke.return_value.content = "{}"
                mock_chat.return_value = mock_llm
                return Orchestrator()

    def test_handles_no_candidates_found(self, orchestrator):
        """Should handle case when no upgrade candidates are found."""
        request = OrchestratorRequest(
            message="Upgrade",
            deck_cards=["01016"],
            upgrade_xp=5,
        )
        state = DeckUpgradeState(
            request=request,
            available_xp=5,
            upgrade_candidates=[],  # No candidates found
            current_deck_cards=[],
        )

        result = orchestrator._generate_recommendations_node(state)

        assert result["recommendations"] == []
        assert any("No upgrade candidates" in w for w in result["warnings"])

    def test_handles_all_candidates_too_expensive(self, orchestrator):
        """Should handle when all candidates exceed budget."""
        request = OrchestratorRequest(
            message="Upgrade",
            deck_cards=["01016"],
            upgrade_xp=1,  # Very limited budget
        )
        state = DeckUpgradeState(
            request=request,
            available_xp=1,
            upgrade_candidates=[
                {"card_id": "01020", "name": "Card A", "xp_cost": 3, "relevance_score": 0.9},
                {"card_id": "01021", "name": "Card B", "xp_cost": 2, "relevance_score": 0.8},
            ],
            current_deck_cards=[],
        )

        result = orchestrator._generate_recommendations_node(state)

        # No recommendations since all exceed budget
        assert result["recommendations"] == []

    def test_identifies_direct_upgrade_action(self, orchestrator):
        """Should identify when card is a direct upgrade of existing card."""
        request = OrchestratorRequest(
            message="Upgrade",
            deck_cards=["01016"],
            upgrade_xp=5,
        )
        state = DeckUpgradeState(
            request=request,
            available_xp=5,
            upgrade_candidates=[
                {
                    "card_id": "01020",
                    "name": "Machete (2)",  # Upgraded version
                    "xp_cost": 2,
                    "relevance_score": 0.9,
                    "card_type": "Asset",
                },
            ],
            current_deck_cards=[
                {
                    "code": "01016",
                    "name": "Machete",
                    "xp_cost": 0,
                    "type_name": "Asset",
                },  # Level 0 version
            ],
        )

        result = orchestrator._generate_recommendations_node(state)

        # Should be marked as "upgrade" action
        assert len(result["recommendations"]) == 1
        rec = result["recommendations"][0]
        assert rec.action == "upgrade"
        assert rec.remove_card == "01016"
        assert rec.remove_card_name == "Machete"

    def test_scenario_context_integration(self, orchestrator):
        """Should integrate scenario priorities."""
        request = OrchestratorRequest(
            message="Upgrade for The Gathering",
            deck_cards=["01016"],
            upgrade_xp=5,
            scenario_name="The Gathering",
        )
        state = DeckUpgradeState(request=request)

        result = orchestrator._extract_upgrade_goals_node(state)

        assert result["context"].get("scenario_name") == "The Gathering"
