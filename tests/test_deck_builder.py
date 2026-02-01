"""Unit tests for the New Deck Creation Flow (Issue #13).

This module tests the deck building functionality including:
- Request detection (is_new_deck_request)
- Goal extraction
- Deck building algorithm
- Integration tests for different investigators
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.models.deck_builder_models import (
    CardSelection,
    DeckBuilderSubagentResult,
    DeckBuildGoals,
    DeckRecommendationResponse,
    DeckSummary,
    InvestigatorConstraints,
    NewDeckResponse,
    Recommendation,
)
from backend.services.orchestrator import (
    DECK_CREATION_KEYWORDS,
    DeckBuilderState,
    Orchestrator,
    OrchestratorRequest,
)

# =============================================================================
# Model Tests
# =============================================================================


class TestCardSelection:
    """Tests for CardSelection model."""

    def test_valid_card_selection(self):
        """Should accept valid card selection."""
        card = CardSelection(
            card_id="01016",
            name=".45 Automatic",
            quantity=2,
            reason="Good combat card",
            category="combat",
        )
        assert card.card_id == "01016"
        assert card.name == ".45 Automatic"
        assert card.quantity == 2
        assert card.category == "combat"

    def test_quantity_bounds(self):
        """Should enforce quantity between 1 and 2."""
        with pytest.raises(ValidationError):
            CardSelection(
                card_id="01016",
                name="Test",
                quantity=0,
                reason="Test",
                category="test",
            )

        with pytest.raises(ValidationError):
            CardSelection(
                card_id="01016",
                name="Test",
                quantity=3,
                reason="Test",
                category="test",
            )


class TestDeckBuildGoals:
    """Tests for DeckBuildGoals model."""

    def test_minimal_goals(self):
        """Should accept just primary focus."""
        goals = DeckBuildGoals(primary_focus="combat")
        assert goals.primary_focus == "combat"
        assert goals.secondary_focus is None
        assert goals.specific_requests == []
        assert goals.avoid_cards == []

    def test_full_goals(self):
        """Should accept all fields."""
        goals = DeckBuildGoals(
            primary_focus="combat",
            secondary_focus="clues",
            specific_requests=["lots of card draw", "cheap cards"],
            avoid_cards=["expensive assets"],
        )
        assert goals.primary_focus == "combat"
        assert goals.secondary_focus == "clues"
        assert len(goals.specific_requests) == 2
        assert len(goals.avoid_cards) == 1


class TestInvestigatorConstraints:
    """Tests for InvestigatorConstraints model."""

    def test_basic_constraints(self):
        """Should create basic investigator constraints."""
        constraints = InvestigatorConstraints(
            investigator_id="01001",
            investigator_name="Roland Banks",
            primary_class="Guardian",
        )
        assert constraints.investigator_id == "01001"
        assert constraints.primary_class == "Guardian"
        assert constraints.deck_size == 30  # default
        assert constraints.secondary_class is None

    def test_with_secondary_class(self):
        """Should handle secondary class access."""
        constraints = InvestigatorConstraints(
            investigator_id="01004",
            investigator_name="Agnes Baker",
            primary_class="Mystic",
            secondary_class="Survivor",
            secondary_level=2,
        )
        assert constraints.secondary_class == "Survivor"
        assert constraints.secondary_level == 2


class TestNewDeckResponse:
    """Tests for NewDeckResponse model."""

    def test_minimal_response(self):
        """Should accept minimal response."""
        response = NewDeckResponse(
            deck_name="Test Deck",
            investigator_id="01001",
            investigator_name="Roland Banks",
        )
        assert response.deck_name == "Test Deck"
        assert response.total_cards == 0
        assert response.confidence == 0.5

    def test_error_response(self):
        """Should create error response."""
        response = NewDeckResponse.error_response(
            error_message="Something went wrong",
            investigator_id="01001",
        )
        assert response.deck_name == "Error"
        assert response.confidence == 0.0
        assert "Something went wrong" in response.reasoning
        assert response.metadata.get("error") is True


# =============================================================================
# Detection Tests
# =============================================================================


class TestDeckCreationKeywords:
    """Tests for deck creation keyword detection."""

    def test_keywords_exist(self):
        """Should have deck creation keywords defined."""
        assert len(DECK_CREATION_KEYWORDS) > 0
        assert "build me" in DECK_CREATION_KEYWORDS
        assert "new deck" in DECK_CREATION_KEYWORDS

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI"):
                return Orchestrator()

    @pytest.mark.parametrize(
        "message,expected",
        [
            ("Build me a combat deck", True),
            ("Build a deck for Roland Banks", True),
            ("Create a deck focused on clues", True),
            ("Make me a deck with lots of card draw", True),
            ("Start a new deck for Agnes", True),
            ("I want a fresh deck", True),
            ("What cards should I include?", False),
            ("What are the best upgrades?", False),
            ("How do I prepare for The Gathering?", False),
            ("Can Roland include Shrivelling?", False),
        ],
    )
    def test_is_new_deck_request_messages(self, orchestrator, message, expected):
        """Should detect deck creation requests from various messages."""
        request = OrchestratorRequest(message=message)
        result = orchestrator._is_new_deck_request(request)
        assert result == expected, f"Failed for message: {message}"

    def test_is_new_deck_request_with_investigator(self, orchestrator):
        """Should detect deck request when investigator is specified."""
        request = OrchestratorRequest(
            message="Build a deck for this investigator",
            investigator_id="01001",
        )
        assert orchestrator._is_new_deck_request(request) is True

    def test_is_not_new_deck_when_deck_exists(self, orchestrator):
        """Should not detect as new deck when deck already exists."""
        request = OrchestratorRequest(
            message="Build on this deck",
            investigator_id="01001",
            deck_cards=["01016", "01017"],
        )
        # With existing deck_cards, it's modifying not creating
        assert orchestrator._is_new_deck_request(request) is False


# =============================================================================
# DeckBuilderState Tests
# =============================================================================


class TestDeckBuilderState:
    """Tests for DeckBuilderState."""

    def test_initial_state(self):
        """Should create initial state."""
        request = OrchestratorRequest(message="Build me a combat deck")
        state = DeckBuilderState(request=request)

        assert state.request == request
        assert state.context == {}
        assert state.goals is None
        assert state.constraints is None
        assert state.candidate_cards == []
        assert state.selected_cards == []
        assert state.current_card_count == 0

    def test_state_with_goals(self):
        """Should accept goals."""
        request = OrchestratorRequest(message="Build me a combat deck")
        goals = DeckBuildGoals(primary_focus="combat")
        state = DeckBuilderState(
            request=request,
            goals=goals,
        )

        assert state.goals.primary_focus == "combat"


# =============================================================================
# Goal Extraction Tests
# =============================================================================


class TestGoalExtraction:
    """Tests for goal extraction from user messages."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI") as mock_chat:
                mock_llm = MagicMock()
                mock_chat.return_value = mock_llm
                orch = Orchestrator()
                orch._mock_llm = mock_llm
                return orch

    def test_extract_combat_focus(self, orchestrator):
        """Should extract combat focus from message."""
        mock_response = MagicMock()
        mock_response.content = '{"primary_focus": "combat", "secondary_focus": null, "specific_requests": [], "avoid_cards": []}'
        orchestrator._mock_llm.invoke.return_value = mock_response

        request = OrchestratorRequest(
            message="Build me a combat deck",
            investigator_id="01001",
        )
        state = DeckBuilderState(request=request)

        result = orchestrator._extract_goals_node(state)

        assert result["goals"].primary_focus == "combat"

    def test_extract_clues_focus(self, orchestrator):
        """Should extract clues focus from message."""
        mock_response = MagicMock()
        mock_response.content = '{"primary_focus": "clues", "secondary_focus": "support", "specific_requests": ["lots of draw"], "avoid_cards": []}'
        orchestrator._mock_llm.invoke.return_value = mock_response

        request = OrchestratorRequest(
            message="Build me a clue-gathering deck with lots of card draw",
            investigator_id="01002",
        )
        state = DeckBuilderState(request=request)

        result = orchestrator._extract_goals_node(state)

        assert result["goals"].primary_focus == "clues"
        assert result["goals"].secondary_focus == "support"

    def test_extract_goals_handles_invalid_json(self, orchestrator):
        """Should handle invalid JSON gracefully."""
        mock_response = MagicMock()
        mock_response.content = "I think you want a combat deck."
        orchestrator._mock_llm.invoke.return_value = mock_response

        request = OrchestratorRequest(
            message="Build me a deck",
            investigator_id="01001",
        )
        state = DeckBuilderState(request=request)

        result = orchestrator._extract_goals_node(state)

        # Should default to flex
        assert result["goals"].primary_focus == "flex"


# =============================================================================
# Deck Building Algorithm Tests
# =============================================================================


class TestDeckBuildingAlgorithm:
    """Tests for the deck building algorithm."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI"):
                return Orchestrator()

    def test_build_deck_fills_slots(self, orchestrator):
        """Should fill deck slots with cards."""
        # Create state with candidates
        request = OrchestratorRequest(message="Build deck", investigator_id="01001")
        goals = DeckBuildGoals(primary_focus="combat")
        constraints = InvestigatorConstraints(
            investigator_id="01001",
            investigator_name="Roland Banks",
            primary_class="Guardian",
            deck_size=30,
        )

        # Create many candidate cards
        candidates = []
        for i in range(50):
            candidates.append({
                "card_id": f"card_{i:03d}",
                "name": f"Test Card {i}",
                "xp_cost": 0,
                "relevance_score": 0.8 - (i * 0.01),
                "reason": "Test card",
                "card_type": "Asset",
                "class_name": "Guardian",
                "cost": 2,
                "search_category": "primary" if i < 20 else "other",
                "capability": "combat" if i < 20 else None,
            })

        state = DeckBuilderState(
            request=request,
            goals=goals,
            constraints=constraints,
            candidate_cards=candidates,
        )

        result = orchestrator._build_deck_node(state)

        # Should have selected cards
        assert len(result["selected_cards"]) > 0
        # Should have cards up to deck size
        assert result["current_card_count"] <= 30

    def test_build_deck_respects_quantity_limit(self, orchestrator):
        """Should not add more than 2 copies of a card."""
        request = OrchestratorRequest(message="Build deck", investigator_id="01001")
        goals = DeckBuildGoals(primary_focus="combat")
        constraints = InvestigatorConstraints(
            investigator_id="01001",
            investigator_name="Roland Banks",
            primary_class="Guardian",
            deck_size=30,
        )

        # Create just a few high-relevance candidates
        candidates = [
            {
                "card_id": "card_001",
                "name": "Best Card",
                "xp_cost": 0,
                "relevance_score": 0.95,
                "reason": "Great combat card",
                "card_type": "Asset",
                "class_name": "Guardian",
                "cost": 2,
                "search_category": "primary",
                "capability": "combat",
            },
        ]

        state = DeckBuilderState(
            request=request,
            goals=goals,
            constraints=constraints,
            candidate_cards=candidates,
        )

        result = orchestrator._build_deck_node(state)

        # Count how many copies of card_001 were added
        total_copies = sum(
            card.quantity
            for card in result["selected_cards"]
            if card.card_id == "card_001"
        )

        assert total_copies <= 2

    def test_build_deck_categorizes_cards(self, orchestrator):
        """Should categorize cards by role."""
        request = OrchestratorRequest(message="Build deck", investigator_id="01001")
        goals = DeckBuildGoals(primary_focus="combat", secondary_focus="clues")
        constraints = InvestigatorConstraints(
            investigator_id="01001",
            investigator_name="Roland Banks",
            primary_class="Guardian",
            deck_size=30,
        )

        candidates = [
            {"card_id": "combat_01", "name": "Combat Card", "xp_cost": 0,
             "relevance_score": 0.9, "reason": "Combat", "card_type": "Asset",
             "class_name": "Guardian", "cost": 2, "search_category": "primary",
             "capability": "combat"},
            {"card_id": "clues_01", "name": "Clue Card", "xp_cost": 0,
             "relevance_score": 0.85, "reason": "Clues", "card_type": "Event",
             "class_name": "Seeker", "cost": 1, "search_category": "secondary",
             "capability": "clues"},
            {"card_id": "econ_01", "name": "Economy Card", "xp_cost": 0,
             "relevance_score": 0.8, "reason": "Resources", "card_type": "Asset",
             "class_name": "Neutral", "cost": 0, "search_category": "economy",
             "capability": "economy"},
        ]

        state = DeckBuilderState(
            request=request,
            goals=goals,
            constraints=constraints,
            candidate_cards=candidates,
        )

        result = orchestrator._build_deck_node(state)

        # Check that cards have different categories
        categories = {card.category for card in result["selected_cards"]}
        assert len(categories) >= 1  # At least some cards selected


# =============================================================================
# Integration Tests
# =============================================================================


class TestDeckBuilderIntegration:
    """Integration tests for the full deck building flow."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create orchestrator with all dependencies mocked."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI") as mock_chat:
                mock_llm = MagicMock()
                mock_chat.return_value = mock_llm
                orch = Orchestrator()
                orch._mock_llm = mock_llm
                return orch

    def _setup_mock_llm(self, orchestrator, goals_json, synthesis_json):
        """Set up mock LLM to return specific responses."""
        def mock_invoke(messages):
            content = str(messages[1].content) if len(messages) > 1 else ""
            mock_response = MagicMock()
            if "Extract" in content or "goals" in content.lower():
                mock_response.content = goals_json
            else:
                mock_response.content = synthesis_json
            return mock_response

        orchestrator._mock_llm.invoke.side_effect = mock_invoke

    @patch("backend.services.chroma_client.ChromaClient")
    @patch.object(Orchestrator, "_get_subagent")
    def test_full_flow_roland_combat(
        self, mock_get_subagent, mock_chroma, mock_orchestrator
    ):
        """Should build a complete combat deck for Roland Banks."""
        # Setup mocks
        self._setup_mock_llm(
            mock_orchestrator,
            '{"primary_focus": "combat", "secondary_focus": null, "specific_requests": [], "avoid_cards": []}',
            '{"deck_name": "Roland\'s Arsenal", "reasoning": "A focused combat deck for fighting enemies."}',
        )

        # Mock ChromaDB to return investigator
        mock_chroma_instance = MagicMock()
        mock_chroma_instance.get_character.return_value = {
            "name": "Roland Banks",
            "faction_name": "Guardian",
            "deck_options": "",
        }
        mock_chroma.return_value = mock_chroma_instance

        # Mock subagents
        mock_action_agent = MagicMock()
        mock_action_response = MagicMock()
        mock_action_response.candidates = []
        # Add some mock candidates
        for i in range(20):
            mock_candidate = MagicMock()
            mock_candidate.card_id = f"0101{i:01d}"
            mock_candidate.name = f"Guardian Card {i}"
            mock_candidate.xp_cost = 0
            mock_candidate.relevance_score = 0.8
            mock_candidate.reason = "Good card"
            mock_candidate.card_type = "Asset"
            mock_candidate.class_name = "Guardian"
            mock_candidate.cost = 2
            mock_candidate.traits = "Item"
            mock_candidate.text = "Fight action"
            mock_action_response.candidates.append(mock_candidate)
        mock_action_agent.search.return_value = mock_action_response

        mock_state_agent = MagicMock()
        mock_state_response = MagicMock()
        mock_state_response.identified_gaps = []
        mock_state_agent.query.return_value = mock_state_response

        def get_subagent(agent_type):
            if agent_type.value == "action_space":
                return mock_action_agent
            elif agent_type.value == "state":
                return mock_state_agent
            return MagicMock()

        mock_get_subagent.side_effect = get_subagent

        # Make the request
        request = OrchestratorRequest(
            message="Build me a combat-focused deck for Roland Banks",
            investigator_id="01001",
            investigator_name="Roland Banks",
        )

        response = mock_orchestrator.process(request)

        # Verify response
        assert isinstance(response, NewDeckResponse)
        assert response.investigator_id == "01001"
        assert response.archetype is not None
        assert "combat" in response.archetype.lower() or "guardian" in response.archetype.lower()

    @patch("backend.services.chroma_client.ChromaClient")
    @patch.object(Orchestrator, "_get_subagent")
    def test_full_flow_daisy_clues(
        self, mock_get_subagent, mock_chroma, mock_orchestrator
    ):
        """Should build a complete clue-gathering deck for Daisy Walker."""
        # Setup mocks
        self._setup_mock_llm(
            mock_orchestrator,
            '{"primary_focus": "clues", "secondary_focus": null, "specific_requests": ["tome cards"], "avoid_cards": []}',
            '{"deck_name": "Daisy\'s Library", "reasoning": "A focused clue-gathering deck with tomes."}',
        )

        mock_chroma_instance = MagicMock()
        mock_chroma_instance.get_character.return_value = {
            "name": "Daisy Walker",
            "faction_name": "Seeker",
            "deck_options": "",
        }
        mock_chroma.return_value = mock_chroma_instance

        mock_action_agent = MagicMock()
        mock_action_response = MagicMock()
        mock_action_response.candidates = []
        for i in range(20):
            mock_candidate = MagicMock()
            mock_candidate.card_id = f"0102{i:01d}"
            mock_candidate.name = f"Seeker Card {i}"
            mock_candidate.xp_cost = 0
            mock_candidate.relevance_score = 0.8
            mock_candidate.reason = "Good card"
            mock_candidate.card_type = "Asset"
            mock_candidate.class_name = "Seeker"
            mock_candidate.cost = 2
            mock_candidate.traits = "Tome"
            mock_candidate.text = "Investigate action"
            mock_action_response.candidates.append(mock_candidate)
        mock_action_agent.search.return_value = mock_action_response

        mock_state_agent = MagicMock()
        mock_state_response = MagicMock()
        mock_state_response.identified_gaps = []
        mock_state_agent.query.return_value = mock_state_response

        def get_subagent(agent_type):
            if agent_type.value == "action_space":
                return mock_action_agent
            elif agent_type.value == "state":
                return mock_state_agent
            return MagicMock()

        mock_get_subagent.side_effect = get_subagent

        request = OrchestratorRequest(
            message="Build me a clue-focused deck for Daisy Walker with tome cards",
            investigator_id="01002",
            investigator_name="Daisy Walker",
        )

        response = mock_orchestrator.process(request)

        assert isinstance(response, NewDeckResponse)
        assert response.investigator_id == "01002"

    @patch("backend.services.chroma_client.ChromaClient")
    @patch.object(Orchestrator, "_get_subagent")
    def test_full_flow_agnes_mystic(
        self, mock_get_subagent, mock_chroma, mock_orchestrator
    ):
        """Should build a deck for Agnes Baker with secondary class."""
        self._setup_mock_llm(
            mock_orchestrator,
            '{"primary_focus": "combat", "secondary_focus": "support", "specific_requests": [], "avoid_cards": []}',
            '{"deck_name": "Agnes\\u0027s Fury", "reasoning": "A mystic combat deck using spells."}',
        )

        mock_chroma_instance = MagicMock()
        mock_chroma_instance.get_character.return_value = {
            "name": "Agnes Baker",
            "faction_name": "Mystic",
            "deck_options": "Survivor cards level 0-2",
        }
        mock_chroma.return_value = mock_chroma_instance

        mock_action_agent = MagicMock()
        mock_action_response = MagicMock()
        mock_action_response.candidates = []
        for i in range(20):
            mock_candidate = MagicMock()
            mock_candidate.card_id = f"0104{i:01d}"
            mock_candidate.name = f"Mystic Card {i}"
            mock_candidate.xp_cost = 0
            mock_candidate.relevance_score = 0.8
            mock_candidate.reason = "Spell"
            mock_candidate.card_type = "Asset"
            mock_candidate.class_name = "Mystic"
            mock_candidate.cost = 3
            mock_candidate.traits = "Spell"
            mock_candidate.text = "Fight using willpower"
            mock_action_response.candidates.append(mock_candidate)
        mock_action_agent.search.return_value = mock_action_response

        mock_state_agent = MagicMock()
        mock_state_response = MagicMock()
        mock_state_response.identified_gaps = []
        mock_state_agent.query.return_value = mock_state_response

        def get_subagent(agent_type):
            if agent_type.value == "action_space":
                return mock_action_agent
            elif agent_type.value == "state":
                return mock_state_agent
            return MagicMock()

        mock_get_subagent.side_effect = get_subagent

        request = OrchestratorRequest(
            message="Build me a mystic combat deck for Agnes Baker",
            investigator_id="01004",
            investigator_name="Agnes Baker",
        )

        response = mock_orchestrator.process(request)

        assert isinstance(response, NewDeckResponse)
        assert response.investigator_id == "01004"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestDeckBuilderEdgeCases:
    """Tests for edge cases in deck building."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked LLM."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.orchestrator.ChatOpenAI"):
                return Orchestrator()

    def test_empty_candidate_pool(self, orchestrator):
        """Should handle empty candidate pool gracefully."""
        request = OrchestratorRequest(message="Build deck", investigator_id="01001")
        goals = DeckBuildGoals(primary_focus="combat")
        constraints = InvestigatorConstraints(
            investigator_id="01001",
            investigator_name="Roland Banks",
            primary_class="Guardian",
            deck_size=30,
        )

        state = DeckBuilderState(
            request=request,
            goals=goals,
            constraints=constraints,
            candidate_cards=[],  # Empty pool
        )

        result = orchestrator._build_deck_node(state)

        assert result["selected_cards"] == []
        assert result["current_card_count"] == 0

    def test_no_constraints(self, orchestrator):
        """Should handle missing constraints."""
        request = OrchestratorRequest(message="Build deck", investigator_id="01001")

        state = DeckBuilderState(
            request=request,
            constraints=None,  # No constraints
        )

        result = orchestrator._build_deck_node(state)

        assert result["selected_cards"] == []
        assert result["current_card_count"] == 0

    @patch("backend.services.chroma_client.ChromaClient")
    def test_unknown_investigator(self, mock_chroma, orchestrator):
        """Should handle unknown investigator ID."""
        mock_chroma_instance = MagicMock()
        mock_chroma_instance.get_character.return_value = None
        mock_chroma.return_value = mock_chroma_instance

        request = OrchestratorRequest(
            message="Build deck",
            investigator_id="unknown_999",
        )

        state = DeckBuilderState(request=request)

        result = orchestrator._get_constraints_node(state)

        # Should still return constraints with defaults
        assert result["constraints"] is not None
        assert result["constraints"].investigator_id == "unknown_999"
        assert result["constraints"].primary_class == "Neutral"


# =============================================================================
# Subagent Result Tracking Tests
# =============================================================================


class TestSubagentResultTracking:
    """Tests for tracking subagent results in deck building."""

    def test_deck_builder_subagent_result(self):
        """Should create subagent result correctly."""
        result = DeckBuilderSubagentResult(
            agent_type="rules",
            query="Get constraints for Roland",
            success=True,
            summary="Primary: Guardian",
        )

        assert result.agent_type == "rules"
        assert result.success is True
        assert "Guardian" in result.summary

    def test_failed_subagent_result(self):
        """Should track failed subagent queries."""
        result = DeckBuilderSubagentResult(
            agent_type="scenario",
            query="Analyze The Gathering",
            success=False,
            summary="Scenario not found",
        )

        assert result.success is False
        assert "not found" in result.summary


# =============================================================================
# DeckSummary Model Tests
# =============================================================================


class TestDeckSummary:
    """Tests for DeckSummary model."""

    def test_minimal_summary(self):
        """Should create minimal summary with defaults."""
        summary = DeckSummary()
        assert summary.card_count == 0
        assert summary.curve == {}
        assert summary.type_distribution == {}
        assert summary.class_distribution == {}
        assert summary.key_cards == []

    def test_full_summary(self):
        """Should create summary with all fields."""
        summary = DeckSummary(
            card_count=30,
            curve={"0": 4, "1": 6, "2": 8, "3": 6, "4": 4, "5": 2},
            type_distribution={"Asset": 15, "Event": 10, "Skill": 5},
            class_distribution={"Guardian": 20, "Neutral": 10},
            key_cards=["Machete", ".45 Automatic", "Beat Cop"],
        )
        assert summary.card_count == 30
        assert summary.curve["2"] == 8
        assert summary.type_distribution["Asset"] == 15
        assert "Guardian" in summary.class_distribution
        assert len(summary.key_cards) == 3

    def test_to_readable(self):
        """Should format summary as readable text."""
        summary = DeckSummary(
            card_count=30,
            curve={"0": 4, "2": 10},
            type_distribution={"Asset": 15, "Event": 15},
            class_distribution={"Guardian": 25, "Neutral": 5},
            key_cards=["Machete", "Beat Cop"],
        )
        readable = summary.to_readable()

        assert "**Card Count**: 30" in readable
        assert "**Resource Curve**:" in readable
        assert "**Types**:" in readable
        assert "**Classes**:" in readable
        assert "**Key Cards**: Machete, Beat Cop" in readable


# =============================================================================
# Recommendation Model Tests
# =============================================================================


class TestRecommendation:
    """Tests for Recommendation model."""

    def test_add_recommendation(self):
        """Should create add recommendation."""
        rec = Recommendation(
            action="add",
            card_id="01016",
            card_name="Machete",
            xp_cost=0,
            priority=1,
            reason="Core combat weapon",
        )
        assert rec.action == "add"
        assert rec.card_id == "01016"
        assert rec.remove_card_id is None

    def test_swap_recommendation(self):
        """Should create swap recommendation with remove card."""
        rec = Recommendation(
            action="swap",
            card_id="01016",
            card_name="Machete",
            remove_card_id="01017",
            remove_card_name="Knife",
            xp_cost=0,
            priority=2,
            reason="Better damage output",
        )
        assert rec.action == "swap"
        assert rec.remove_card_id == "01017"
        assert rec.remove_card_name == "Knife"

    def test_upgrade_recommendation_with_xp(self):
        """Should create upgrade recommendation with XP cost."""
        rec = Recommendation(
            action="upgrade",
            card_id="01016",
            card_name="Machete (2)",
            remove_card_id="01015",
            remove_card_name="Machete",
            xp_cost=2,
            priority=1,
            reason="Higher level version",
        )
        assert rec.action == "upgrade"
        assert rec.xp_cost == 2

    def test_priority_bounds(self):
        """Should enforce priority between 1 and 10."""
        with pytest.raises(ValidationError):
            Recommendation(
                action="add",
                card_id="01016",
                card_name="Test",
                priority=0,
                reason="Test",
            )

        with pytest.raises(ValidationError):
            Recommendation(
                action="add",
                card_id="01016",
                card_name="Test",
                priority=11,
                reason="Test",
            )

    def test_to_readable_add(self):
        """Should format add recommendation."""
        rec = Recommendation(
            action="add",
            card_id="01016",
            card_name="Machete",
            priority=1,
            reason="Best combat weapon",
        )
        readable = rec.to_readable()
        assert "Add **Machete**" in readable
        assert "Best combat weapon" in readable

    def test_to_readable_swap(self):
        """Should format swap recommendation."""
        rec = Recommendation(
            action="swap",
            card_id="01016",
            card_name="Machete",
            remove_card_id="01017",
            remove_card_name="Knife",
            priority=1,
            reason="Better damage",
        )
        readable = rec.to_readable()
        assert "Swap **Knife** → **Machete**" in readable

    def test_to_readable_with_xp(self):
        """Should include XP cost in readable output."""
        rec = Recommendation(
            action="upgrade",
            card_id="01016",
            card_name="Machete (2)",
            remove_card_id="01015",
            remove_card_name="Machete",
            xp_cost=2,
            priority=1,
            reason="Upgrade",
        )
        readable = rec.to_readable()
        assert "(2 XP)" in readable


# =============================================================================
# DeckRecommendationResponse Model Tests
# =============================================================================


class TestDeckRecommendationResponse:
    """Tests for DeckRecommendationResponse model."""

    def test_new_deck_response(self):
        """Should create new deck recommendation response."""
        response = DeckRecommendationResponse(
            investigator_id="01001",
            request_type="new_deck",
            original_message="Build me a combat deck",
            proposed_deck_summary=DeckSummary(card_count=30),
            recommendations=[
                Recommendation(
                    action="add",
                    card_id="01016",
                    card_name="Machete",
                    priority=1,
                    reason="Core weapon",
                )
            ],
            reasoning="Combat-focused deck",
            subagents_consulted=["rules", "action_space"],
            confidence_score=0.85,
        )
        assert response.request_type == "new_deck"
        assert response.current_deck_summary is None
        assert len(response.recommendations) == 1
        assert response.confidence_score == 0.85

    def test_upgrade_response_with_current_deck(self):
        """Should create upgrade response with current deck summary."""
        response = DeckRecommendationResponse(
            investigator_id="01001",
            request_type="upgrade",
            original_message="Upgrade my deck with 5 XP",
            current_deck_summary=DeckSummary(card_count=30),
            proposed_deck_summary=DeckSummary(card_count=30),
            recommendations=[
                Recommendation(
                    action="upgrade",
                    card_id="01016",
                    card_name="Machete (2)",
                    remove_card_id="01015",
                    remove_card_name="Machete",
                    xp_cost=2,
                    priority=1,
                    reason="Better version",
                )
            ],
            reasoning="Prioritizing core upgrades",
        )
        assert response.request_type == "upgrade"
        assert response.current_deck_summary is not None
        assert response.recommendations[0].xp_cost == 2

    def test_error_response(self):
        """Should create error response."""
        response = DeckRecommendationResponse.error_response(
            error_message="Failed to analyze deck",
            investigator_id="01001",
            original_message="Help me upgrade",
        )
        assert response.confidence_score == 0.0
        assert "Failed to analyze deck" in response.reasoning
        assert "Failed to analyze deck" in response.warnings

    def test_to_readable(self):
        """Should format response as readable text."""
        response = DeckRecommendationResponse(
            investigator_id="01001",
            request_type="new_deck",
            original_message="Build deck",
            proposed_deck_summary=DeckSummary(
                card_count=30,
                key_cards=["Machete"],
            ),
            recommendations=[
                Recommendation(
                    action="add",
                    card_id="01016",
                    card_name="Machete",
                    priority=1,
                    reason="Core weapon",
                ),
                Recommendation(
                    action="add",
                    card_id="01017",
                    card_name="Beat Cop",
                    priority=2,
                    reason="Ally support",
                ),
            ],
            reasoning="Combat strategy",
            confidence_score=0.8,
        )
        readable = response.to_readable()

        assert "# Deck Recommendations" in readable
        assert "Combat strategy" in readable
        assert "## Recommendations" in readable
        assert "Machete" in readable
        assert "**Confidence**: 80%" in readable

    def test_to_readable_with_xp_total(self):
        """Should show total XP cost in readable output."""
        response = DeckRecommendationResponse(
            investigator_id="01001",
            request_type="upgrade",
            original_message="Upgrade deck",
            proposed_deck_summary=DeckSummary(card_count=30),
            recommendations=[
                Recommendation(
                    action="upgrade",
                    card_id="01016",
                    card_name="Card A",
                    xp_cost=3,
                    priority=1,
                    reason="Upgrade",
                ),
                Recommendation(
                    action="upgrade",
                    card_id="01017",
                    card_name="Card B",
                    xp_cost=2,
                    priority=2,
                    reason="Upgrade",
                ),
            ],
            reasoning="XP spending plan",
        )
        readable = response.to_readable()
        assert "**Total XP Cost**: 5" in readable


# =============================================================================
# NewDeckResponse.to_readable Tests
# =============================================================================


class TestNewDeckResponseReadable:
    """Tests for NewDeckResponse.to_readable() method."""

    def test_to_readable_basic(self):
        """Should format deck as readable text."""
        response = NewDeckResponse(
            deck_name="Roland's Assault Force",
            investigator_id="01001",
            investigator_name="Roland Banks",
            cards=[
                CardSelection(
                    card_id="01016",
                    name="Machete",
                    quantity=2,
                    reason="Primary weapon",
                    category="combat",
                ),
                CardSelection(
                    card_id="01030",
                    name="Dr. Milan Christopher",
                    quantity=1,
                    reason="Resource generation",
                    category="economy",
                ),
            ],
            total_cards=30,
            reasoning="Combat-focused build",
            archetype="Combat Guardian",
        )
        readable = response.to_readable()

        assert "# Roland's Assault Force" in readable
        assert "**Investigator**: Roland Banks" in readable
        assert "**Archetype**: Combat Guardian" in readable
        assert "## Strategy" in readable
        assert "Combat-focused build" in readable
        assert "### Combat" in readable
        assert "Machete x2" in readable
        assert "### Economy" in readable

    def test_to_readable_with_warnings(self):
        """Should include warnings in output."""
        response = NewDeckResponse(
            deck_name="Test Deck",
            investigator_id="01001",
            investigator_name="Roland Banks",
            warnings=["Deck is incomplete", "Missing card draw"],
            archetype="Test",
        )
        readable = response.to_readable()

        assert "## Warnings" in readable
        assert "Deck is incomplete" in readable
        assert "Missing card draw" in readable
