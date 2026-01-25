"""Unit tests for prompts module."""

import pytest
from pydantic import ValidationError

from backend.services.prompts import (
    # Prompt templates
    ORCHESTRATOR_SYSTEM_PROMPT,
    RULES_AGENT_PROMPT,
    STATE_AGENT_PROMPT,
    ACTION_SPACE_AGENT_PROMPT,
    SCENARIO_AGENT_PROMPT,
    # Formatting functions
    build_context_block,
    format_orchestrator_prompt,
    format_subagent_prompt,
    # Pydantic schemas
    RulesQueryInput,
    StateAnalysisInput,
    CardSearchInput,
    ScenarioAnalysisInput,
    # LangGraph tools
    consult_rules_agent,
    consult_state_agent,
    consult_action_space_agent,
    consult_scenario_agent,
    # Registries
    SUBAGENT_TOOLS,
    AGENT_TOOL_MAP,
    AGENT_TYPES,
)


# ============================================================================
# Prompt Template Tests
# ============================================================================


class TestPromptTemplates:
    """Tests for raw prompt templates."""

    def test_orchestrator_prompt_has_placeholders(self):
        """Orchestrator prompt should have required placeholders."""
        assert "{context_block}" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "{additional_instructions}" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_orchestrator_prompt_mentions_subagents(self):
        """Orchestrator prompt should mention all subagents."""
        assert "RulesAgent" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "StateAgent" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "ActionSpaceAgent" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "ScenarioAgent" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_subagent_prompts_have_context_placeholder(self):
        """All subagent prompts should have context_block placeholder."""
        assert "{context_block}" in RULES_AGENT_PROMPT
        assert "{context_block}" in STATE_AGENT_PROMPT
        assert "{context_block}" in ACTION_SPACE_AGENT_PROMPT
        assert "{context_block}" in SCENARIO_AGENT_PROMPT

    def test_rules_agent_prompt_covers_key_topics(self):
        """Rules agent prompt should cover key deckbuilding rules."""
        assert "deckbuilding" in RULES_AGENT_PROMPT.lower()
        assert "legality" in RULES_AGENT_PROMPT.lower()
        assert "restriction" in RULES_AGENT_PROMPT.lower()

    def test_state_agent_prompt_covers_analysis_areas(self):
        """State agent prompt should cover deck analysis areas."""
        assert "curve" in STATE_AGENT_PROMPT.lower()
        assert "gap" in STATE_AGENT_PROMPT.lower()
        assert "composition" in STATE_AGENT_PROMPT.lower()

    def test_action_space_agent_prompt_covers_search(self):
        """Action space agent prompt should cover card search."""
        assert "search" in ACTION_SPACE_AGENT_PROMPT.lower()
        assert "filter" in ACTION_SPACE_AGENT_PROMPT.lower()

    def test_scenario_agent_prompt_covers_threats(self):
        """Scenario agent prompt should cover scenario threats."""
        assert "threat" in SCENARIO_AGENT_PROMPT.lower()
        assert "preparation" in SCENARIO_AGENT_PROMPT.lower()


# ============================================================================
# Context Block Builder Tests
# ============================================================================


class TestBuildContextBlock:
    """Tests for build_context_block function."""

    def test_empty_context_returns_default(self):
        """Should return default message when no context provided."""
        result = build_context_block()
        assert "No specific context" in result

    def test_includes_investigator_name(self):
        """Should include investigator name when provided."""
        result = build_context_block(investigator_name="Roland Banks")
        assert "Roland Banks" in result
        assert "Investigator" in result

    def test_includes_deck_id(self):
        """Should include deck ID when provided."""
        result = build_context_block(deck_id="deck_123")
        assert "deck_123" in result
        assert "Deck ID" in result

    def test_includes_deck_summary(self):
        """Should include deck summary info when provided."""
        summary = {
            "deck_name": "Roland's Starter",
            "total_cards": 30,
            "archetype": "combat",
        }
        result = build_context_block(deck_summary=summary)
        assert "Roland's Starter" in result
        assert "30" in result
        assert "combat" in result

    def test_includes_scenario_name(self):
        """Should include scenario name when provided."""
        result = build_context_block(scenario_name="The Gathering")
        assert "The Gathering" in result
        assert "Scenario" in result

    def test_includes_upgrade_xp(self):
        """Should include XP when provided."""
        result = build_context_block(upgrade_xp=5)
        assert "5" in result
        assert "XP" in result

    def test_includes_campaign_name(self):
        """Should include campaign name when provided."""
        result = build_context_block(campaign_name="Night of the Zealot")
        assert "Night of the Zealot" in result
        assert "Campaign" in result

    def test_includes_owned_sets(self):
        """Should include owned sets when provided."""
        result = build_context_block(owned_sets=["Core Set", "Dunwich Legacy"])
        assert "Core Set" in result
        assert "Dunwich Legacy" in result

    def test_combines_multiple_fields(self):
        """Should combine all provided fields."""
        result = build_context_block(
            investigator_name="Daisy Walker",
            scenario_name="The House Always Wins",
            upgrade_xp=10,
        )
        assert "Daisy Walker" in result
        assert "The House Always Wins" in result
        assert "10" in result


# ============================================================================
# Orchestrator Prompt Formatting Tests
# ============================================================================


class TestFormatOrchestratorPrompt:
    """Tests for format_orchestrator_prompt function."""

    def test_returns_formatted_string(self):
        """Should return a formatted string."""
        result = format_orchestrator_prompt()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_injects_context(self):
        """Should inject context into prompt."""
        result = format_orchestrator_prompt(
            investigator_name="Jenny Barnes",
            upgrade_xp=8,
        )
        assert "Jenny Barnes" in result
        assert "8" in result

    def test_includes_additional_instructions(self):
        """Should include additional instructions when provided."""
        result = format_orchestrator_prompt(
            additional_instructions="Focus on economy cards."
        )
        assert "Focus on economy cards" in result

    def test_no_unfilled_placeholders(self):
        """Should not have unfilled placeholders."""
        result = format_orchestrator_prompt()
        assert "{context_block}" not in result
        assert "{additional_instructions}" not in result


# ============================================================================
# Subagent Prompt Formatting Tests
# ============================================================================


class TestFormatSubagentPrompt:
    """Tests for format_subagent_prompt function."""

    def test_formats_rules_agent(self):
        """Should format rules agent prompt."""
        result = format_subagent_prompt("rules")
        assert "Rules Agent" in result
        assert isinstance(result, str)

    def test_formats_state_agent(self):
        """Should format state agent prompt."""
        result = format_subagent_prompt("state")
        assert "State Agent" in result

    def test_formats_action_space_agent(self):
        """Should format action space agent prompt."""
        result = format_subagent_prompt("action_space")
        assert "Action Space Agent" in result

    def test_formats_scenario_agent(self):
        """Should format scenario agent prompt."""
        result = format_subagent_prompt("scenario")
        assert "Scenario Agent" in result

    def test_injects_context(self):
        """Should inject context into subagent prompts."""
        result = format_subagent_prompt(
            "rules",
            investigator_name="Skids O'Toole",
            deck_id="deck_456",
        )
        assert "Skids O'Toole" in result
        assert "deck_456" in result

    def test_raises_for_unknown_agent(self):
        """Should raise ValueError for unknown agent type."""
        with pytest.raises(ValueError) as exc_info:
            format_subagent_prompt("unknown_agent")
        assert "unknown_agent" in str(exc_info.value)
        assert "Must be one of" in str(exc_info.value)

    def test_no_unfilled_placeholders(self):
        """Should not have unfilled placeholders."""
        for agent_type in AGENT_TYPES:
            result = format_subagent_prompt(agent_type)
            assert "{context_block}" not in result


# ============================================================================
# Pydantic Schema Tests
# ============================================================================


class TestRulesQueryInput:
    """Tests for RulesQueryInput schema."""

    def test_accepts_valid_question(self):
        """Should accept valid question."""
        schema = RulesQueryInput(question="Can Roland include Shrivelling?")
        assert schema.question == "Can Roland include Shrivelling?"

    def test_accepts_optional_investigator(self):
        """Should accept optional investigator name."""
        schema = RulesQueryInput(
            question="Is this card legal?",
            investigator_name="Agnes Baker"
        )
        assert schema.investigator_name == "Agnes Baker"

    def test_investigator_defaults_to_none(self):
        """Investigator should default to None."""
        schema = RulesQueryInput(question="Test question")
        assert schema.investigator_name is None

    def test_requires_question(self):
        """Should require question field."""
        with pytest.raises(ValidationError):
            RulesQueryInput()


class TestStateAnalysisInput:
    """Tests for StateAnalysisInput schema."""

    def test_accepts_valid_analysis_types(self):
        """Should accept all valid analysis types."""
        for analysis_type in ["full", "curve", "gaps", "redundancy"]:
            schema = StateAnalysisInput(analysis_type=analysis_type)
            assert schema.analysis_type == analysis_type

    def test_defaults_to_full_analysis(self):
        """Should default to full analysis."""
        schema = StateAnalysisInput()
        assert schema.analysis_type == "full"

    def test_rejects_invalid_analysis_type(self):
        """Should reject invalid analysis type."""
        with pytest.raises(ValidationError):
            StateAnalysisInput(analysis_type="invalid")

    def test_accepts_optional_fields(self):
        """Should accept optional fields."""
        schema = StateAnalysisInput(
            deck_id="deck_789",
            focus_area="combat"
        )
        assert schema.deck_id == "deck_789"
        assert schema.focus_area == "combat"


class TestCardSearchInput:
    """Tests for CardSearchInput schema."""

    def test_accepts_valid_search(self):
        """Should accept valid search query."""
        schema = CardSearchInput(search_query="damage dealing events")
        assert schema.search_query == "damage dealing events"

    def test_requires_search_query(self):
        """Should require search query."""
        with pytest.raises(ValidationError):
            CardSearchInput()

    def test_accepts_max_level(self):
        """Should accept max level filter."""
        schema = CardSearchInput(search_query="test", max_level=3)
        assert schema.max_level == 3

    def test_validates_max_level_bounds(self):
        """Should validate max level is 0-5."""
        with pytest.raises(ValidationError):
            CardSearchInput(search_query="test", max_level=-1)
        with pytest.raises(ValidationError):
            CardSearchInput(search_query="test", max_level=6)

    def test_accepts_card_type_filter(self):
        """Should accept card type filter."""
        for card_type in ["asset", "event", "skill"]:
            schema = CardSearchInput(search_query="test", card_type=card_type)
            assert schema.card_type == card_type

    def test_rejects_invalid_card_type(self):
        """Should reject invalid card type."""
        with pytest.raises(ValidationError):
            CardSearchInput(search_query="test", card_type="investigator")

    def test_owned_only_defaults_true(self):
        """Should default to owned only."""
        schema = CardSearchInput(search_query="test")
        assert schema.owned_only is True


class TestScenarioAnalysisInput:
    """Tests for ScenarioAnalysisInput schema."""

    def test_requires_scenario_name(self):
        """Should require scenario name."""
        with pytest.raises(ValidationError):
            ScenarioAnalysisInput()

    def test_accepts_valid_scenario(self):
        """Should accept valid scenario name."""
        schema = ScenarioAnalysisInput(scenario_name="The Gathering")
        assert schema.scenario_name == "The Gathering"

    def test_accepts_valid_focus_types(self):
        """Should accept all valid focus types."""
        for focus in ["threats", "preparation", "strategy", "full"]:
            schema = ScenarioAnalysisInput(
                scenario_name="Test",
                analysis_focus=focus
            )
            assert schema.analysis_focus == focus

    def test_defaults_to_full_focus(self):
        """Should default to full focus."""
        schema = ScenarioAnalysisInput(scenario_name="Test")
        assert schema.analysis_focus == "full"

    def test_validates_player_count_bounds(self):
        """Should validate player count is 1-4."""
        with pytest.raises(ValidationError):
            ScenarioAnalysisInput(scenario_name="Test", player_count=0)
        with pytest.raises(ValidationError):
            ScenarioAnalysisInput(scenario_name="Test", player_count=5)

    def test_player_count_defaults_to_one(self):
        """Should default to 1 player."""
        schema = ScenarioAnalysisInput(scenario_name="Test")
        assert schema.player_count == 1


# ============================================================================
# LangGraph Tool Tests
# ============================================================================


class TestConsultRulesAgent:
    """Tests for consult_rules_agent tool."""

    def test_tool_has_correct_name(self):
        """Should have correct tool name."""
        assert consult_rules_agent.name == "consult_rules_agent"

    def test_tool_has_description(self):
        """Should have description for LLM."""
        assert consult_rules_agent.description
        assert "rules" in consult_rules_agent.description.lower()

    def test_returns_placeholder_response(self):
        """Should return placeholder response (stub implementation)."""
        result = consult_rules_agent.invoke({
            "question": "Can Roland include Shrivelling?"
        })
        assert "Rules Agent" in result
        assert "Shrivelling" in result

    def test_includes_investigator_in_response(self):
        """Should include investigator in response when provided."""
        result = consult_rules_agent.invoke({
            "question": "Is this legal?",
            "investigator_name": "Agnes Baker"
        })
        assert "Agnes Baker" in result


class TestConsultStateAgent:
    """Tests for consult_state_agent tool."""

    def test_tool_has_correct_name(self):
        """Should have correct tool name."""
        assert consult_state_agent.name == "consult_state_agent"

    def test_tool_has_description(self):
        """Should have description for LLM."""
        assert consult_state_agent.description
        assert "analysis" in consult_state_agent.description.lower()

    def test_returns_placeholder_response(self):
        """Should return placeholder response."""
        result = consult_state_agent.invoke({
            "analysis_type": "curve"
        })
        assert "State Agent" in result
        assert "curve" in result


class TestConsultActionSpaceAgent:
    """Tests for consult_action_space_agent tool."""

    def test_tool_has_correct_name(self):
        """Should have correct tool name."""
        assert consult_action_space_agent.name == "consult_action_space_agent"

    def test_tool_has_description(self):
        """Should have description for LLM."""
        assert consult_action_space_agent.description
        assert "search" in consult_action_space_agent.description.lower()

    def test_returns_placeholder_response(self):
        """Should return placeholder response."""
        result = consult_action_space_agent.invoke({
            "search_query": "damage dealing events"
        })
        assert "Action Space Agent" in result
        assert "damage dealing events" in result

    def test_includes_filters_in_response(self):
        """Should include filters in response."""
        result = consult_action_space_agent.invoke({
            "search_query": "weapons",
            "max_level": 2,
            "card_type": "asset",
            "class_filter": "Guardian",
        })
        assert "level 0-2" in result
        assert "asset" in result
        assert "Guardian" in result


class TestConsultScenarioAgent:
    """Tests for consult_scenario_agent tool."""

    def test_tool_has_correct_name(self):
        """Should have correct tool name."""
        assert consult_scenario_agent.name == "consult_scenario_agent"

    def test_tool_has_description(self):
        """Should have description for LLM."""
        assert consult_scenario_agent.description
        assert "scenario" in consult_scenario_agent.description.lower()

    def test_returns_placeholder_response(self):
        """Should return placeholder response."""
        result = consult_scenario_agent.invoke({
            "scenario_name": "The Gathering"
        })
        assert "Scenario Agent" in result
        assert "The Gathering" in result

    def test_includes_focus_and_players(self):
        """Should include focus and player count in response."""
        result = consult_scenario_agent.invoke({
            "scenario_name": "Blood on the Altar",
            "analysis_focus": "threats",
            "player_count": 3,
        })
        assert "threats" in result
        assert "3" in result


# ============================================================================
# Tool Registry Tests
# ============================================================================


class TestToolRegistries:
    """Tests for tool registry exports."""

    def test_subagent_tools_contains_all_tools(self):
        """Should contain all 4 subagent tools."""
        assert len(SUBAGENT_TOOLS) == 4
        tool_names = [t.name for t in SUBAGENT_TOOLS]
        assert "consult_rules_agent" in tool_names
        assert "consult_state_agent" in tool_names
        assert "consult_action_space_agent" in tool_names
        assert "consult_scenario_agent" in tool_names

    def test_agent_tool_map_has_all_agents(self):
        """Should map all agent types to tools."""
        assert len(AGENT_TOOL_MAP) == 4
        assert "rules" in AGENT_TOOL_MAP
        assert "state" in AGENT_TOOL_MAP
        assert "action_space" in AGENT_TOOL_MAP
        assert "scenario" in AGENT_TOOL_MAP

    def test_agent_types_list(self):
        """Should list all agent types."""
        assert len(AGENT_TYPES) == 4
        assert "rules" in AGENT_TYPES
        assert "state" in AGENT_TYPES
        assert "action_space" in AGENT_TYPES
        assert "scenario" in AGENT_TYPES

    def test_all_tools_are_langchain_tools(self):
        """All tools should be valid LangChain tools."""
        from langchain_core.tools import BaseTool

        for tool in SUBAGENT_TOOLS:
            assert isinstance(tool, BaseTool)

    def test_tool_map_values_match_tools_list(self):
        """Tool map values should be the same tools as in the list."""
        for agent_type, tool in AGENT_TOOL_MAP.items():
            assert tool in SUBAGENT_TOOLS
