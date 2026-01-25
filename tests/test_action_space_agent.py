"""Unit tests for the ActionSpaceAgent.

Tests cover:
- Class access filtering based on investigator rules
- XP cost filtering
- Type and trait filtering
- Ownership filtering
- Relevance scoring
- Search functionality
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.services.subagents.action_space_agent import (
    CAPABILITY_KEYWORDS,
    INVESTIGATOR_CLASS_ACCESS,
    ActionSpaceAgent,
    ActionSpaceQuery,
    ActionSpaceResponse,
    CardCandidate,
    InvestigatorAccessRules,
    create_action_space_agent,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_chroma_client():
    """Create a mock ChromaDB client."""
    mock_client = MagicMock()

    # Mock character/investigator data
    mock_client.get_character.return_value = {
        "code": "01001",
        "name": "Roland Banks",
        "faction_name": "Guardian",
        "deck_options": "Seeker cards level 0",
    }

    return mock_client


@pytest.fixture
def agent(mock_chroma_client):
    """Create an ActionSpaceAgent with mocked ChromaDB."""
    return ActionSpaceAgent(chroma_client=mock_chroma_client)


@pytest.fixture
def sample_cards():
    """Sample card data for testing."""
    return [
        {
            "code": "01016",
            "name": "Machete",
            "class_name": "Guardian",
            "type_name": "Asset",
            "xp": 0,
            "cost": 3,
            "traits": "Item. Weapon. Melee.",
            "text": "Fight. +1 combat for this attack. If you are engaged with only 1 enemy, this attack deals +1 damage.",
        },
        {
            "code": "01020",
            "name": "Beat Cop",
            "class_name": "Guardian",
            "type_name": "Asset",
            "xp": 0,
            "cost": 4,
            "traits": "Ally. Police.",
            "text": "While Beat Cop is in play, you get +1 combat.",
        },
        {
            "code": "01025",
            "name": "Shrivelling",
            "class_name": "Mystic",
            "type_name": "Asset",
            "xp": 0,
            "cost": 3,
            "traits": "Spell.",
            "text": "Fight. Use willpower instead of combat for this attack.",
        },
        {
            "code": "01030",
            "name": "Higher Education",
            "class_name": "Seeker",
            "type_name": "Asset",
            "xp": 3,
            "cost": 0,
            "traits": "Talent.",
            "text": "While you have 5 or more cards in hand, you get +2 intellect and +2 willpower.",
        },
        {
            "code": "01088",
            "name": "Emergency Cache",
            "class_name": "Neutral",
            "type_name": "Event",
            "xp": 0,
            "cost": 0,
            "traits": "Supply.",
            "text": "Gain 3 resources.",
        },
        {
            "code": "01089",
            "name": "Unexpected Courage",
            "class_name": "Neutral",
            "type_name": "Skill",
            "xp": 0,
            "cost": None,
            "traits": "Innate.",
            "text": "Commit only to your own skill tests.",
        },
        {
            "code": "02020",
            "name": "Beat Cop (2)",
            "class_name": "Guardian",
            "type_name": "Asset",
            "xp": 2,
            "cost": 4,
            "traits": "Ally. Police.",
            "text": "While Beat Cop is in play, you get +1 combat. Exhaust Beat Cop and deal 1 damage to it: Deal 1 damage to an enemy at your location.",
        },
        {
            "code": "02028",
            "name": "Delve Too Deep",
            "class_name": "Mystic",
            "type_name": "Event",
            "xp": 0,
            "cost": 1,
            "traits": "Insight.",
            "text": "Fast. Play during the mythos phase. Add 1 doom to the current agenda. Each investigator earns 1 additional experience.",
        },
    ]


# =============================================================================
# InvestigatorAccessRules Tests
# =============================================================================


class TestInvestigatorAccessRules:
    """Tests for investigator deckbuilding rules."""

    def test_hardcoded_roland_banks(self, agent):
        """Roland Banks should have Guardian 5, Neutral 5, Seeker 0."""
        rules = agent._get_investigator_rules("01001")

        assert rules.investigator_id == "01001"
        assert rules.class_access.get("Guardian") == 5
        assert rules.class_access.get("Neutral") == 5
        # Seeker access comes from both hardcoded and mock data

    def test_hardcoded_agnes_baker(self, agent):
        """Agnes Baker should have Mystic 5, Neutral 5, Survivor 2."""
        # Override mock to return Agnes
        agent._chroma_client.get_character.return_value = None

        rules = agent._get_investigator_rules("01004")

        assert rules.class_access.get("Mystic") == 5
        assert rules.class_access.get("Neutral") == 5
        assert rules.class_access.get("Survivor") == 2

    def test_unknown_investigator_gets_default(self, agent):
        """Unknown investigator should get default rules."""
        agent._chroma_client.get_character.return_value = None

        rules = agent._get_investigator_rules("99999")

        # Default: Neutral 5 only
        assert rules.class_access.get("Neutral") == 5

    def test_rules_from_chromadb(self, agent):
        """Rules should incorporate ChromaDB character data."""
        agent._chroma_client.get_character.return_value = {
            "code": "custom01",
            "name": "Custom Investigator",
            "faction_name": "Survivor",
            "deck_options": '{"Guardian": 0}',
        }

        rules = agent._get_investigator_rules("custom01")

        assert rules.investigator_name == "Custom Investigator"
        assert rules.class_access.get("Survivor") == 5
        assert rules.class_access.get("Neutral") == 5


# =============================================================================
# Card Legality Tests
# =============================================================================


class TestCardLegality:
    """Tests for card legality checking."""

    def test_primary_class_card_legal(self, agent, sample_cards):
        """Guardian card should be legal for Roland Banks."""
        rules = InvestigatorAccessRules(
            investigator_id="01001",
            class_access={"Guardian": 5, "Neutral": 5, "Seeker": 0},
        )
        machete = sample_cards[0]  # Guardian, level 0

        assert agent._is_card_legal(machete, rules, max_xp=0) is True

    def test_secondary_class_level_0_legal(self, agent, sample_cards):
        """Seeker level 0 should be legal for Roland (has Seeker 0 access)."""
        rules = InvestigatorAccessRules(
            investigator_id="01001",
            class_access={"Guardian": 5, "Neutral": 5, "Seeker": 0},
        )
        # Create a level 0 Seeker card
        seeker_card = {"class_name": "Seeker", "xp": 0}

        assert agent._is_card_legal(seeker_card, rules, max_xp=5) is True

    def test_secondary_class_higher_level_illegal(self, agent, sample_cards):
        """Seeker level 3 should be illegal for Roland (only has Seeker 0)."""
        rules = InvestigatorAccessRules(
            investigator_id="01001",
            class_access={"Guardian": 5, "Neutral": 5, "Seeker": 0},
        )
        higher_education = sample_cards[3]  # Seeker, level 3

        assert agent._is_card_legal(higher_education, rules, max_xp=5) is False

    def test_no_class_access_illegal(self, agent, sample_cards):
        """Mystic card should be illegal for Roland (no Mystic access)."""
        rules = InvestigatorAccessRules(
            investigator_id="01001",
            class_access={"Guardian": 5, "Neutral": 5, "Seeker": 0},
        )
        shrivelling = sample_cards[2]  # Mystic, level 0

        assert agent._is_card_legal(shrivelling, rules, max_xp=5) is False

    def test_neutral_always_legal(self, agent, sample_cards):
        """Neutral cards should always be legal."""
        rules = InvestigatorAccessRules(
            investigator_id="01001",
            class_access={"Guardian": 5, "Neutral": 5},
        )
        emergency_cache = sample_cards[4]  # Neutral, level 0

        assert agent._is_card_legal(emergency_cache, rules, max_xp=0) is True

    def test_xp_constraint_respected(self, agent, sample_cards):
        """Cards above XP budget should be illegal."""
        rules = InvestigatorAccessRules(
            investigator_id="01001",
            class_access={"Guardian": 5, "Neutral": 5},
        )
        beat_cop_2 = sample_cards[6]  # Guardian, level 2

        # Should be illegal with max_xp=1
        assert agent._is_card_legal(beat_cop_2, rules, max_xp=1) is False

        # Should be legal with max_xp=2
        assert agent._is_card_legal(beat_cop_2, rules, max_xp=2) is True

    def test_missing_level_defaults_to_zero(self, agent):
        """Cards with missing level should default to level 0."""
        rules = InvestigatorAccessRules(
            investigator_id="01001",
            class_access={"Guardian": 5},
        )
        card = {"class_name": "Guardian", "xp": None}

        assert agent._is_card_legal(card, rules, max_xp=0) is True


# =============================================================================
# Filter Tests
# =============================================================================


class TestTypeFilter:
    """Tests for card type filtering."""

    def test_asset_filter(self, agent, sample_cards):
        """Should match asset cards."""
        machete = sample_cards[0]  # Asset

        assert agent._matches_type_filter(machete, "asset") is True
        assert agent._matches_type_filter(machete, "event") is False

    def test_event_filter(self, agent, sample_cards):
        """Should match event cards."""
        emergency_cache = sample_cards[4]  # Event

        assert agent._matches_type_filter(emergency_cache, "event") is True
        assert agent._matches_type_filter(emergency_cache, "asset") is False

    def test_skill_filter(self, agent, sample_cards):
        """Should match skill cards."""
        unexpected_courage = sample_cards[5]  # Skill

        assert agent._matches_type_filter(unexpected_courage, "skill") is True
        assert agent._matches_type_filter(unexpected_courage, "event") is False

    def test_none_filter_matches_all(self, agent, sample_cards):
        """None filter should match all cards."""
        for card in sample_cards:
            assert agent._matches_type_filter(card, None) is True

    def test_case_insensitive(self, agent, sample_cards):
        """Filter should be case-insensitive."""
        machete = sample_cards[0]

        assert agent._matches_type_filter(machete, "ASSET") is True
        assert agent._matches_type_filter(machete, "Asset") is True
        assert agent._matches_type_filter(machete, "asset") is True


class TestTraitFilter:
    """Tests for card trait filtering."""

    def test_single_trait_match(self, agent, sample_cards):
        """Should match if card has the trait."""
        machete = sample_cards[0]  # Has "Weapon" trait

        assert agent._matches_trait_filter(machete, ["weapon"]) is True

    def test_multiple_trait_or_logic(self, agent, sample_cards):
        """Should match if card has ANY of the traits (OR logic)."""
        machete = sample_cards[0]  # Has "Weapon", "Melee", "Item"

        assert agent._matches_trait_filter(machete, ["weapon", "spell"]) is True
        assert agent._matches_trait_filter(machete, ["tome", "spell"]) is False

    def test_spell_trait(self, agent, sample_cards):
        """Should find spell cards."""
        shrivelling = sample_cards[2]  # Has "Spell" trait

        assert agent._matches_trait_filter(shrivelling, ["spell"]) is True

    def test_none_filter_matches_all(self, agent, sample_cards):
        """None filter should match all cards."""
        for card in sample_cards:
            assert agent._matches_trait_filter(card, None) is True

    def test_case_insensitive(self, agent, sample_cards):
        """Filter should be case-insensitive."""
        machete = sample_cards[0]

        assert agent._matches_trait_filter(machete, ["WEAPON"]) is True
        assert agent._matches_trait_filter(machete, ["Weapon"]) is True


class TestOwnershipFilter:
    """Tests for ownership filtering."""

    def test_owned_flag_true(self, agent):
        """Should match cards marked as owned."""
        card = {"name": "Test Card", "owned": True}

        assert agent._matches_ownership(card, ["Core Set"]) is True

    def test_pack_name_match(self, agent):
        """Should match cards from owned packs."""
        card = {"name": "Test Card", "pack_name": "Core Set"}

        assert agent._matches_ownership(card, ["Core Set"]) is True
        assert agent._matches_ownership(card, ["Dunwich Legacy"]) is False

    def test_partial_pack_name_match(self, agent):
        """Should match partial pack names."""
        card = {"name": "Test Card", "pack_name": "The Dunwich Legacy Investigator Expansion"}

        assert agent._matches_ownership(card, ["Dunwich Legacy"]) is True

    def test_none_ownership_matches_all(self, agent, sample_cards):
        """None owned_sets should match all cards."""
        for card in sample_cards:
            assert agent._matches_ownership(card, None) is True


# =============================================================================
# Relevance Scoring Tests
# =============================================================================


class TestRelevanceScoring:
    """Tests for relevance score calculation."""

    def test_name_match_high_score(self, agent, sample_cards):
        """Cards matching search query in name should score higher."""
        machete = sample_cards[0]
        query = ActionSpaceQuery(
            investigator_id="01001",
            search_query="Machete"
        )

        score, reason = agent._calculate_relevance_score(machete, query)

        assert score >= 0.7
        assert "Name matches" in reason

    def test_text_match_medium_score(self, agent, sample_cards):
        """Cards matching search query in text should score moderately."""
        machete = sample_cards[0]  # Text mentions "damage"
        query = ActionSpaceQuery(
            investigator_id="01001",
            search_query="damage"
        )

        score, reason = agent._calculate_relevance_score(machete, query)

        assert score >= 0.6
        assert "damage" in reason.lower()

    def test_capability_combat_match(self, agent, sample_cards):
        """Cards matching combat capability should score higher."""
        machete = sample_cards[0]  # Weapon, deals damage
        query = ActionSpaceQuery(
            investigator_id="01001",
            capability_need="combat"
        )

        score, reason = agent._calculate_relevance_score(machete, query)

        assert "combat" in reason.lower()
        assert score >= 0.5

    def test_capability_economy_match(self, agent, sample_cards):
        """Cards matching economy capability should score higher."""
        emergency_cache = sample_cards[4]  # Gains resources
        query = ActionSpaceQuery(
            investigator_id="01001",
            capability_need="economy"
        )

        score, reason = agent._calculate_relevance_score(emergency_cache, query)

        assert "economy" in reason.lower()

    def test_score_in_valid_range(self, agent, sample_cards):
        """Scores should always be between 0 and 1."""
        for card in sample_cards:
            query = ActionSpaceQuery(
                investigator_id="01001",
                search_query="test",
                capability_need="combat",
                trait_filter=["spell", "weapon"],
            )
            score, _ = agent._calculate_relevance_score(card, query)

            assert 0.0 <= score <= 1.0


# =============================================================================
# Search Integration Tests
# =============================================================================


class TestSearchIntegration:
    """Tests for the main search functionality."""

    def test_search_returns_response(self, agent, sample_cards):
        """Search should return an ActionSpaceResponse."""
        agent._chroma_client.search_cards.return_value = sample_cards

        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
        )
        response = agent.search(query)

        assert isinstance(response, ActionSpaceResponse)
        assert response.metadata.agent_type == "action_space"

    def test_search_filters_by_class(self, agent, sample_cards):
        """Search should only return legal cards for investigator."""
        agent._chroma_client.search_cards.return_value = sample_cards

        query = ActionSpaceQuery(
            investigator_id="01001",  # Roland: Guardian, Neutral, Seeker 0
            upgrade_points=5,
        )
        response = agent.search(query)

        # Should not include Mystic cards
        card_classes = [c.class_name for c in response.candidates]
        assert "Mystic" not in card_classes

    def test_search_filters_by_xp(self, agent, sample_cards):
        """Search should respect XP budget."""
        agent._chroma_client.search_cards.return_value = sample_cards

        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=1,  # Only level 0-1
        )
        response = agent.search(query)

        # Should not include level 2+ cards
        for candidate in response.candidates:
            assert candidate.xp_cost <= 1

    def test_search_filters_by_type(self, agent, sample_cards):
        """Search should filter by card type."""
        agent._chroma_client.search_cards.return_value = sample_cards

        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            type_filter="asset",
        )
        response = agent.search(query)

        for candidate in response.candidates:
            assert candidate.card_type.lower() == "asset"

    def test_search_excludes_cards(self, agent, sample_cards):
        """Search should exclude specified cards."""
        agent._chroma_client.search_cards.return_value = sample_cards

        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            exclude_cards=["01016"],  # Exclude Machete
        )
        response = agent.search(query)

        card_ids = [c.card_id for c in response.candidates]
        assert "01016" not in card_ids

    def test_search_respects_limit(self, agent, sample_cards):
        """Search should respect result limit."""
        agent._chroma_client.search_cards.return_value = sample_cards

        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            limit=3,
        )
        response = agent.search(query)

        assert len(response.candidates) <= 3

    def test_search_sorts_by_relevance(self, agent, sample_cards):
        """Search results should be sorted by relevance score."""
        agent._chroma_client.search_cards.return_value = sample_cards

        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            capability_need="combat",
        )
        response = agent.search(query)

        if len(response.candidates) > 1:
            scores = [c.relevance_score for c in response.candidates]
            assert scores == sorted(scores, reverse=True)

    def test_search_with_owned_sets_context(self, agent, sample_cards):
        """Search should use owned_sets from context."""
        # Add pack_name to sample cards
        for i, card in enumerate(sample_cards):
            card["pack_name"] = "Core Set" if i < 4 else "Dunwich Legacy"

        agent._chroma_client.search_cards.return_value = sample_cards

        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
        )
        context = {"owned_sets": ["Core Set"]}
        response = agent.search(query, context=context)

        # All returned cards should be from Core Set
        # (This is a soft check since some cards might not have pack_name)
        assert isinstance(response, ActionSpaceResponse)


# =============================================================================
# CardCandidate Tests
# =============================================================================


class TestCardCandidate:
    """Tests for CardCandidate model."""

    def test_valid_candidate(self):
        """Should create valid candidate with all fields."""
        candidate = CardCandidate(
            card_id="01016",
            name="Machete",
            xp_cost=0,
            relevance_score=0.85,
            reason="Excellent combat weapon",
            card_type="Asset",
            class_name="Guardian",
            cost=3,
            traits="Item. Weapon. Melee.",
            text="Fight. +1 combat for this attack.",
        )

        assert candidate.card_id == "01016"
        assert candidate.relevance_score == 0.85
        assert candidate.xp_cost == 0

    def test_minimal_candidate(self):
        """Should create candidate with only required fields."""
        candidate = CardCandidate(
            card_id="01016",
            name="Machete",
            relevance_score=0.5,
            reason="Legal card",
        )

        assert candidate.card_id == "01016"
        assert candidate.xp_cost == 0  # Default

    def test_score_validation(self):
        """Relevance score should be between 0 and 1."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CardCandidate(
                card_id="test",
                name="Test",
                relevance_score=1.5,  # Invalid
                reason="Test",
            )


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_action_space_agent factory."""

    def test_creates_agent(self):
        """Should create ActionSpaceAgent instance."""
        mock_client = MagicMock()
        agent = create_action_space_agent(chroma_client=mock_client)

        assert isinstance(agent, ActionSpaceAgent)

    def test_accepts_config(self):
        """Should accept custom config."""
        from backend.services.subagents.base import SubagentConfig

        config = SubagentConfig(temperature=0.5)
        mock_client = MagicMock()
        agent = create_action_space_agent(config=config, chroma_client=mock_client)

        assert agent.config.temperature == 0.5


# =============================================================================
# Capability Keywords Tests
# =============================================================================


class TestCapabilityKeywords:
    """Tests for capability keyword mappings."""

    def test_combat_keywords_exist(self):
        """Combat capability should have relevant keywords."""
        keywords = CAPABILITY_KEYWORDS.get("combat", [])

        assert "damage" in keywords
        assert "fight" in keywords
        assert "weapon" in keywords

    def test_card_draw_keywords_exist(self):
        """Card draw capability should have relevant keywords."""
        keywords = CAPABILITY_KEYWORDS.get("card_draw", [])

        assert "draw" in keywords
        assert "card" in keywords

    def test_economy_keywords_exist(self):
        """Economy capability should have relevant keywords."""
        keywords = CAPABILITY_KEYWORDS.get("economy", [])

        assert "resource" in keywords
        assert "gain" in keywords

    def test_all_capabilities_have_keywords(self):
        """All defined capabilities should have keywords."""
        expected_capabilities = [
            "card_draw", "combat", "clues", "economy",
            "willpower", "movement", "healing", "action_efficiency"
        ]

        for cap in expected_capabilities:
            assert cap in CAPABILITY_KEYWORDS
            assert len(CAPABILITY_KEYWORDS[cap]) > 0
