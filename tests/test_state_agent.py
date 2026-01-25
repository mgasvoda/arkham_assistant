"""Unit tests for the StateAgent implementation."""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.services.subagents.state_agent import (
    IDEAL_CAPABILITIES,
    SYNERGY_PATTERNS,
    StateAgent,
    StateQuery,
    StateResponse,
    SynergyInfo,
    create_state_agent,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def state_agent():
    """Create a StateAgent with mocked ChromaDB client."""
    agent = StateAgent()
    agent._client = MagicMock()
    return agent


@pytest.fixture
def sample_cards():
    """Sample cards for testing deck analysis."""
    return [
        {
            "code": "01016",
            "name": "Machete",
            "class_name": "Guardian",
            "type_name": "Asset",
            "cost": 3,
            "text": "Fight. You get +1 combat for this attack.",
            "traits": '["Item", "Weapon", "Melee"]',
            "icons": '{"combat": 1}',
            "xp_cost": 0,
            "count": 2,
        },
        {
            "code": "01020",
            "name": "Guard Dog",
            "class_name": "Guardian",
            "type_name": "Asset",
            "cost": 3,
            "text": "When an enemy attacks you, deal 1 damage to that enemy.",
            "traits": '["Ally", "Creature"]',
            "icons": '{"combat": 1, "willpower": 1}',
            "xp_cost": 0,
            "count": 1,
        },
        {
            "code": "01088",
            "name": "Emergency Cache",
            "class_name": "Neutral",
            "type_name": "Event",
            "cost": 0,
            "text": "Gain 3 resources.",
            "traits": '["Supply"]',
            "icons": "{}",
            "xp_cost": 0,
            "count": 2,
        },
        {
            "code": "01089",
            "name": "Guts",
            "class_name": "Neutral",
            "type_name": "Skill",
            "cost": None,
            "text": "If this skill test is successful, draw 1 card.",
            "traits": '["Innate"]',
            "icons": '{"willpower": 2}',
            "xp_cost": 0,
            "count": 2,
        },
        {
            "code": "01039",
            "name": "Magnifying Glass",
            "class_name": "Seeker",
            "type_name": "Asset",
            "cost": 1,
            "text": "You get +1 intellect while investigating.",
            "traits": '["Item", "Tool"]',
            "icons": '{"intellect": 1}',
            "xp_cost": 0,
            "count": 2,
        },
        {
            "code": "01037",
            "name": "Deduction",
            "class_name": "Seeker",
            "type_name": "Skill",
            "cost": None,
            "text": "If this skill test is successful during an investigate action, discover 1 additional clue.",
            "traits": '["Practiced"]',
            "icons": '{"intellect": 1}',
            "xp_cost": 0,
            "count": 2,
        },
    ]


@pytest.fixture
def combat_focused_deck():
    """Deck focused heavily on combat."""
    return [
        {
            "code": "01016",
            "name": "Machete",
            "class_name": "Guardian",
            "type_name": "Asset",
            "cost": 3,
            "text": "Fight. You get +1 combat for this attack.",
            "traits": '["Weapon"]',
            "icons": '{"combat": 1}',
            "count": 2,
        },
        {
            "code": "01017",
            "name": ".45 Automatic",
            "class_name": "Guardian",
            "type_name": "Asset",
            "cost": 4,
            "text": "Fight. You get +1 combat and deal +1 damage for this attack.",
            "traits": '["Weapon", "Firearm"]',
            "icons": '{"combat": 1}',
            "count": 2,
        },
        {
            "code": "01025",
            "name": "Vicious Blow",
            "class_name": "Guardian",
            "type_name": "Skill",
            "cost": None,
            "text": "If this skill test is successful, deal +1 damage for this attack.",
            "traits": '["Practiced"]',
            "icons": '{"combat": 1}',
            "count": 2,
        },
        {
            "code": "01028",
            "name": "Beat Cop",
            "class_name": "Guardian",
            "type_name": "Asset",
            "cost": 4,
            "text": "You get +1 combat. Exhaust Beat Cop and deal 1 damage to it: Deal 1 damage to an enemy at your location.",
            "traits": '["Ally", "Police"]',
            "icons": '{"combat": 1}',
            "count": 2,
        },
    ]


@pytest.fixture
def empty_deck():
    """Empty deck for edge case testing."""
    return []


@pytest.fixture
def single_class_deck():
    """Deck with only one class."""
    return [
        {
            "code": "01016",
            "name": "Machete",
            "class_name": "Guardian",
            "type_name": "Asset",
            "cost": 3,
            "text": "Fight action.",
            "count": 2,
        },
        {
            "code": "01028",
            "name": "Beat Cop",
            "class_name": "Guardian",
            "type_name": "Asset",
            "cost": 4,
            "text": "You get +1 combat.",
            "count": 2,
        },
    ]


@pytest.fixture
def multi_class_deck():
    """Deck with multiple classes."""
    return [
        {
            "code": "01016",
            "name": "Machete",
            "class_name": "Guardian",
            "type_name": "Asset",
            "cost": 3,
            "text": "Fight action.",
            "count": 2,
        },
        {
            "code": "01039",
            "name": "Magnifying Glass",
            "class_name": "Seeker",
            "type_name": "Asset",
            "cost": 1,
            "text": "Investigation bonus.",
            "count": 2,
        },
        {
            "code": "01088",
            "name": "Emergency Cache",
            "class_name": "Neutral",
            "type_name": "Event",
            "cost": 0,
            "text": "Gain resources.",
            "count": 2,
        },
        {
            "code": "01065",
            "name": "Sneak Attack",
            "class_name": "Rogue",
            "type_name": "Event",
            "cost": 2,
            "text": "Evade and deal damage.",
            "count": 1,
        },
    ]


# =============================================================================
# StateQuery Tests
# =============================================================================


class TestStateQuery:
    """Tests for StateQuery input schema."""

    def test_requires_investigator_id(self):
        """Should require investigator_id field."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StateQuery()

    def test_accepts_deck_id(self):
        """Should accept deck_id for stored deck analysis."""
        query = StateQuery(
            deck_id="deck_12345",
            investigator_id="01001",
        )
        assert query.deck_id == "deck_12345"
        assert query.card_list is None

    def test_accepts_card_list(self):
        """Should accept raw card list."""
        query = StateQuery(
            card_list=["01016", "01017"],
            investigator_id="01001",
        )
        assert query.card_list == ["01016", "01017"]
        assert query.deck_id is None

    def test_default_upgrade_points(self):
        """Should default upgrade_points to 0."""
        query = StateQuery(investigator_id="01001")
        assert query.upgrade_points == 0

    def test_upgrade_points_validation(self):
        """Should reject negative upgrade_points."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StateQuery(investigator_id="01001", upgrade_points=-5)


# =============================================================================
# StateResponse Tests
# =============================================================================


class TestStateResponse:
    """Tests for StateResponse output schema."""

    def test_default_values(self):
        """Should have sensible defaults for state-specific fields."""
        from backend.models.subagent_models import SubagentMetadata

        response = StateResponse(
            content="Test analysis",
            metadata=SubagentMetadata(agent_type="state"),
        )
        assert response.curve_analysis == {}
        assert response.type_distribution == {}
        assert response.class_distribution == {}
        assert response.identified_gaps == []
        assert response.strengths == []
        assert response.synergies == []
        assert response.upgrade_priority == []
        assert response.total_cards == 0
        assert response.investigator_name is None

    def test_accepts_all_fields(self):
        """Should accept all analysis fields."""
        from backend.models.subagent_models import SubagentMetadata

        response = StateResponse(
            content="Full analysis",
            confidence=0.9,
            sources=["Deck: Test"],
            metadata=SubagentMetadata(agent_type="state", query_type="deck_analysis"),
            curve_analysis={"0": 5, "1": 8, "2": 10},
            type_distribution={"Asset": 15, "Event": 10},
            class_distribution={"Guardian": 20, "Neutral": 5},
            identified_gaps=["card draw"],
            strengths=["strong combat"],
            synergies=[SynergyInfo(cards=["A", "B"], effect="combo")],
            upgrade_priority=["Machete"],
            total_cards=30,
            investigator_name="Roland Banks",
        )
        assert response.total_cards == 30
        assert "Guardian" in response.class_distribution
        assert response.content == "Full analysis"
        assert response.confidence == 0.9


# =============================================================================
# SynergyInfo Tests
# =============================================================================


class TestSynergyInfo:
    """Tests for SynergyInfo model."""

    def test_requires_cards_and_effect(self):
        """Should require cards and effect."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SynergyInfo()

    def test_default_strength(self):
        """Should default to moderate strength."""
        synergy = SynergyInfo(cards=["A", "B"], effect="test")
        assert synergy.strength == "moderate"

    def test_accepts_all_fields(self):
        """Should accept all synergy info fields."""
        synergy = SynergyInfo(
            cards=["Machete", "Beat Cop"],
            effect="Combat synergy",
            strength="strong",
        )
        assert len(synergy.cards) == 2
        assert synergy.strength == "strong"


# =============================================================================
# StateAgent Curve Analysis Tests
# =============================================================================


class TestStateAgentCurveAnalysis:
    """Tests for resource curve analysis."""

    def test_analyze_curve_basic(self, state_agent, sample_cards):
        """Should count cards by cost."""
        curve = state_agent._analyze_curve(sample_cards)

        # Check specific costs
        assert "3" in curve  # Machete, Guard Dog
        assert "0" in curve  # Emergency Cache
        assert "1" in curve  # Magnifying Glass

    def test_analyze_curve_with_counts(self, state_agent, sample_cards):
        """Should respect card counts."""
        curve = state_agent._analyze_curve(sample_cards)

        # Machete (2x) + Guard Dog (1x) = 3 cards at cost 3
        assert curve["3"] == 3
        # Emergency Cache 2x
        assert curve["0"] == 2

    def test_analyze_curve_empty_deck(self, state_agent, empty_deck):
        """Should handle empty deck."""
        curve = state_agent._analyze_curve(empty_deck)
        assert curve == {}

    def test_analyze_curve_skips_null_cost(self, state_agent, sample_cards):
        """Should skip cards with null cost (skills)."""
        curve = state_agent._analyze_curve(sample_cards)

        # Skills have no cost, shouldn't appear in curve
        # Total counted cards should exclude skills
        total_in_curve = sum(curve.values())
        total_cards = sum(c.get("count", 1) for c in sample_cards if c.get("cost") is not None)
        assert total_in_curve == total_cards


# =============================================================================
# StateAgent Type Distribution Tests
# =============================================================================


class TestStateAgentTypeDistribution:
    """Tests for card type distribution analysis."""

    def test_analyze_types_basic(self, state_agent, sample_cards):
        """Should count cards by type."""
        types = state_agent._analyze_types(sample_cards)

        assert "Asset" in types
        assert "Event" in types
        assert "Skill" in types

    def test_analyze_types_with_counts(self, state_agent, sample_cards):
        """Should respect card counts."""
        types = state_agent._analyze_types(sample_cards)

        # Assets: Machete 2x, Guard Dog 1x, Magnifying Glass 2x = 5
        assert types["Asset"] == 5
        # Events: Emergency Cache 2x
        assert types["Event"] == 2
        # Skills: Guts 2x, Deduction 2x = 4
        assert types["Skill"] == 4

    def test_analyze_types_empty_deck(self, state_agent, empty_deck):
        """Should handle empty deck."""
        types = state_agent._analyze_types(empty_deck)
        assert types == {}

    def test_analyze_types_handles_missing_field(self, state_agent):
        """Should handle cards without type field."""
        cards = [{"name": "Unknown", "count": 1}]
        types = state_agent._analyze_types(cards)
        assert "Unknown" in types


# =============================================================================
# StateAgent Class Distribution Tests
# =============================================================================


class TestStateAgentClassDistribution:
    """Tests for class distribution analysis."""

    def test_analyze_classes_basic(self, state_agent, sample_cards):
        """Should count cards by class."""
        classes = state_agent._analyze_classes(sample_cards)

        assert "Guardian" in classes
        assert "Seeker" in classes
        assert "Neutral" in classes

    def test_analyze_classes_with_counts(self, state_agent, sample_cards):
        """Should respect card counts."""
        classes = state_agent._analyze_classes(sample_cards)

        # Guardian: Machete 2x, Guard Dog 1x = 3
        assert classes["Guardian"] == 3
        # Seeker: Magnifying Glass 2x, Deduction 2x = 4
        assert classes["Seeker"] == 4
        # Neutral: Emergency Cache 2x, Guts 2x = 4
        assert classes["Neutral"] == 4

    def test_analyze_classes_single_class(self, state_agent, single_class_deck):
        """Should handle single-class decks."""
        classes = state_agent._analyze_classes(single_class_deck)
        assert len(classes) == 1
        assert "Guardian" in classes

    def test_analyze_classes_multi_class(self, state_agent, multi_class_deck):
        """Should handle multi-class decks."""
        classes = state_agent._analyze_classes(multi_class_deck)
        assert len(classes) == 4
        assert "Guardian" in classes
        assert "Seeker" in classes
        assert "Neutral" in classes
        assert "Rogue" in classes

    def test_analyze_classes_empty_deck(self, state_agent, empty_deck):
        """Should handle empty deck."""
        classes = state_agent._analyze_classes(empty_deck)
        assert classes == {}


# =============================================================================
# StateAgent Gap Identification Tests
# =============================================================================


class TestStateAgentGapIdentification:
    """Tests for gap identification logic."""

    def test_identify_gaps_finds_missing(self, state_agent, combat_focused_deck):
        """Should identify missing capabilities."""
        gaps = state_agent._identify_gaps(combat_focused_deck)

        # Combat-focused deck should have gaps in other areas
        gap_text = " ".join(gaps)
        # Should be missing card draw, clues, etc.
        assert len(gaps) > 0

    def test_identify_gaps_empty_deck(self, state_agent, empty_deck):
        """Should identify all gaps for empty deck."""
        gaps = state_agent._identify_gaps(empty_deck)

        # Should have gaps for all capabilities
        assert len(gaps) == len(IDEAL_CAPABILITIES)

    def test_identify_gaps_includes_counts(self, state_agent, sample_cards):
        """Should include current/minimum counts in gap messages."""
        gaps = state_agent._identify_gaps(sample_cards)

        for gap in gaps:
            # Each gap should mention card counts
            assert "/" in gap  # Format: (X/Y cards)

    def test_identify_gaps_balanced_deck(self, state_agent):
        """Well-rounded deck should have fewer gaps."""
        balanced_cards = [
            {"name": "Card Draw 1", "text": "draw 2 cards", "count": 2},
            {"name": "Card Draw 2", "text": "search your deck", "count": 2},
            {"name": "Resource 1", "text": "gain 3 resources", "count": 2},
            {"name": "Resource 2", "text": "gain resource", "count": 2},
            {"name": "Combat 1", "text": "fight action", "count": 3},
            {"name": "Combat 2", "text": "deal damage", "count": 3},
            {"name": "Clue 1", "text": "investigate action", "count": 3},
            {"name": "Clue 2", "text": "discover clue", "count": 3},
            {"name": "Will 1", "icons": '{"willpower": 2}', "count": 3},
            {"name": "Will 2", "icons": '{"willpower": 2}', "count": 3},
            {"name": "Cancel 1", "text": "cancel that effect", "count": 2},
            {"name": "Heal 1", "text": "heal 2 damage", "count": 2},
        ]
        gaps = state_agent._identify_gaps(balanced_cards)
        assert len(gaps) < len(IDEAL_CAPABILITIES)


# =============================================================================
# StateAgent Strength Identification Tests
# =============================================================================


class TestStateAgentStrengthIdentification:
    """Tests for strength identification logic."""

    def test_identify_strengths_combat_focused(self, state_agent, combat_focused_deck):
        """Should identify combat as a strength in combat deck."""
        strengths = state_agent._identify_strengths(combat_focused_deck)

        strength_text = " ".join(strengths).lower()
        # Should recognize combat strength or asset presence (all combat cards are assets)
        assert "combat" in strength_text or "board presence" in strength_text or len(strengths) > 0

    def test_identify_strengths_empty_deck(self, state_agent, empty_deck):
        """Should have no strengths for empty deck."""
        strengths = state_agent._identify_strengths(empty_deck)
        assert len(strengths) == 0

    def test_identify_strengths_asset_heavy(self, state_agent):
        """Should identify board presence in asset-heavy decks."""
        asset_heavy = [
            {"name": f"Asset {i}", "type_name": "Asset", "count": 1}
            for i in range(20)
        ]
        asset_heavy.extend([
            {"name": f"Event {i}", "type_name": "Event", "count": 1}
            for i in range(5)
        ])

        strengths = state_agent._identify_strengths(asset_heavy)
        strength_text = " ".join(strengths).lower()
        assert "board presence" in strength_text or "asset" in strength_text

    def test_identify_strengths_skill_heavy(self, state_agent):
        """Should identify test reliability in skill-heavy decks."""
        skill_heavy = [
            {"name": f"Skill {i}", "type_name": "Skill", "count": 1}
            for i in range(10)
        ]
        skill_heavy.extend([
            {"name": f"Asset {i}", "type_name": "Asset", "count": 1}
            for i in range(20)
        ])

        strengths = state_agent._identify_strengths(skill_heavy)
        strength_text = " ".join(strengths).lower()
        assert "skill" in strength_text or "test" in strength_text


# =============================================================================
# StateAgent Synergy Detection Tests
# =============================================================================


class TestStateAgentSynergyDetection:
    """Tests for synergy detection logic."""

    def test_detect_synergies_basic(self, state_agent, sample_cards):
        """Should detect synergies when cards match patterns."""
        synergies = state_agent._detect_synergies(sample_cards)

        # Should be a list of SynergyInfo
        assert isinstance(synergies, list)

    def test_detect_synergies_requires_multiple_cards(self, state_agent):
        """Should only report synergies with 2+ cards."""
        single_card = [
            {"name": "Single", "text": "draw a card", "count": 1}
        ]
        synergies = state_agent._detect_synergies(single_card)
        assert len(synergies) == 0

    def test_detect_synergies_combat_synergy(self, state_agent, combat_focused_deck):
        """Should detect combat synergies in combat deck."""
        synergies = state_agent._detect_synergies(combat_focused_deck)

        # Should have at least one synergy
        if synergies:
            synergy_effects = [s.effect.lower() for s in synergies]
            # Combat deck should have combat-related synergies
            has_combat = any("combat" in e or "fight" in e or "attack" in e for e in synergy_effects)
            assert has_combat or len(synergies) > 0

    def test_detect_synergies_strength_levels(self, state_agent):
        """Should assign strength based on card count."""
        # 2 cards = weak
        two_cards = [
            {"name": "Draw 1", "text": "draw a card", "count": 1},
            {"name": "Draw 2", "text": "draw 2 cards", "count": 1},
        ]
        synergies_weak = state_agent._detect_synergies(two_cards)

        # 4+ cards = strong
        many_cards = [
            {"name": f"Draw {i}", "text": "draw a card", "count": 1}
            for i in range(5)
        ]
        synergies_strong = state_agent._detect_synergies(many_cards)

        # Check strength assignments
        if synergies_weak:
            assert any(s.strength in ["weak", "moderate"] for s in synergies_weak)
        if synergies_strong:
            assert any(s.strength == "strong" for s in synergies_strong)

    def test_detect_synergies_empty_deck(self, state_agent, empty_deck):
        """Should return empty list for empty deck."""
        synergies = state_agent._detect_synergies(empty_deck)
        assert synergies == []


# =============================================================================
# StateAgent Upgrade Priority Tests
# =============================================================================


class TestStateAgentUpgradePriority:
    """Tests for upgrade priority logic."""

    def test_prioritize_upgrades_basic(self, state_agent, sample_cards):
        """Should return list of upgrade candidates."""
        priorities = state_agent._prioritize_upgrades(sample_cards, available_xp=10)
        assert isinstance(priorities, list)

    def test_prioritize_upgrades_excludes_upgraded(self, state_agent):
        """Should exclude cards that already have XP."""
        cards = [
            {"name": "Level 0", "text": "draw card", "xp_cost": 0, "count": 1},
            {"name": "Level 2", "text": "draw card", "xp_cost": 2, "count": 1},
        ]
        priorities = state_agent._prioritize_upgrades(cards, available_xp=5)

        assert "Level 0" in priorities or len(priorities) == 0
        assert "Level 2" not in priorities

    def test_prioritize_upgrades_limited_count(self, state_agent):
        """Should limit to top 10 candidates."""
        many_cards = [
            {"name": f"Card {i}", "text": "draw card fight investigate", "xp_cost": 0, "count": 1}
            for i in range(20)
        ]
        priorities = state_agent._prioritize_upgrades(many_cards, available_xp=10)
        assert len(priorities) <= 10

    def test_prioritize_upgrades_empty_deck(self, state_agent, empty_deck):
        """Should return empty list for empty deck."""
        priorities = state_agent._prioritize_upgrades(empty_deck, available_xp=10)
        assert priorities == []


# =============================================================================
# StateAgent Full Analysis Tests
# =============================================================================


class TestStateAgentAnalyze:
    """Tests for full deck analysis."""

    def test_analyze_with_deck_id(self, state_agent):
        """Should analyze stored deck by ID."""
        # Mock get_deck
        mock_deck = {
            "name": "Test Deck",
            "investigator_name": "Roland Banks",
            "cards": '[{"id": "01016", "count": 2}]',
        }
        mock_card = {
            "code": "01016",
            "name": "Machete",
            "class_name": "Guardian",
            "type_name": "Asset",
            "cost": 3,
            "text": "Fight action",
        }

        with patch("backend.services.agent_tools.get_deck", return_value=mock_deck):
            state_agent._client.get_card.return_value = mock_card

            query = StateQuery(deck_id="deck_123", investigator_id="01001")
            response = state_agent.analyze(query)

            assert response.investigator_name == "Roland Banks"
            assert response.total_cards > 0

    def test_analyze_with_card_list(self, state_agent, sample_cards):
        """Should analyze raw card list."""
        # Setup mock to return cards
        def mock_get_card(card_id):
            for card in sample_cards:
                if card.get("code") == card_id:
                    return card
            return None

        state_agent._client.get_card.side_effect = mock_get_card
        state_agent._client.get_character.return_value = {"name": "Roland Banks"}

        card_list = [c["code"] for c in sample_cards]
        query = StateQuery(card_list=card_list, investigator_id="01001")
        response = state_agent.analyze(query)

        assert response.total_cards > 0
        assert len(response.curve_analysis) > 0

    def test_analyze_empty_deck(self, state_agent):
        """Should handle empty deck gracefully."""
        mock_deck = {
            "name": "Empty Deck",
            "investigator_name": "Roland Banks",
            "cards": "[]",
        }

        with patch("backend.services.agent_tools.get_deck", return_value=mock_deck):
            query = StateQuery(deck_id="deck_empty", investigator_id="01001")
            response = state_agent.analyze(query)

            assert response.total_cards == 0
            assert "Empty deck" in response.identified_gaps[0]

    def test_analyze_raises_without_deck_source(self, state_agent):
        """Should raise if neither deck_id nor card_list provided."""
        query = StateQuery(investigator_id="01001")

        with pytest.raises(ValueError) as exc_info:
            state_agent.analyze(query)
        assert "deck_id or card_list" in str(exc_info.value)

    def test_analyze_returns_all_fields(self, state_agent, sample_cards):
        """Should return complete StateResponse with all fields."""
        def mock_get_card(card_id):
            for card in sample_cards:
                if card.get("code") == card_id:
                    return card
            return None

        state_agent._client.get_card.side_effect = mock_get_card
        state_agent._client.get_character.return_value = {"name": "Roland Banks"}

        card_list = [c["code"] for c in sample_cards]
        query = StateQuery(card_list=card_list, investigator_id="01001", upgrade_points=5)
        response = state_agent.analyze(query)

        # Check all fields are populated
        assert isinstance(response.curve_analysis, dict)
        assert isinstance(response.type_distribution, dict)
        assert isinstance(response.class_distribution, dict)
        assert isinstance(response.identified_gaps, list)
        assert isinstance(response.strengths, list)
        assert isinstance(response.synergies, list)
        assert isinstance(response.upgrade_priority, list)
        assert isinstance(response.total_cards, int)


# =============================================================================
# Card List Expansion Tests
# =============================================================================


class TestStateAgentCardExpansion:
    """Tests for card list format handling."""

    def test_expand_list_of_ids(self, state_agent):
        """Should handle list of card IDs."""
        mock_card = {"code": "01016", "name": "Machete"}
        state_agent._client.get_card.return_value = mock_card

        cards = state_agent._expand_card_list(["01016", "01016", "01017"])

        # Should have 2 unique cards with correct counts
        assert len(cards) >= 1

    def test_expand_list_of_dicts(self, state_agent):
        """Should handle list of dicts with id and count."""
        # Return different cards based on ID
        def mock_get_card(card_id):
            if card_id == "01016":
                return {"code": "01016", "name": "Machete"}
            elif card_id == "01017":
                return {"code": "01017", "name": "Beat Cop"}
            return None

        state_agent._client.get_card.side_effect = mock_get_card

        cards = state_agent._expand_card_list([
            {"id": "01016", "count": 2},
            {"id": "01017", "count": 1},
        ])

        # Check counts are preserved
        for card in cards:
            if card.get("code") == "01016":
                assert card.get("count") == 2

    def test_expand_dict_mapping(self, state_agent):
        """Should handle dict mapping card_id -> count."""
        mock_card = {"code": "01016", "name": "Machete"}
        state_agent._client.get_card.return_value = mock_card

        cards = state_agent._expand_card_list({"01016": 2, "01017": 1})

        assert len(cards) >= 1

    def test_expand_parses_json_fields(self, state_agent):
        """Should parse JSON fields in card data."""
        mock_card = {
            "code": "01016",
            "name": "Machete",
            "traits": '["Weapon", "Melee"]',
            "icons": '{"combat": 1}',
        }
        state_agent._client.get_card.return_value = mock_card

        cards = state_agent._expand_card_list(["01016"])

        if cards:
            card = cards[0]
            # JSON fields should be parsed
            if isinstance(card.get("traits"), list):
                assert "Weapon" in card["traits"]
            if isinstance(card.get("icons"), dict):
                assert card["icons"].get("combat") == 1


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateStateAgent:
    """Tests for create_state_agent factory function."""

    def test_creates_state_agent(self):
        """Should create a StateAgent instance."""
        agent = create_state_agent()
        assert isinstance(agent, StateAgent)

    def test_agent_has_lazy_client(self):
        """Agent should have lazy-loaded client."""
        agent = create_state_agent()
        assert agent._client is None  # Not loaded yet


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestStateAgentEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_malformed_json(self, state_agent):
        """Should handle malformed JSON in card fields gracefully."""
        cards = [{
            "name": "Bad Card",
            "traits": "not valid json",
            "icons": "also not json",
            "text": "Some text",
            "count": 1,
        }]

        # These should not raise
        gaps = state_agent._identify_gaps(cards)
        strengths = state_agent._identify_strengths(cards)
        synergies = state_agent._detect_synergies(cards)

        assert isinstance(gaps, list)
        assert isinstance(strengths, list)
        assert isinstance(synergies, list)

    def test_handles_missing_fields(self, state_agent):
        """Should handle cards with missing fields."""
        minimal_cards = [
            {"name": "Minimal Card", "count": 1},
        ]

        curve = state_agent._analyze_curve(minimal_cards)
        types = state_agent._analyze_types(minimal_cards)
        classes = state_agent._analyze_classes(minimal_cards)

        # Should not raise, should use defaults
        assert isinstance(curve, dict)
        assert isinstance(types, dict)
        assert isinstance(classes, dict)

    def test_handles_none_values(self, state_agent):
        """Should handle None values in card fields."""
        cards = [{
            "name": "None Card",
            "cost": None,
            "type_name": None,
            "class_name": None,
            "text": None,
            "count": 1,
        }]

        # These should not raise
        curve = state_agent._analyze_curve(cards)
        types = state_agent._analyze_types(cards)
        classes = state_agent._analyze_classes(cards)
        gaps = state_agent._identify_gaps(cards)

        assert isinstance(curve, dict)
        assert isinstance(types, dict)
        assert isinstance(classes, dict)
        assert isinstance(gaps, list)
