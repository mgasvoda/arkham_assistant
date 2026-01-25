"""Integration tests for agent tools with ChromaDB.

These tests verify that agent tools correctly communicate with the actual
ChromaDB client. They use a temporary database to avoid affecting production data.
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path

from backend.services.chroma_client import ChromaClient
from backend.services import agent_tools
from backend.services.agent_tools import (
    CardNotFoundError,
    DeckNotFoundError,
    get_card_details,
    get_deck,
    get_static_info,
    summarize_deck,
)


@pytest.fixture
def temp_chroma_db(tmp_path):
    """Create a temporary ChromaDB instance for testing."""
    # Create a fresh ChromaClient with temp path
    client = ChromaClient(persist_path=str(tmp_path / "chroma_test"))

    # Inject the client into agent_tools module
    original_client = agent_tools._chroma_client
    original_loader = agent_tools._card_loader
    agent_tools._chroma_client = client
    agent_tools._card_loader = None  # Reset so it uses new client

    yield client

    # Restore original client and loader
    agent_tools._chroma_client = original_client
    agent_tools._card_loader = original_loader


@pytest.fixture
def populated_db(temp_chroma_db):
    """Populate the temporary database with test data."""
    client = temp_chroma_db

    # Add test cards
    test_cards = [
        {
            "id": "01016",
            "name": ".45 Automatic",
            "class_name": "Guardian",
            "cost": 4,
            "type_name": "Asset",
            "subtype": "Weapon",
            "text": "Uses (4 ammo). Spend 1 ammo: Fight.",
            "traits": json.dumps(["Item", "Weapon", "Firearm"]),
            "icons": json.dumps({"combat": 1}),
            "owned": True,
        },
        {
            "id": "01017",
            "name": "Beat Cop",
            "class_name": "Guardian",
            "cost": 2,
            "type_name": "Asset",
            "subtype": "Ally",
            "text": "You get +1 Combat. Exhaust Beat Cop: Deal 1 damage.",
            "traits": json.dumps(["Ally", "Police"]),
            "icons": json.dumps({"combat": 1}),
            "owned": True,
        },
        {
            "id": "01022",
            "name": "Working a Hunch",
            "class_name": "Seeker",
            "cost": 2,
            "type_name": "Event",
            "subtype": None,
            "text": "Discover 1 clue at your location.",
            "traits": json.dumps(["Insight"]),
            "icons": json.dumps({"intellect": 2}),
            "owned": True,
        },
        {
            "id": "01088",
            "name": "Unexpected Courage",
            "class_name": "Neutral",
            "cost": 0,
            "type_name": "Skill",
            "subtype": None,
            "text": "Commit to a skill test.",
            "traits": json.dumps(["Innate"]),
            "icons": json.dumps({"wild": 2}),
            "owned": True,
        },
    ]

    for card in test_cards:
        client.add_card(card.copy())

    # Add test deck
    test_deck = {
        "name": "Integration Test Deck",
        "investigator_code": "01001",
        "investigator_name": "Roland Banks",
        "cards": json.dumps([
            {"id": "01016", "count": 2},
            {"id": "01017", "count": 2},
            {"id": "01022", "count": 2},
            {"id": "01088", "count": 2},
        ]),
        "archetype": "combat",
        "notes": "Test deck for integration tests",
    }
    deck_id = client.create_deck(test_deck)

    return {"client": client, "deck_id": deck_id, "cards": test_cards}


# ============================================================================
# Integration: get_card_details → ChromaDB
# ============================================================================


class TestGetCardDetailsIntegration:
    """Integration tests for get_card_details with real ChromaDB."""

    def test_retrieves_single_card(self, populated_db):
        """Should retrieve card from ChromaDB by ID."""
        result = get_card_details(["01016"])

        assert len(result) == 1
        assert result[0]["name"] == ".45 Automatic"
        assert result[0]["class_name"] == "Guardian"
        assert result[0]["cost"] == 4

    def test_retrieves_multiple_cards(self, populated_db):
        """Should retrieve multiple cards from ChromaDB."""
        result = get_card_details(["01016", "01017", "01022"])

        assert len(result) == 3
        names = [card["name"] for card in result]
        assert ".45 Automatic" in names
        assert "Beat Cop" in names
        assert "Working a Hunch" in names

    def test_parses_json_fields(self, populated_db):
        """Should parse JSON fields from ChromaDB data."""
        result = get_card_details(["01016"])

        # Traits should be parsed from JSON string to list
        assert isinstance(result[0]["traits"], list)
        assert "Weapon" in result[0]["traits"]

        # Icons should be parsed from JSON string to dict
        assert isinstance(result[0]["icons"], dict)
        assert result[0]["icons"]["combat"] == 1

    def test_raises_for_nonexistent_card(self, populated_db):
        """Should raise CardNotFoundError for missing card."""
        with pytest.raises(CardNotFoundError) as exc_info:
            get_card_details(["99999"])

        assert "99999" in str(exc_info.value)


# ============================================================================
# Integration: get_deck → ChromaDB
# ============================================================================


class TestGetDeckIntegration:
    """Integration tests for get_deck with real ChromaDB."""

    def test_retrieves_deck(self, populated_db):
        """Should retrieve deck from ChromaDB."""
        deck_id = populated_db["deck_id"]

        result = get_deck(deck_id)

        assert result["name"] == "Integration Test Deck"
        assert result["investigator_name"] == "Roland Banks"
        assert result["archetype"] == "combat"

    def test_parses_cards_list(self, populated_db):
        """Should parse cards JSON field."""
        deck_id = populated_db["deck_id"]

        result = get_deck(deck_id)

        assert isinstance(result["cards"], list)
        assert len(result["cards"]) == 4
        assert result["cards"][0]["id"] == "01016"
        assert result["cards"][0]["count"] == 2

    def test_raises_for_nonexistent_deck(self, populated_db):
        """Should raise DeckNotFoundError for missing deck."""
        with pytest.raises(DeckNotFoundError):
            get_deck("nonexistent_deck_id")


# ============================================================================
# Integration: summarize_deck → ChromaDB
# ============================================================================


class TestSummarizeDeckIntegration:
    """Integration tests for summarize_deck with real ChromaDB."""

    def test_calculates_summary(self, populated_db):
        """Should calculate deck summary from ChromaDB data."""
        deck_id = populated_db["deck_id"]

        result = summarize_deck(deck_id)

        assert result["deck_name"] == "Integration Test Deck"
        assert result["investigator"] == "Roland Banks"
        assert result["total_cards"] == 8  # 4 cards × 2 copies each
        assert result["archetype"] == "combat"

    def test_calculates_curve(self, populated_db):
        """Should calculate resource curve from card costs."""
        deck_id = populated_db["deck_id"]

        result = summarize_deck(deck_id)

        # .45 Auto (cost 4) × 2 + Beat Cop (cost 2) × 2 + Working a Hunch (cost 2) × 2 + Unexpected Courage (cost 0) × 2
        assert "0" in result["curve"]  # Unexpected Courage
        assert "2" in result["curve"]  # Beat Cop + Working a Hunch
        assert "4" in result["curve"]  # .45 Automatic
        assert result["curve"]["0"] == 2
        assert result["curve"]["2"] == 4  # 2 Beat Cop + 2 Working a Hunch
        assert result["curve"]["4"] == 2

    def test_calculates_class_distribution(self, populated_db):
        """Should calculate class distribution from cards."""
        deck_id = populated_db["deck_id"]

        result = summarize_deck(deck_id)

        assert "Guardian" in result["class_distribution"]
        assert "Seeker" in result["class_distribution"]
        assert "Neutral" in result["class_distribution"]
        assert result["class_distribution"]["Guardian"] == 4  # .45 Auto + Beat Cop
        assert result["class_distribution"]["Seeker"] == 2   # Working a Hunch
        assert result["class_distribution"]["Neutral"] == 2  # Unexpected Courage

    def test_calculates_type_breakdown(self, populated_db):
        """Should calculate card type breakdown."""
        deck_id = populated_db["deck_id"]

        result = summarize_deck(deck_id)

        assert "Asset" in result["type_breakdown"]
        assert "Event" in result["type_breakdown"]
        assert "Skill" in result["type_breakdown"]
        assert result["type_breakdown"]["Asset"] == 4   # .45 Auto + Beat Cop
        assert result["type_breakdown"]["Event"] == 2   # Working a Hunch
        assert result["type_breakdown"]["Skill"] == 2   # Unexpected Courage


# ============================================================================
# Integration: get_static_info → filesystem
# ============================================================================


class TestGetStaticInfoIntegration:
    """Integration tests for get_static_info with real filesystem."""

    def test_reads_rules_file(self):
        """Should read actual rules_overview.md file."""
        result = get_static_info("rules")

        assert "Arkham Horror LCG" in result
        assert "Action Economy" in result
        assert "Deck Construction" in result

    def test_reads_meta_file(self):
        """Should read actual meta_trends.md file."""
        result = get_static_info("meta")

        # File contains strategic doctrine for deckbuilding
        assert "Strategic Doctrine" in result or "Deckbuilding" in result
        assert "Guardian" in result
        assert "Seeker" in result

    def test_reads_owned_sets_file(self):
        """Should read actual owned_sets.md file."""
        result = get_static_info("owned_sets")

        assert "Owned Card Sets" in result
        assert "Core Set" in result


# ============================================================================
# Integration: Full workflow test
# ============================================================================


class TestFullWorkflow:
    """Test complete workflow from deck retrieval to summary."""

    def test_deck_to_summary_workflow(self, populated_db):
        """Should support complete deck analysis workflow."""
        deck_id = populated_db["deck_id"]

        # Step 1: Get deck
        deck = get_deck(deck_id)
        assert deck["name"] == "Integration Test Deck"

        # Step 2: Get all cards in deck
        card_ids = [c["id"] for c in deck["cards"]]
        cards = get_card_details(card_ids)
        assert len(cards) == 4

        # Step 3: Get summary
        summary = summarize_deck(deck_id)
        assert summary["total_cards"] == 8

        # Step 4: Get static info for context
        rules = get_static_info("rules")
        assert "Deck Construction" in rules
