"""Unit tests for agent tools."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.services.agent_tools import (
    CardNotFoundError,
    DeckNotFoundError,
    StaticFileNotFoundError,
    get_card_details,
    get_deck,
    get_static_info,
    run_simulation_tool,
    recommend_cards,
    summarize_deck,
    _get_client,
    # LangGraph tools
    card_lookup_tool,
    deck_lookup_tool,
    static_info_tool,
    deck_summary_tool,
    simulation_tool,
    recommendation_tool,
    AGENT_TOOLS,
    IMPLEMENTED_TOOLS,
    STUB_TOOLS,
    # Pydantic schemas
    CardLookupInput,
    DeckLookupInput,
    StaticInfoInput,
    DeckSummaryInput,
    SimulationInput,
    RecommendationInput,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_chroma_client():
    """Create a mock ChromaDB client."""
    # Reset both module-level singletons to ensure fresh mock injection
    with patch("backend.services.agent_tools._chroma_client", None):
        with patch("backend.services.agent_tools._card_loader", None):
            with patch("backend.services.agent_tools.ChromaClient") as MockClient:
                mock_client = MagicMock()
                MockClient.return_value = mock_client
                yield mock_client


@pytest.fixture
def sample_card_data():
    """Sample card data as returned by ChromaDB."""
    return {
        "code": "01001",
        "name": "Roland Banks",
        "class_name": "Guardian",
        "cost": 0,
        "type_name": "Investigator",
        "text": "Elder Sign effect: +1 for each clue on your location.",
        "traits": '["Detective", "Agency"]',
        "icons": '{"willpower": 3, "intellect": 3, "combat": 4, "agility": 2}',
        "owned": True,
    }


@pytest.fixture
def sample_deck_data():
    """Sample deck data as returned by ChromaDB."""
    return {
        "id": "deck_abc123",
        "name": "Roland's Starter",
        "investigator_code": "01001",
        "investigator_name": "Roland Banks",
        "cards": '[{"id": "01016", "count": 2}, {"id": "01017", "count": 2}]',
        "archetype": "combat",
        "notes": "A basic Guardian deck",
    }


# ============================================================================
# get_card_details tests
# ============================================================================


class TestGetCardDetails:
    """Tests for get_card_details function."""

    def test_returns_empty_list_for_empty_input(self, mock_chroma_client):
        """Should return empty list when no card IDs provided."""
        result = get_card_details([])
        assert result == []
        mock_chroma_client.get_card.assert_not_called()

    def test_returns_single_card(self, mock_chroma_client, sample_card_data):
        """Should return card data for a single valid ID."""
        mock_chroma_client.get_card.return_value = sample_card_data.copy()

        result = get_card_details(["01001"])

        assert len(result) == 1
        assert result[0]["name"] == "Roland Banks"
        mock_chroma_client.get_card.assert_called_once_with("01001")

    def test_returns_multiple_cards(self, mock_chroma_client, sample_card_data):
        """Should return multiple cards for multiple IDs."""
        card1 = sample_card_data.copy()
        card2 = sample_card_data.copy()
        card2["code"] = "01002"
        card2["name"] = "Daisy Walker"

        mock_chroma_client.get_card.side_effect = [card1, card2]

        result = get_card_details(["01001", "01002"])

        assert len(result) == 2
        assert result[0]["name"] == "Roland Banks"
        assert result[1]["name"] == "Daisy Walker"

    def test_parses_json_fields(self, mock_chroma_client, sample_card_data):
        """Should parse JSON string fields into Python objects."""
        mock_chroma_client.get_card.return_value = sample_card_data.copy()

        result = get_card_details(["01001"])

        assert result[0]["traits"] == ["Detective", "Agency"]
        assert result[0]["icons"]["combat"] == 4

    def test_handles_invalid_json_fields(self, mock_chroma_client, sample_card_data):
        """Should keep field as string if JSON parsing fails."""
        card = sample_card_data.copy()
        card["traits"] = "invalid json"
        mock_chroma_client.get_card.return_value = card

        result = get_card_details(["01001"])

        assert result[0]["traits"] == "invalid json"

    def test_raises_error_for_missing_card(self, mock_chroma_client):
        """Should raise CardNotFoundError when card doesn't exist."""
        mock_chroma_client.get_card.return_value = None

        with pytest.raises(CardNotFoundError) as exc_info:
            get_card_details(["nonexistent"])

        assert "nonexistent" in str(exc_info.value)

    def test_raises_error_with_all_missing_ids(self, mock_chroma_client):
        """Should include all missing IDs in error message."""
        mock_chroma_client.get_card.return_value = None

        with pytest.raises(CardNotFoundError) as exc_info:
            get_card_details(["bad1", "bad2"])

        assert "bad1" in str(exc_info.value)
        assert "bad2" in str(exc_info.value)


# ============================================================================
# get_deck tests
# ============================================================================


class TestGetDeck:
    """Tests for get_deck function."""

    def test_raises_error_for_empty_id(self, mock_chroma_client):
        """Should raise error when deck ID is empty."""
        with pytest.raises(DeckNotFoundError) as exc_info:
            get_deck("")

        assert "empty" in str(exc_info.value).lower()

    def test_returns_deck_data(self, mock_chroma_client, sample_deck_data):
        """Should return deck with full metadata."""
        mock_chroma_client.get_deck.return_value = sample_deck_data.copy()

        result = get_deck("deck_abc123")

        assert result["name"] == "Roland's Starter"
        assert result["investigator_name"] == "Roland Banks"
        mock_chroma_client.get_deck.assert_called_once_with("deck_abc123")

    def test_parses_cards_json(self, mock_chroma_client, sample_deck_data):
        """Should parse cards JSON field."""
        mock_chroma_client.get_deck.return_value = sample_deck_data.copy()

        result = get_deck("deck_abc123")

        assert isinstance(result["cards"], list)
        assert len(result["cards"]) == 2
        assert result["cards"][0]["id"] == "01016"

    def test_raises_error_for_missing_deck(self, mock_chroma_client):
        """Should raise DeckNotFoundError when deck doesn't exist."""
        mock_chroma_client.get_deck.return_value = None

        with pytest.raises(DeckNotFoundError) as exc_info:
            get_deck("nonexistent")

        assert "nonexistent" in str(exc_info.value)


# ============================================================================
# get_static_info tests
# ============================================================================


class TestGetStaticInfo:
    """Tests for get_static_info function."""

    def test_returns_rules_content(self):
        """Should return content of rules_overview.md."""
        result = get_static_info("rules")

        assert "Arkham Horror" in result
        assert "Action Economy" in result

    def test_returns_meta_content(self):
        """Should return content of meta_trends.md."""
        result = get_static_info("meta")

        # File contains strategic doctrine for deckbuilding
        assert "Strategic Doctrine" in result or "Deckbuilding" in result
        assert "Guardian" in result  # Class doctrine sections

    def test_returns_owned_sets_content(self):
        """Should return content of owned_sets.md."""
        result = get_static_info("owned_sets")

        assert "Owned Card Sets" in result
        assert "Core Set" in result

    def test_accepts_owned_alias(self):
        """Should accept 'owned' as alias for 'owned_sets'."""
        result = get_static_info("owned")

        assert "Owned Card Sets" in result

    def test_case_insensitive(self):
        """Should handle topic names case-insensitively."""
        result = get_static_info("RULES")

        assert "Arkham Horror" in result

    def test_handles_investigator_topic(self):
        """Should handle investigator subtopic by returning meta trends."""
        result = get_static_info("investigator:roland")

        # Currently returns meta_trends.md for investigator topics
        # File contains strategic doctrine including class information
        assert "Guardian" in result or "Seeker" in result

    def test_raises_error_for_unknown_topic(self):
        """Should raise error for unknown topic."""
        with pytest.raises(StaticFileNotFoundError) as exc_info:
            get_static_info("unknown_topic")

        assert "unknown_topic" in str(exc_info.value)
        assert "Available topics" in str(exc_info.value)


# ============================================================================
# run_simulation_tool tests
# ============================================================================


class TestRunSimulationTool:
    """Tests for run_simulation_tool function (stub)."""

    def test_returns_stub_response(self):
        """Should return stub response indicating not implemented."""
        result = run_simulation_tool("deck_123", n_trials=500)

        assert result["error"] == "Simulation not yet implemented"
        assert result["deck_id"] == "deck_123"
        assert result["n_trials"] == 500


# ============================================================================
# recommend_cards tests
# ============================================================================


class TestRecommendCards:
    """Tests for recommend_cards function (stub)."""

    def test_returns_empty_list_stub(self):
        """Should return empty list as stub implementation."""
        result = recommend_cards("deck_123", goal="combat")

        assert result == []


# ============================================================================
# summarize_deck tests
# ============================================================================


class TestSummarizeDeck:
    """Tests for summarize_deck function."""

    def test_returns_basic_summary(self, mock_chroma_client, sample_deck_data):
        """Should return deck summary with basic info."""
        mock_chroma_client.get_deck.return_value = sample_deck_data.copy()
        mock_chroma_client.get_card.return_value = None  # Cards not found

        result = summarize_deck("deck_abc123")

        assert result["deck_name"] == "Roland's Starter"
        assert result["investigator"] == "Roland Banks"
        assert result["archetype"] == "combat"

    def test_calculates_card_counts(self, mock_chroma_client, sample_deck_data):
        """Should calculate total cards and distributions."""
        deck = sample_deck_data.copy()
        mock_chroma_client.get_deck.return_value = deck

        # Mock card data for the cards in the deck
        card1 = {
            "code": "01016",
            "name": ".45 Automatic",
            "class_name": "Guardian",
            "cost": 4,
            "type_name": "Asset",
        }
        card2 = {
            "code": "01017",
            "name": "Beat Cop",
            "class_name": "Guardian",
            "cost": 2,
            "type_name": "Asset",
        }

        mock_chroma_client.get_card.side_effect = [card1, card2]

        result = summarize_deck("deck_abc123")

        assert result["total_cards"] == 4  # 2 copies of each
        assert result["class_distribution"]["Guardian"] == 4
        assert result["type_breakdown"]["Asset"] == 4
        assert "4" in result["curve"]  # Cost 4 cards
        assert "2" in result["curve"]  # Cost 2 cards

    def test_handles_list_of_card_ids(self, mock_chroma_client):
        """Should handle deck with simple list of card IDs."""
        deck = {
            "id": "deck_123",
            "name": "Test Deck",
            "cards": '["01001", "01001", "01002"]',
        }
        mock_chroma_client.get_deck.return_value = deck

        card1 = {"code": "01001", "name": "Card One", "class_name": "Seeker", "cost": 1, "type_name": "Event"}
        card2 = {"code": "01002", "name": "Card Two", "class_name": "Mystic", "cost": 2, "type_name": "Skill"}

        mock_chroma_client.get_card.side_effect = [card1, card2]

        result = summarize_deck("deck_123")

        assert result["total_cards"] == 3
        assert result["class_distribution"]["Seeker"] == 2
        assert result["class_distribution"]["Mystic"] == 1

    def test_handles_empty_deck(self, mock_chroma_client):
        """Should handle deck with no cards."""
        deck = {
            "id": "deck_123",
            "name": "Empty Deck",
            "cards": "[]",
        }
        mock_chroma_client.get_deck.return_value = deck

        result = summarize_deck("deck_123")

        assert result["total_cards"] == 0
        assert result["curve"] == {}
        assert result["class_distribution"] == {}

    def test_raises_error_for_missing_deck(self, mock_chroma_client):
        """Should raise error when deck doesn't exist."""
        mock_chroma_client.get_deck.return_value = None

        with pytest.raises(DeckNotFoundError):
            summarize_deck("nonexistent")


# ============================================================================
# Pydantic Input Schema tests
# ============================================================================


class TestPydanticSchemas:
    """Tests for Pydantic input schemas."""

    def test_card_lookup_input_valid(self):
        """Should accept valid card IDs list."""
        schema = CardLookupInput(card_ids=["01001", "01002"])
        assert schema.card_ids == ["01001", "01002"]

    def test_card_lookup_input_empty_list(self):
        """Should accept empty list."""
        schema = CardLookupInput(card_ids=[])
        assert schema.card_ids == []

    def test_deck_lookup_input_valid(self):
        """Should accept valid deck ID."""
        schema = DeckLookupInput(deck_id="deck_abc123")
        assert schema.deck_id == "deck_abc123"

    def test_static_info_input_valid_topics(self):
        """Should accept all valid topic values."""
        for topic in ["rules", "meta", "owned_sets", "owned"]:
            schema = StaticInfoInput(topic=topic)
            assert schema.topic == topic

    def test_static_info_input_invalid_topic(self):
        """Should reject invalid topic values."""
        with pytest.raises(ValueError):
            StaticInfoInput(topic="invalid_topic")

    def test_simulation_input_defaults(self):
        """Should use default n_trials value."""
        schema = SimulationInput(deck_id="deck_123")
        assert schema.n_trials == 1000

    def test_simulation_input_custom_trials(self):
        """Should accept custom n_trials value."""
        schema = SimulationInput(deck_id="deck_123", n_trials=500)
        assert schema.n_trials == 500

    def test_simulation_input_trial_bounds(self):
        """Should enforce n_trials bounds."""
        with pytest.raises(ValueError):
            SimulationInput(deck_id="deck_123", n_trials=0)
        with pytest.raises(ValueError):
            SimulationInput(deck_id="deck_123", n_trials=20000)

    def test_recommendation_input_defaults(self):
        """Should use default goal value."""
        schema = RecommendationInput(deck_id="deck_123")
        assert schema.goal == "balance"

    def test_recommendation_input_valid_goals(self):
        """Should accept all valid goal values."""
        for goal in ["balance", "card_draw", "economy", "combat", "clues"]:
            schema = RecommendationInput(deck_id="deck_123", goal=goal)
            assert schema.goal == goal

    def test_recommendation_input_invalid_goal(self):
        """Should reject invalid goal values."""
        with pytest.raises(ValueError):
            RecommendationInput(deck_id="deck_123", goal="invalid_goal")


# ============================================================================
# LangGraph Tool Wrapper tests
# ============================================================================


class TestCardLookupTool:
    """Tests for card_lookup_tool LangGraph wrapper."""

    def test_returns_json_string(self, mock_chroma_client, sample_card_data):
        """Should return JSON-formatted string."""
        mock_chroma_client.get_card.return_value = sample_card_data.copy()

        result = card_lookup_tool.invoke({"card_ids": ["01001"]})

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_returns_error_json_for_missing_card(self, mock_chroma_client):
        """Should return error JSON when card not found."""
        mock_chroma_client.get_card.return_value = None

        result = card_lookup_tool.invoke({"card_ids": ["nonexistent"]})

        parsed = json.loads(result)
        assert "error" in parsed

    def test_tool_has_correct_name(self):
        """Should have correct tool name."""
        assert card_lookup_tool.name == "card_lookup"

    def test_tool_has_description(self):
        """Should have a description for LLM."""
        assert card_lookup_tool.description
        assert "card" in card_lookup_tool.description.lower()


class TestDeckLookupTool:
    """Tests for deck_lookup_tool LangGraph wrapper."""

    def test_returns_json_string(self, mock_chroma_client, sample_deck_data):
        """Should return JSON-formatted string."""
        mock_chroma_client.get_deck.return_value = sample_deck_data.copy()

        result = deck_lookup_tool.invoke({"deck_id": "deck_abc123"})

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["name"] == "Roland's Starter"

    def test_returns_error_json_for_missing_deck(self, mock_chroma_client):
        """Should return error JSON when deck not found."""
        mock_chroma_client.get_deck.return_value = None

        result = deck_lookup_tool.invoke({"deck_id": "nonexistent"})

        parsed = json.loads(result)
        assert "error" in parsed

    def test_tool_has_correct_name(self):
        """Should have correct tool name."""
        assert deck_lookup_tool.name == "deck_lookup"


class TestStaticInfoTool:
    """Tests for static_info_tool LangGraph wrapper."""

    def test_returns_markdown_content(self):
        """Should return markdown file content."""
        result = static_info_tool.invoke({"topic": "rules"})

        assert isinstance(result, str)
        assert "Arkham Horror" in result

    def test_tool_has_correct_name(self):
        """Should have correct tool name."""
        assert static_info_tool.name == "static_info"


class TestDeckSummaryTool:
    """Tests for deck_summary_tool LangGraph wrapper."""

    def test_returns_json_string(self, mock_chroma_client, sample_deck_data):
        """Should return JSON-formatted summary."""
        mock_chroma_client.get_deck.return_value = sample_deck_data.copy()
        mock_chroma_client.get_card.return_value = None

        result = deck_summary_tool.invoke({"deck_id": "deck_abc123"})

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "deck_name" in parsed
        assert "curve" in parsed

    def test_tool_has_correct_name(self):
        """Should have correct tool name."""
        assert deck_summary_tool.name == "deck_summary"


class TestSimulationTool:
    """Tests for simulation_tool LangGraph wrapper (stub)."""

    def test_returns_stub_json(self):
        """Should return stub response as JSON."""
        result = simulation_tool.invoke({"deck_id": "deck_123", "n_trials": 100})

        parsed = json.loads(result)
        assert parsed["error"] == "Simulation not yet implemented"

    def test_tool_has_correct_name(self):
        """Should have correct tool name."""
        assert simulation_tool.name == "run_simulation"


class TestRecommendationTool:
    """Tests for recommendation_tool LangGraph wrapper (stub)."""

    def test_returns_empty_list_json(self):
        """Should return empty list as JSON."""
        result = recommendation_tool.invoke({"deck_id": "deck_123", "goal": "combat"})

        parsed = json.loads(result)
        assert parsed == []

    def test_tool_has_correct_name(self):
        """Should have correct tool name."""
        assert recommendation_tool.name == "recommend_cards"


# ============================================================================
# Tool Registry tests
# ============================================================================


class TestToolRegistry:
    """Tests for tool registry exports."""

    def test_agent_tools_contains_all_tools(self):
        """Should contain all 6 tools."""
        assert len(AGENT_TOOLS) == 6
        tool_names = [t.name for t in AGENT_TOOLS]
        assert "card_lookup" in tool_names
        assert "deck_lookup" in tool_names
        assert "static_info" in tool_names
        assert "deck_summary" in tool_names
        assert "run_simulation" in tool_names
        assert "recommend_cards" in tool_names

    def test_implemented_tools_list(self):
        """Should contain 4 implemented tools."""
        assert len(IMPLEMENTED_TOOLS) == 4
        tool_names = [t.name for t in IMPLEMENTED_TOOLS]
        assert "card_lookup" in tool_names
        assert "deck_lookup" in tool_names
        assert "static_info" in tool_names
        assert "deck_summary" in tool_names

    def test_stub_tools_list(self):
        """Should contain 2 stub tools."""
        assert len(STUB_TOOLS) == 2
        tool_names = [t.name for t in STUB_TOOLS]
        assert "run_simulation" in tool_names
        assert "recommend_cards" in tool_names

    def test_all_tools_are_langchain_tools(self):
        """All tools should be valid LangChain tools."""
        from langchain_core.tools import BaseTool

        for tool in AGENT_TOOLS:
            assert isinstance(tool, BaseTool)
