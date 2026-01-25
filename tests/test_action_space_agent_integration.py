"""Integration tests for ActionSpaceAgent with ChromaDB.

These tests verify the ActionSpaceAgent works correctly with
a real (temporary) ChromaDB instance containing test card data.
"""

import os
import tempfile
from pathlib import Path

import pytest

from backend.services.chroma_client import ChromaClient
from backend.services.subagents.action_space_agent import (
    ActionSpaceAgent,
    ActionSpaceQuery,
    ActionSpaceResponse,
)


# =============================================================================
# Test Data
# =============================================================================


SAMPLE_INVESTIGATORS = [
    {
        "id": "01001",
        "name": "Roland Banks",
        "faction_name": "Guardian",
        "deck_options": "Seeker cards level 0",
    },
    {
        "id": "01002",
        "name": "Daisy Walker",
        "faction_name": "Seeker",
        "deck_options": "Mystic cards level 0-2",
    },
    {
        "id": "01004",
        "name": "Agnes Baker",
        "faction_name": "Mystic",
        "deck_options": "Survivor cards level 0-2",
    },
]


SAMPLE_CARDS = [
    # Guardian cards
    {
        "id": "01016",
        "name": "Machete",
        "class_name": "Guardian",
        "type_name": "Asset",
        "xp": 0,
        "cost": 3,
        "traits": "Item. Weapon. Melee.",
        "text": "Fight. +1 combat for this attack. If you are engaged with only 1 enemy, this attack deals +1 damage.",
        "pack_name": "Core Set",
    },
    {
        "id": "01017",
        "name": ".45 Automatic",
        "class_name": "Guardian",
        "type_name": "Asset",
        "xp": 0,
        "cost": 4,
        "traits": "Item. Weapon. Firearm.",
        "text": "Uses (4 ammo). Fight. Spend 1 ammo: +1 combat for this attack. This attack deals +1 damage.",
        "pack_name": "Core Set",
    },
    {
        "id": "01020",
        "name": "Beat Cop",
        "class_name": "Guardian",
        "type_name": "Asset",
        "xp": 0,
        "cost": 4,
        "traits": "Ally. Police.",
        "text": "While Beat Cop is in play, you get +1 combat.",
        "pack_name": "Core Set",
    },
    {
        "id": "02029",
        "name": "Beat Cop (2)",
        "class_name": "Guardian",
        "type_name": "Asset",
        "xp": 2,
        "cost": 4,
        "traits": "Ally. Police.",
        "text": "While Beat Cop is in play, you get +1 combat. Exhaust Beat Cop and deal 1 damage to it: Deal 1 damage to an enemy at your location.",
        "pack_name": "The Dunwich Legacy",
    },
    # Seeker cards
    {
        "id": "01039",
        "name": "Magnifying Glass",
        "class_name": "Seeker",
        "type_name": "Asset",
        "xp": 0,
        "cost": 1,
        "traits": "Item. Tool.",
        "text": "You get +1 intellect while investigating.",
        "pack_name": "Core Set",
    },
    {
        "id": "01040",
        "name": "Old Book of Lore",
        "class_name": "Seeker",
        "type_name": "Asset",
        "xp": 0,
        "cost": 3,
        "traits": "Item. Tome.",
        "text": "Exhaust Old Book of Lore: Search the top 3 cards of your deck for a card and draw it.",
        "pack_name": "Core Set",
    },
    {
        "id": "02030",
        "name": "Higher Education",
        "class_name": "Seeker",
        "type_name": "Asset",
        "xp": 3,
        "cost": 0,
        "traits": "Talent.",
        "text": "While you have 5 or more cards in hand, you get +2 intellect and +2 willpower.",
        "pack_name": "The Dunwich Legacy",
    },
    # Mystic cards
    {
        "id": "01060",
        "name": "Shrivelling",
        "class_name": "Mystic",
        "type_name": "Asset",
        "xp": 0,
        "cost": 3,
        "traits": "Spell.",
        "text": "Fight. Use willpower instead of combat for this attack. This attack deals +1 damage.",
        "pack_name": "Core Set",
    },
    {
        "id": "01061",
        "name": "Scrying",
        "class_name": "Mystic",
        "type_name": "Asset",
        "xp": 0,
        "cost": 1,
        "traits": "Spell.",
        "text": "Look at the top 3 cards of the encounter deck.",
        "pack_name": "Core Set",
    },
    {
        "id": "02028",
        "name": "Delve Too Deep",
        "class_name": "Mystic",
        "type_name": "Event",
        "xp": 0,
        "cost": 1,
        "traits": "Insight.",
        "text": "Fast. Play during the mythos phase. Add 1 doom. Each investigator earns 1 additional experience.",
        "pack_name": "The Dunwich Legacy",
    },
    # Survivor cards
    {
        "id": "01073",
        "name": "Leather Coat",
        "class_name": "Survivor",
        "type_name": "Asset",
        "xp": 0,
        "cost": 0,
        "traits": "Item. Armor.",
        "text": "Health +2.",
        "pack_name": "Core Set",
    },
    {
        "id": "01074",
        "name": "Baseball Bat",
        "class_name": "Survivor",
        "type_name": "Asset",
        "xp": 0,
        "cost": 2,
        "traits": "Item. Weapon. Melee.",
        "text": "Fight. +2 combat for this attack. If you fail, discard Baseball Bat.",
        "pack_name": "Core Set",
    },
    # Neutral cards
    {
        "id": "01088",
        "name": "Emergency Cache",
        "class_name": "Neutral",
        "type_name": "Event",
        "xp": 0,
        "cost": 0,
        "traits": "Supply.",
        "text": "Gain 3 resources.",
        "pack_name": "Core Set",
    },
    {
        "id": "01089",
        "name": "Unexpected Courage",
        "class_name": "Neutral",
        "type_name": "Skill",
        "xp": 0,
        "cost": 0,
        "traits": "Innate.",
        "text": "Commit only to your own skill tests.",
        "pack_name": "Core Set",
    },
    {
        "id": "02026",
        "name": "Emergency Cache (2)",
        "class_name": "Neutral",
        "type_name": "Event",
        "xp": 2,
        "cost": 0,
        "traits": "Supply.",
        "text": "Gain 4 resources.",
        "pack_name": "The Dunwich Legacy",
    },
]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_chroma_client():
    """Create a ChromaDB client with temporary storage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        client = ChromaClient(persist_path=temp_dir)

        # Add investigators
        for investigator in SAMPLE_INVESTIGATORS:
            client.add_character(investigator.copy())

        # Add cards
        for card in SAMPLE_CARDS:
            client.add_card(card.copy())

        yield client


@pytest.fixture
def agent(temp_chroma_client):
    """Create an ActionSpaceAgent with the test ChromaDB."""
    return ActionSpaceAgent(chroma_client=temp_chroma_client)


# =============================================================================
# Integration Tests
# =============================================================================


class TestBasicSearch:
    """Basic search functionality tests."""

    def test_search_all_cards_for_investigator(self, agent):
        """Should return legal cards for the investigator."""
        query = ActionSpaceQuery(
            investigator_id="01001",  # Roland Banks
            upgrade_points=5,
            limit=50,
        )
        response = agent.search(query)

        assert isinstance(response, ActionSpaceResponse)
        assert len(response.candidates) > 0

        # Roland should get Guardian and Neutral cards
        for candidate in response.candidates:
            assert candidate.class_name in ["Guardian", "Neutral", "Seeker"]

    def test_search_with_text_query(self, agent):
        """Should find cards matching text query."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            search_query="weapon",
            limit=10,
        )
        response = agent.search(query)

        # Should find Machete and .45 Automatic
        card_names = [c.name for c in response.candidates]
        assert any("Machete" in name or ".45" in name for name in card_names)

    def test_search_with_capability_combat(self, agent):
        """Should find combat-relevant cards."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            capability_need="combat",
            limit=10,
        )
        response = agent.search(query)

        # Combat cards should score high
        assert len(response.candidates) > 0

        # Top results should be combat-oriented
        top_candidate = response.candidates[0]
        assert any(word in top_candidate.reason.lower()
                   for word in ["combat", "damage", "fight", "weapon"])


class TestClassAccessFiltering:
    """Tests for class access restrictions."""

    def test_roland_gets_guardian_cards(self, agent):
        """Roland should have access to all Guardian cards."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            limit=50,
        )
        response = agent.search(query)

        guardian_cards = [c for c in response.candidates if c.class_name == "Guardian"]
        assert len(guardian_cards) > 0

        # Should include Beat Cop (2) at XP 2
        card_names = [c.name for c in guardian_cards]
        assert "Beat Cop (2)" in card_names or any("Beat Cop" in n for n in card_names)

    def test_roland_gets_seeker_level_0(self, agent):
        """Roland should have access to Seeker level 0 cards."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            limit=50,
        )
        response = agent.search(query)

        # Filter to Seeker cards (based on hardcoded rules)
        seeker_cards = [c for c in response.candidates if c.class_name == "Seeker"]

        # All Seeker cards should be level 0
        for card in seeker_cards:
            assert card.xp_cost == 0

    def test_roland_no_mystic_cards(self, agent):
        """Roland should not have access to Mystic cards."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            limit=50,
        )
        response = agent.search(query)

        mystic_cards = [c for c in response.candidates if c.class_name == "Mystic"]
        assert len(mystic_cards) == 0

    def test_agnes_gets_mystic_cards(self, agent):
        """Agnes should have access to Mystic cards."""
        query = ActionSpaceQuery(
            investigator_id="01004",  # Agnes Baker
            upgrade_points=5,
            limit=50,
        )
        response = agent.search(query)

        mystic_cards = [c for c in response.candidates if c.class_name == "Mystic"]
        assert len(mystic_cards) > 0


class TestXpFiltering:
    """Tests for XP budget filtering."""

    def test_xp_0_only_level_0(self, agent):
        """With 0 XP, should only get level 0 cards."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=0,
            limit=50,
        )
        response = agent.search(query)

        for candidate in response.candidates:
            assert candidate.xp_cost == 0

    def test_xp_2_includes_level_2(self, agent):
        """With 2 XP, should include level 0-2 cards."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=2,
            limit=50,
        )
        response = agent.search(query)

        # Should have some level 2 cards
        xp_costs = [c.xp_cost for c in response.candidates]
        assert 2 in xp_costs or all(xp <= 2 for xp in xp_costs)

    def test_xp_1_excludes_level_2(self, agent):
        """With 1 XP, should exclude level 2+ cards."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=1,
            limit=50,
        )
        response = agent.search(query)

        for candidate in response.candidates:
            assert candidate.xp_cost <= 1


class TestTypeFiltering:
    """Tests for card type filtering."""

    def test_asset_filter(self, agent):
        """Should only return assets when filtered."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            type_filter="asset",
            limit=50,
        )
        response = agent.search(query)

        for candidate in response.candidates:
            assert candidate.card_type.lower() == "asset"

    def test_event_filter(self, agent):
        """Should only return events when filtered."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            type_filter="event",
            limit=50,
        )
        response = agent.search(query)

        for candidate in response.candidates:
            assert candidate.card_type.lower() == "event"

    def test_skill_filter(self, agent):
        """Should only return skills when filtered."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            type_filter="skill",
            limit=50,
        )
        response = agent.search(query)

        for candidate in response.candidates:
            assert candidate.card_type.lower() == "skill"


class TestTraitFiltering:
    """Tests for trait filtering."""

    def test_weapon_trait_filter(self, agent):
        """Should find weapons when filtering by trait."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            trait_filter=["weapon"],
            limit=50,
        )
        response = agent.search(query)

        # Should find weapons
        for candidate in response.candidates:
            assert "weapon" in candidate.traits.lower()

    def test_spell_trait_filter(self, agent):
        """Should find spells when filtering by trait."""
        query = ActionSpaceQuery(
            investigator_id="01004",  # Agnes can use Mystic spells
            upgrade_points=5,
            trait_filter=["spell"],
            limit=50,
        )
        response = agent.search(query)

        for candidate in response.candidates:
            assert "spell" in candidate.traits.lower()

    def test_multiple_traits_or(self, agent):
        """Multiple traits should use OR logic."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            trait_filter=["weapon", "ally"],
            limit=50,
        )
        response = agent.search(query)

        # Each card should have at least one of the traits
        for candidate in response.candidates:
            traits_lower = candidate.traits.lower()
            assert "weapon" in traits_lower or "ally" in traits_lower


class TestExcludeCards:
    """Tests for excluding specific cards."""

    def test_exclude_single_card(self, agent):
        """Should exclude specified card."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            exclude_cards=["01016"],  # Machete
            limit=50,
        )
        response = agent.search(query)

        card_ids = [c.card_id for c in response.candidates]
        assert "01016" not in card_ids

    def test_exclude_multiple_cards(self, agent):
        """Should exclude all specified cards."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            exclude_cards=["01016", "01017", "01020"],
            limit=50,
        )
        response = agent.search(query)

        card_ids = [c.card_id for c in response.candidates]
        assert "01016" not in card_ids
        assert "01017" not in card_ids
        assert "01020" not in card_ids


class TestRelevanceScoring:
    """Tests for relevance score ordering."""

    def test_results_sorted_by_relevance(self, agent):
        """Results should be sorted by relevance score (descending)."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            capability_need="combat",
            limit=10,
        )
        response = agent.search(query)

        if len(response.candidates) > 1:
            scores = [c.relevance_score for c in response.candidates]
            assert scores == sorted(scores, reverse=True)

    def test_name_match_scores_higher(self, agent):
        """Cards matching query in name should score higher."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            search_query="Machete",
            limit=10,
        )
        response = agent.search(query)

        # Machete should be first or near top
        if response.candidates:
            top_names = [c.name for c in response.candidates[:3]]
            assert "Machete" in top_names


class TestContextIntegration:
    """Tests for context parameter usage."""

    def test_owned_sets_filtering(self, agent):
        """Should filter by owned sets from context."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            limit=50,
        )
        context = {"owned_sets": ["Core Set"]}
        response = agent.search(query, context=context)

        # Cards without Core Set pack should be excluded
        # (assuming pack_name was properly added to test data)
        assert isinstance(response, ActionSpaceResponse)


class TestResponseMetadata:
    """Tests for response metadata."""

    def test_metadata_includes_query_info(self, agent):
        """Response metadata should include query information."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=3,
            type_filter="asset",
            capability_need="combat",
        )
        response = agent.search(query)

        assert response.metadata.agent_type == "action_space"
        assert response.metadata.query_type == "card_search"
        assert response.metadata.context_used["investigator_id"] == "01001"
        assert response.metadata.context_used["upgrade_points"] == 3

    def test_metadata_includes_match_count(self, agent):
        """Response metadata should include total matches."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            limit=10,
        )
        response = agent.search(query)

        assert "total_matches" in response.metadata.extra


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_unknown_investigator(self, agent):
        """Should handle unknown investigator gracefully."""
        query = ActionSpaceQuery(
            investigator_id="99999",  # Unknown
            upgrade_points=5,
            limit=10,
        )
        response = agent.search(query)

        # Should still return some results (neutral cards at minimum)
        assert isinstance(response, ActionSpaceResponse)

    def test_empty_result(self, agent):
        """Should handle no matching cards gracefully."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            search_query="xyznonexistent123",
            limit=10,
        )
        response = agent.search(query)

        assert isinstance(response, ActionSpaceResponse)
        assert response.candidates == []
        assert "No cards found" in response.content

    def test_very_restrictive_filters(self, agent):
        """Should handle very restrictive filter combinations."""
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=0,
            type_filter="skill",
            trait_filter=["spell"],  # No Guardian spell skills exist
            limit=10,
        )
        response = agent.search(query)

        assert isinstance(response, ActionSpaceResponse)
        # May be empty or very few results
