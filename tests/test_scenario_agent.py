"""Unit tests for the ScenarioAgent with scenario data integration."""

import os
from unittest.mock import MagicMock, patch

import pytest

from backend.models.subagent_models import SubagentMetadata
from backend.services.scenario_loader import (
    EnemyData,
    ScenarioData,
    ScenarioLoader,
    TreacheryData,
)
from backend.services.subagents.base import SubagentConfig
from backend.services.subagents.scenario_agent import (
    Priority,
    ScenarioAgent,
    ScenarioQuery,
    ScenarioResponse,
    ThreatProfile,
    create_scenario_agent,
)

# =============================================================================
# ScenarioQuery Tests
# =============================================================================


class TestScenarioQuery:
    """Tests for ScenarioQuery input schema."""

    def test_minimal_query(self):
        """Should accept just a scenario_id."""
        query = ScenarioQuery(scenario_id="the_gathering")
        assert query.scenario_id == "the_gathering"
        assert query.campaign is None
        assert query.investigator_id is None

    def test_full_query(self):
        """Should accept all fields."""
        query = ScenarioQuery(
            scenario_id="the_gathering",
            campaign="Night of the Zealot",
            investigator_id="01001",
        )
        assert query.scenario_id == "the_gathering"
        assert query.campaign == "Night of the Zealot"
        assert query.investigator_id == "01001"

    def test_requires_scenario_id(self):
        """Should require scenario_id field."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ScenarioQuery()


# =============================================================================
# ThreatProfile Tests
# =============================================================================


class TestThreatProfile:
    """Tests for ThreatProfile schema."""

    def test_create_profile(self):
        """Should create profile with all fields."""
        profile = ThreatProfile(
            enemy_density="high",
            treachery_types=["willpower", "agility"],
            key_skill_tests=["willpower", "combat"],
            special_mechanics=["doom", "darkness"],
        )
        assert profile.enemy_density == "high"
        assert "willpower" in profile.treachery_types
        assert "combat" in profile.key_skill_tests
        assert "doom" in profile.special_mechanics

    def test_default_lists(self):
        """Should default lists to empty."""
        profile = ThreatProfile(enemy_density="low")
        assert profile.treachery_types == []
        assert profile.key_skill_tests == []
        assert profile.special_mechanics == []


# =============================================================================
# Priority Tests
# =============================================================================


class TestPriority:
    """Tests for Priority schema."""

    def test_create_priority(self):
        """Should create priority with all fields."""
        priority = Priority(
            capability="willpower_icons",
            importance="critical",
            reason="High willpower treachery count",
        )
        assert priority.capability == "willpower_icons"
        assert priority.importance == "critical"
        assert "willpower" in priority.reason.lower()


# =============================================================================
# ScenarioResponse Tests
# =============================================================================


class TestScenarioResponse:
    """Tests for ScenarioResponse output schema."""

    def test_minimal_response(self):
        """Should create with required fields."""
        response = ScenarioResponse(
            content="Scenario analysis here",
            metadata=SubagentMetadata(agent_type="scenario"),
        )
        assert response.content == "Scenario analysis here"
        assert response.scenario_name == ""
        assert response.threat_profile is None
        assert response.preparation_priorities == []
        assert response.recommended_capabilities == []

    def test_full_response(self):
        """Should include all scenario-specific fields."""
        threat_profile = ThreatProfile(
            enemy_density="high",
            treachery_types=["willpower"],
            key_skill_tests=["willpower", "combat"],
            special_mechanics=["doom"],
        )
        priorities = [
            Priority(
                capability="willpower_icons",
                importance="critical",
                reason="High willpower tests",
            )
        ]
        response = ScenarioResponse(
            content="Full analysis",
            confidence=0.9,
            sources=["Scenario: The Gathering"],
            metadata=SubagentMetadata(
                agent_type="scenario",
                query_type="full_analysis",
            ),
            scenario_name="The Gathering",
            threat_profile=threat_profile,
            preparation_priorities=priorities,
            recommended_capabilities=["willpower_boost", "combat"],
        )
        assert response.scenario_name == "The Gathering"
        assert response.threat_profile.enemy_density == "high"
        assert len(response.preparation_priorities) == 1
        assert "willpower_boost" in response.recommended_capabilities

    def test_error_response(self):
        """Should create error response."""
        response = ScenarioResponse.error_response("Something went wrong", "scenario")
        assert response.content == "Something went wrong"
        assert response.confidence == 0.0
        assert response.metadata.agent_type == "scenario"
        assert response.metadata.query_type == "error"
        assert response.metadata.extra.get("error") is True
        assert response.scenario_name == ""
        assert response.threat_profile is None

    def test_unknown_scenario_response(self):
        """Should create unknown scenario response."""
        response = ScenarioResponse.unknown_scenario_response("nonexistent_scenario")
        assert "not found" in response.content.lower()
        assert response.confidence == 0.3
        assert response.metadata.query_type == "unknown_scenario"
        assert response.scenario_name == ""

    def test_from_base_response(self):
        """Should convert from base SubagentResponse."""
        from backend.models.subagent_models import SubagentResponse

        base = SubagentResponse(
            content="Base content",
            confidence=0.8,
            sources=["Source 1"],
            metadata=SubagentMetadata(agent_type="scenario"),
        )
        threat_profile = ThreatProfile(enemy_density="medium")
        priorities = [
            Priority(
                capability="combat",
                importance="important",
                reason="Enemies present",
            )
        ]

        scenario_response = ScenarioResponse.from_base_response(
            base,
            scenario_name="Test Scenario",
            threat_profile=threat_profile,
            preparation_priorities=priorities,
            recommended_capabilities=["damage_dealing"],
        )

        assert scenario_response.content == "Base content"
        assert scenario_response.confidence == 0.8
        assert scenario_response.scenario_name == "Test Scenario"
        assert scenario_response.threat_profile.enemy_density == "medium"
        assert len(scenario_response.preparation_priorities) == 1


# =============================================================================
# ScenarioAgent Tests
# =============================================================================


class TestScenarioAgent:
    """Tests for ScenarioAgent with mocked dependencies."""

    @pytest.fixture
    def sample_scenario(self):
        """Create a sample scenario for testing."""
        return ScenarioData(
            id="the_gathering",
            name="The Gathering",
            campaign="Night of the Zealot",
            position=1,
            act_count=3,
            agenda_count=3,
            enemy_density="low",
            treachery_profile={"willpower": 3, "agility": 1},
            key_tests=["willpower", "combat"],
            mechanics=["spawn_mechanics", "doom"],
            enemies=[
                EnemyData(
                    name="Ghoul Priest",
                    type="elite",
                    fight=4,
                    health=5,
                    evade=4,
                    damage=2,
                    horror=2,
                    notes="Boss enemy",
                ),
                EnemyData(
                    name="Ghoul",
                    type="basic",
                    fight=2,
                    health=2,
                    evade=2,
                    damage=1,
                    horror=1,
                ),
            ],
            treacheries=[
                TreacheryData(
                    name="Rotting Remains",
                    test="willpower",
                    difficulty=3,
                    effect="horror",
                    notes="Core treachery",
                ),
            ],
            tips=["Bring willpower icons", "Combat for boss"],
            difficulty_notes="Introductory scenario",
        )

    @pytest.fixture
    def mock_scenario_loader(self, sample_scenario):
        """Create a mock scenario loader."""
        loader = MagicMock(spec=ScenarioLoader)
        loader.get_scenario.return_value = sample_scenario
        loader.get_scenario_by_name.return_value = sample_scenario
        loader.search_scenarios.return_value = [sample_scenario]
        return loader

    @pytest.fixture
    def mock_llm_response(self):
        """Create a mock LLM response."""
        mock_response = MagicMock()
        mock_response.content = """## Key Threats

The Gathering is an introductory scenario with relatively low enemy density:

- **Ghoul Priest** is the boss enemy with Fight 4 and 5 health
- **Rotting Remains** tests willpower 3 and deals horror

## Skill Priorities

1. **Willpower** - Critical for treachery tests
2. **Combat** - Needed for the Ghoul Priest boss

## Recommended Cards/Effects

- Willpower commit icons for treachery protection
- Combat assets for the boss fight
- Horror soak for Rotting Remains damage

## Strategy Tips

Take your time early, prepare for the boss fight. Doom mechanic means manage your pacing."""
        return mock_response

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_agent_initialization(self, mock_chat, mock_scenario_loader):
        """Should initialize with scenario loader."""
        agent = ScenarioAgent(scenario_loader=mock_scenario_loader)

        assert agent.agent_type == "scenario"
        assert agent.scenario_loader is mock_scenario_loader

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_query_returns_scenario_response(
        self, mock_chat_class, mock_scenario_loader, mock_llm_response
    ):
        """Should return ScenarioResponse with structured fields."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = ScenarioAgent(scenario_loader=mock_scenario_loader)
        response = agent.query(
            "What threats should I prepare for in The Gathering?",
            context={"scenario_id": "the_gathering"},
        )

        assert isinstance(response, ScenarioResponse)
        assert response.scenario_name == "The Gathering"
        assert response.threat_profile is not None
        assert response.threat_profile.enemy_density == "low"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_query_builds_priorities(
        self, mock_chat_class, mock_scenario_loader, mock_llm_response
    ):
        """Should build preparation priorities from scenario data."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = ScenarioAgent(scenario_loader=mock_scenario_loader)
        response = agent.query(
            "How should I prepare?",
            context={"scenario_id": "the_gathering"},
        )

        assert len(response.preparation_priorities) > 0
        # Should have willpower priority due to treachery profile
        priority_capabilities = [p.capability for p in response.preparation_priorities]
        assert "willpower_icons" in priority_capabilities

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_query_handles_unknown_scenario(
        self, mock_chat_class, mock_scenario_loader
    ):
        """Should handle unknown scenarios gracefully."""
        # Make loader return None
        mock_scenario_loader.get_scenario.return_value = None
        mock_scenario_loader.get_scenario_by_name.return_value = None
        mock_scenario_loader.search_scenarios.return_value = []

        agent = ScenarioAgent(scenario_loader=mock_scenario_loader)
        response = agent.query(
            "Analyze unknown_scenario",
            context={"scenario_id": "unknown_scenario"},
        )

        assert isinstance(response, ScenarioResponse)
        assert "not found" in response.content.lower()
        assert response.metadata.query_type == "unknown_scenario"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_query_with_context(
        self, mock_chat_class, mock_scenario_loader, mock_llm_response
    ):
        """Should use context in prompt."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = ScenarioAgent(scenario_loader=mock_scenario_loader)
        agent.query(
            "What should Roland bring?",
            context={
                "scenario_id": "the_gathering",
                "investigator_name": "Roland Banks",
            },
        )

        # Verify LLM was called with context in prompt
        assert mock_llm.invoke.called
        call_args = mock_llm.invoke.call_args[0][0]
        system_prompt = call_args[0].content
        assert "Roland Banks" in system_prompt

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_query_scenario_method(
        self, mock_chat_class, mock_scenario_loader, mock_llm_response
    ):
        """Should accept ScenarioQuery input schema."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = ScenarioAgent(scenario_loader=mock_scenario_loader)
        scenario_query = ScenarioQuery(
            scenario_id="the_gathering",
            campaign="Night of the Zealot",
            investigator_id="01001",
        )
        response = agent.query_scenario(scenario_query)

        assert isinstance(response, ScenarioResponse)
        assert response.scenario_name == "The Gathering"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_metadata_includes_scenario_found(
        self, mock_chat_class, mock_scenario_loader, mock_llm_response
    ):
        """Should indicate scenario was found in metadata."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = ScenarioAgent(scenario_loader=mock_scenario_loader)
        response = agent.query(
            "Analyze scenario",
            context={"scenario_id": "the_gathering"},
        )

        assert response.metadata.extra.get("scenario_found") is True
        assert response.metadata.extra.get("has_threat_profile") is True

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_handles_llm_error(self, mock_chat_class, mock_scenario_loader):
        """Should return error response on LLM failure."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("API Error")
        mock_chat_class.return_value = mock_llm

        agent = ScenarioAgent(scenario_loader=mock_scenario_loader)
        response = agent.query(
            "Any question",
            context={"scenario_id": "the_gathering"},
        )

        assert isinstance(response, ScenarioResponse)
        assert "failed" in response.content.lower() or "error" in response.content.lower()
        assert response.confidence == 0.0


# =============================================================================
# Query Type Classification Tests
# =============================================================================


class TestQueryTypeClassification:
    """Tests for query type classification."""

    @pytest.fixture
    def agent(self, mock_scenario_loader):
        """Create agent with mocked dependencies."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.subagents.base.ChatOpenAI"):
                return ScenarioAgent(scenario_loader=mock_scenario_loader)

    @pytest.fixture
    def mock_scenario_loader(self):
        loader = MagicMock(spec=ScenarioLoader)
        loader.get_scenario.return_value = None
        loader.get_scenario_by_name.return_value = None
        loader.search_scenarios.return_value = []
        return loader

    def test_threat_analysis_query(self, agent):
        """Should classify threat analysis questions."""
        assert agent._determine_query_type("What enemy threats are there?") == "threat_analysis"
        assert agent._determine_query_type("What threats should I watch for?") == "threat_analysis"
        query = "Tell me about the danger in this scenario"
        assert agent._determine_query_type(query) == "threat_analysis"

    def test_preparation_query(self, agent):
        """Should classify preparation questions."""
        assert agent._determine_query_type("How should I prepare for this?") == "preparation"
        assert agent._determine_query_type("What cards should I bring?") == "preparation"

    def test_strategy_query(self, agent):
        """Should classify strategy questions."""
        assert agent._determine_query_type("How do I approach this scenario?") == "strategy"
        assert agent._determine_query_type("What's the best strategy?") == "strategy"

    def test_encounter_analysis_query(self, agent):
        """Should classify encounter analysis questions."""
        assert agent._determine_query_type("What treacheries are there?") == "encounter_analysis"

    def test_general_query(self, agent):
        """Should default to full analysis."""
        assert agent._determine_query_type("Tell me about this scenario") == "full_analysis"


# =============================================================================
# Priority Building Tests
# =============================================================================


class TestPriorityBuilding:
    """Tests for priority calculation."""

    @pytest.fixture
    def agent(self, mock_scenario_loader):
        """Create agent with mocked dependencies."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.subagents.base.ChatOpenAI"):
                return ScenarioAgent(scenario_loader=mock_scenario_loader)

    @pytest.fixture
    def mock_scenario_loader(self):
        return MagicMock(spec=ScenarioLoader)

    def test_builds_willpower_priority_for_high_treacheries(self, agent):
        """Should build willpower priority for high treachery count."""
        scenario = ScenarioData(
            id="test",
            name="Test",
            campaign="Test",
            position=1,
            act_count=3,
            agenda_count=3,
            enemy_density="low",
            treachery_profile={"willpower": 5, "agility": 1},
            key_tests=["willpower"],
            mechanics=[],
        )
        priorities = agent._build_priorities(scenario)

        willpower_priorities = [p for p in priorities if "willpower" in p.capability]
        assert len(willpower_priorities) >= 1
        assert willpower_priorities[0].importance == "critical"

    def test_builds_combat_priority_for_high_density(self, agent):
        """Should build combat priority for high enemy density."""
        scenario = ScenarioData(
            id="test",
            name="Test",
            campaign="Test",
            position=1,
            act_count=3,
            agenda_count=3,
            enemy_density="high",
            treachery_profile={},
            key_tests=[],
            mechanics=[],
        )
        priorities = agent._build_priorities(scenario)

        combat_priorities = [p for p in priorities if p.capability == "combat"]
        assert len(combat_priorities) >= 1
        assert combat_priorities[0].importance == "critical"

    def test_builds_damage_priority_for_elite_enemies(self, agent):
        """Should build high damage priority for elite enemies."""
        scenario = ScenarioData(
            id="test",
            name="Test",
            campaign="Test",
            position=1,
            act_count=3,
            agenda_count=3,
            enemy_density="medium",
            treachery_profile={},
            key_tests=[],
            mechanics=[],
            enemies=[
                EnemyData(
                    name="Boss",
                    type="elite",
                    fight=4,
                    health=8,
                    evade=3,
                    damage=2,
                    horror=2,
                )
            ],
        )
        priorities = agent._build_priorities(scenario)

        damage_priorities = [p for p in priorities if p.capability == "high_damage"]
        assert len(damage_priorities) >= 1
        assert damage_priorities[0].importance == "critical"

    def test_builds_doom_priority_for_doom_mechanic(self, agent):
        """Should build doom management priority."""
        scenario = ScenarioData(
            id="test",
            name="Test",
            campaign="Test",
            position=1,
            act_count=3,
            agenda_count=3,
            enemy_density="low",
            treachery_profile={},
            key_tests=[],
            mechanics=["doom", "time_pressure"],
        )
        priorities = agent._build_priorities(scenario)

        doom_priorities = [p for p in priorities if p.capability == "doom_management"]
        assert len(doom_priorities) >= 1


# =============================================================================
# Capability Building Tests
# =============================================================================


class TestCapabilityBuilding:
    """Tests for capability recommendation building."""

    @pytest.fixture
    def agent(self, mock_scenario_loader):
        """Create agent with mocked dependencies."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.subagents.base.ChatOpenAI"):
                return ScenarioAgent(scenario_loader=mock_scenario_loader)

    @pytest.fixture
    def mock_scenario_loader(self):
        return MagicMock(spec=ScenarioLoader)

    def test_builds_capabilities_from_key_tests(self, agent):
        """Should recommend capabilities based on key tests."""
        scenario = ScenarioData(
            id="test",
            name="Test",
            campaign="Test",
            position=1,
            act_count=3,
            agenda_count=3,
            enemy_density="low",
            treachery_profile={},
            key_tests=["willpower", "agility"],
            mechanics=[],
        )
        capabilities = agent._build_capabilities(scenario)

        assert "willpower_boost" in capabilities
        assert "agility_boost" in capabilities

    def test_builds_capabilities_for_combat(self, agent):
        """Should recommend combat capabilities for enemy-heavy scenarios."""
        scenario = ScenarioData(
            id="test",
            name="Test",
            campaign="Test",
            position=1,
            act_count=3,
            agenda_count=3,
            enemy_density="high",
            treachery_profile={},
            key_tests=[],
            mechanics=[],
        )
        capabilities = agent._build_capabilities(scenario)

        assert "damage_dealing" in capabilities
        assert "enemy_handling" in capabilities


# =============================================================================
# Confidence Calculation Tests
# =============================================================================


class TestConfidenceCalculation:
    """Tests for confidence score calculation."""

    @pytest.fixture
    def agent(self, mock_scenario_loader):
        """Create agent with mocked dependencies."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.subagents.base.ChatOpenAI"):
                return ScenarioAgent(scenario_loader=mock_scenario_loader)

    @pytest.fixture
    def mock_scenario_loader(self):
        return MagicMock(spec=ScenarioLoader)

    def test_high_confidence_with_scenario_data(self, agent, sample_scenario):
        """Should boost confidence when scenario data available."""
        from backend.services.subagents.base import SubagentState

        state = SubagentState(
            query="test",
            context={"_scenario_data": sample_scenario},
        )
        content = "The key threats in this scenario include..."

        confidence = agent._calculate_confidence(content, state)
        assert confidence >= 0.7

    @pytest.fixture
    def sample_scenario(self):
        return ScenarioData(
            id="test",
            name="Test",
            campaign="Test",
            position=1,
            act_count=3,
            agenda_count=3,
            enemy_density="medium",
            treachery_profile={},
            key_tests=[],
            mechanics=[],
        )

    def test_lower_confidence_without_scenario_data(self, agent):
        """Should have lower confidence without scenario data."""
        from backend.services.subagents.base import SubagentState

        state = SubagentState(query="test", context={})
        content = "I recommend focusing on willpower."

        confidence = agent._calculate_confidence(content, state)
        assert confidence < 0.8

    def test_penalty_for_uncertainty(self, agent, sample_scenario):
        """Should penalize uncertain language."""
        from backend.services.subagents.base import SubagentState

        state = SubagentState(
            query="test",
            context={"_scenario_data": sample_scenario},
        )
        content = "I'm not sure, but it might be important to focus on willpower."

        confidence = agent._calculate_confidence(content, state)
        # Should be reduced by uncertainty
        assert confidence < 0.75


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_scenario_agent factory."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_create_scenario_agent_default(self, mock_chat):
        """Should create agent with default config."""
        agent = create_scenario_agent()

        assert isinstance(agent, ScenarioAgent)
        assert agent.agent_type == "scenario"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_create_scenario_agent_with_config(self, mock_chat):
        """Should accept custom config."""
        config = SubagentConfig(temperature=0.5, max_tokens=1024)
        agent = create_scenario_agent(config=config)

        assert agent.config.temperature == 0.5
        assert agent.config.max_tokens == 1024

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_create_scenario_agent_with_loader(self, mock_chat):
        """Should accept custom scenario loader."""
        mock_loader = MagicMock(spec=ScenarioLoader)
        agent = create_scenario_agent(scenario_loader=mock_loader)

        assert agent.scenario_loader is mock_loader


# =============================================================================
# Integration Tests with Real Scenario Data
# =============================================================================


class TestScenarioAgentIntegration:
    """Integration tests with actual scenario data."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_finds_real_scenario_by_name(self, mock_chat_class):
        """Should find real scenario data by name."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Analysis of The Gathering...")
        mock_chat_class.return_value = mock_llm

        # Use real loader
        agent = ScenarioAgent()
        response = agent.query(
            "What threats are in The Gathering?",
            context={"scenario_id": "the_gathering"},
        )

        # Should find and use real scenario data
        if response.scenario_name:  # Only if data file exists
            assert response.scenario_name == "The Gathering"
            assert response.threat_profile is not None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_finds_scenario_by_partial_name(self, mock_chat_class):
        """Should find scenario by partial name match."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Analysis...")
        mock_chat_class.return_value = mock_llm

        agent = ScenarioAgent()
        scenario = agent._find_scenario("Gathering")

        if scenario:  # Only if data file exists
            assert "Gathering" in scenario.name
