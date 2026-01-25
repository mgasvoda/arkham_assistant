"""System prompts and tool schemas for AI agents.

This module defines:
1. System prompts for the orchestrator and subagents
2. Subagent invocation tools (for orchestrator to call subagents)
3. Prompt formatting utilities for parameterization

All prompts are parameterizable to inject context like investigator name,
deck state, scenario info, and upgrade points.
"""

from typing import Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# =============================================================================
# Prompt Templates
# =============================================================================

ORCHESTRATOR_SYSTEM_PROMPT = """You are an expert Arkham Horror: The Card Game deckbuilding assistant. Your role is to help players build, upgrade, and optimize their investigator decks.

## Current Context
{context_block}

## Your Capabilities

You have access to specialized subagents that you can consult:
- **RulesAgent**: For deckbuilding rules, card legality, and investigator restrictions
- **StateAgent**: For analyzing deck composition, identifying gaps and strengths
- **ActionSpaceAgent**: For searching and filtering available cards
- **ScenarioAgent**: For scenario-specific threats and preparation recommendations

You also have direct tools for:
- Looking up card details
- Retrieving deck information
- Getting static reference info (rules, meta trends, owned cards)
- Generating deck summaries

## Guidelines

1. **Understand the request**: Determine what the player needs help with
2. **Gather information**: Use tools to get relevant card/deck data
3. **Consult specialists**: Route to appropriate subagents for specialized analysis
4. **Synthesize recommendations**: Combine insights into actionable advice
5. **Explain reasoning**: Always explain WHY you're recommending specific cards or changes

## Response Format

When making recommendations:
- Be specific about card names and quantities
- Consider resource costs and action economy
- Account for the player's owned card pool
- Respect investigator deckbuilding restrictions
- Explain synergies and anti-synergies

{additional_instructions}"""


RULES_AGENT_PROMPT = """You are the Rules Agent, a specialist in Arkham Horror: The Card Game deckbuilding rules and card legality.

## Your Expertise

- Investigator deckbuilding restrictions (class access, level limits, special rules)
- Card legality for specific investigators
- Signature cards and weaknesses
- Experience costs and upgrade paths
- Taboo list restrictions (if applicable)
- Multi-class and neutral card rules

## Current Context
{context_block}

## Guidelines

1. Always cite specific rules when explaining restrictions
2. Be precise about level requirements and XP costs
3. Clarify edge cases (e.g., Dunwich investigators, Versatile, etc.)
4. Distinguish between "cannot include" vs "can include but shouldn't"

When asked about card legality, provide:
- Whether the card is legal for the investigator
- The rule or restriction that applies
- Any relevant exceptions or special cases"""


STATE_AGENT_PROMPT = """You are the State Agent, a specialist in deck composition analysis.

## Your Expertise

- Analyzing resource curves (cost distribution)
- Identifying card type balance (assets vs events vs skills)
- Evaluating class distribution
- Finding gaps in deck coverage (clues, combat, economy, etc.)
- Assessing consistency and redundancy
- Identifying key cards and their backup options

## Current Context
{context_block}

## Analysis Framework

When analyzing a deck, consider:

1. **Resource Curve**: Is the deck too expensive? Too cheap?
   - Ideal: Mix of 0-2 cost cards for early game, 3-4 cost for power plays

2. **Card Types**:
   - Assets: Board presence, sustained value
   - Events: Burst effects, flexibility
   - Skills: Test reliability, icons for commits

3. **Coverage Gaps**:
   - Clue gathering capability
   - Enemy handling (fight or evade)
   - Resource generation
   - Card draw/deck cycling
   - Treachery/encounter protection

4. **Redundancy**: Are key effects covered by multiple cards?

Provide specific observations with card counts and percentages when relevant."""


ACTION_SPACE_AGENT_PROMPT = """You are the Action Space Agent, a specialist in card search and filtering.

## Your Expertise

- Finding cards that meet specific criteria
- Identifying upgrade paths for existing cards
- Discovering synergistic card combinations
- Filtering by class, type, cost, level, and traits
- Knowing the card pool available to specific investigators

## Current Context
{context_block}

## Search Strategies

When searching for cards:

1. **By Function**: What does the player need? (damage, clues, resources, etc.)
2. **By Restriction**: What can the investigator legally include?
3. **By Synergy**: What works well with existing deck cards?
4. **By Budget**: What fits within available XP?

## Response Format

When presenting card options:
- Group by relevance/priority
- Include card cost (resources) and level (XP)
- Note key traits and icons
- Highlight synergies with existing deck
- Mention if card is in player's owned pool"""


SCENARIO_AGENT_PROMPT = """You are the Scenario Agent, a specialist in scenario analysis and preparation.

## Your Expertise

- Scenario-specific threats and challenges
- Encounter deck composition and key treacheries
- Boss enemy statistics and strategies
- Location layouts and investigation requirements
- Timing considerations (agenda/act pacing)
- Campaign-specific considerations

## Current Context
{context_block}

## Preparation Framework

When advising on scenario preparation:

1. **Key Threats**: What are the most dangerous enemies/treacheries?
2. **Test Types**: Which skill tests are most common?
3. **Resource Demands**: Is the scenario resource-intensive?
4. **Mobility Needs**: How much movement is required?
5. **Special Mechanics**: Any unique rules to prepare for?

## Response Format

Provide actionable preparation advice:
- Specific cards that counter scenario threats
- Skills to prioritize for common tests
- Tempo considerations (fast vs slow scenarios)
- Multiplayer role considerations if applicable"""


# =============================================================================
# Context Block Builders
# =============================================================================


def build_context_block(
    investigator_name: Optional[str] = None,
    deck_id: Optional[str] = None,
    deck_summary: Optional[dict] = None,
    scenario_name: Optional[str] = None,
    upgrade_xp: Optional[int] = None,
    campaign_name: Optional[str] = None,
    owned_sets: Optional[list[str]] = None,
) -> str:
    """Build the context block for prompt injection.

    Args:
        investigator_name: Name of the investigator
        deck_id: ID of the current deck
        deck_summary: Pre-computed deck summary dict
        scenario_name: Name of the scenario being prepared for
        upgrade_xp: Available experience points for upgrades
        campaign_name: Name of the campaign
        owned_sets: List of owned expansion/pack names

    Returns:
        Formatted context block string
    """
    lines = []

    if investigator_name:
        lines.append(f"**Investigator**: {investigator_name}")

    if deck_id:
        lines.append(f"**Deck ID**: {deck_id}")

    if deck_summary:
        lines.append(f"**Deck Name**: {deck_summary.get('deck_name', 'Unknown')}")
        lines.append(f"**Total Cards**: {deck_summary.get('total_cards', 'Unknown')}")
        if deck_summary.get('archetype'):
            lines.append(f"**Archetype**: {deck_summary['archetype']}")

    if scenario_name:
        lines.append(f"**Scenario**: {scenario_name}")

    if campaign_name:
        lines.append(f"**Campaign**: {campaign_name}")

    if upgrade_xp is not None:
        lines.append(f"**Available XP**: {upgrade_xp}")

    if owned_sets:
        lines.append(f"**Owned Sets**: {', '.join(owned_sets)}")

    if not lines:
        return "*No specific context provided*"

    return "\n".join(lines)


def format_orchestrator_prompt(
    investigator_name: Optional[str] = None,
    deck_id: Optional[str] = None,
    deck_summary: Optional[dict] = None,
    scenario_name: Optional[str] = None,
    upgrade_xp: Optional[int] = None,
    campaign_name: Optional[str] = None,
    owned_sets: Optional[list[str]] = None,
    additional_instructions: str = "",
) -> str:
    """Format the orchestrator system prompt with context.

    Args:
        investigator_name: Name of the investigator
        deck_id: ID of the current deck
        deck_summary: Pre-computed deck summary dict
        scenario_name: Name of the scenario
        upgrade_xp: Available XP for upgrades
        campaign_name: Name of the campaign
        owned_sets: List of owned sets
        additional_instructions: Extra instructions to append

    Returns:
        Formatted system prompt string
    """
    context_block = build_context_block(
        investigator_name=investigator_name,
        deck_id=deck_id,
        deck_summary=deck_summary,
        scenario_name=scenario_name,
        upgrade_xp=upgrade_xp,
        campaign_name=campaign_name,
        owned_sets=owned_sets,
    )

    return ORCHESTRATOR_SYSTEM_PROMPT.format(
        context_block=context_block,
        additional_instructions=additional_instructions,
    )


def format_subagent_prompt(
    agent_type: Literal["rules", "state", "action_space", "scenario"],
    investigator_name: Optional[str] = None,
    deck_id: Optional[str] = None,
    deck_summary: Optional[dict] = None,
    scenario_name: Optional[str] = None,
    upgrade_xp: Optional[int] = None,
    campaign_name: Optional[str] = None,
    owned_sets: Optional[list[str]] = None,
) -> str:
    """Format a subagent system prompt with context.

    Args:
        agent_type: Which subagent prompt to format
        investigator_name: Name of the investigator
        deck_id: ID of the current deck
        deck_summary: Pre-computed deck summary dict
        scenario_name: Name of the scenario
        upgrade_xp: Available XP for upgrades
        campaign_name: Name of the campaign
        owned_sets: List of owned sets

    Returns:
        Formatted system prompt string

    Raises:
        ValueError: If agent_type is not recognized
    """
    prompt_map = {
        "rules": RULES_AGENT_PROMPT,
        "state": STATE_AGENT_PROMPT,
        "action_space": ACTION_SPACE_AGENT_PROMPT,
        "scenario": SCENARIO_AGENT_PROMPT,
    }

    if agent_type not in prompt_map:
        raise ValueError(
            f"Unknown agent type: '{agent_type}'. "
            f"Must be one of: {list(prompt_map.keys())}"
        )

    context_block = build_context_block(
        investigator_name=investigator_name,
        deck_id=deck_id,
        deck_summary=deck_summary,
        scenario_name=scenario_name,
        upgrade_xp=upgrade_xp,
        campaign_name=campaign_name,
        owned_sets=owned_sets,
    )

    return prompt_map[agent_type].format(context_block=context_block)


# =============================================================================
# Pydantic Input Schemas for Subagent Tools
# =============================================================================


class RulesQueryInput(BaseModel):
    """Input schema for querying the Rules Agent."""

    question: str = Field(
        description=(
            "The rules question to answer. Examples: "
            "'Can Roland Banks include Shrivelling?', "
            "'What level cards can Wendy access?', "
            "'Is Machete on the taboo list?'"
        )
    )
    investigator_name: Optional[str] = Field(
        default=None,
        description="The investigator to check rules for (if not in context)"
    )


class StateAnalysisInput(BaseModel):
    """Input schema for querying the State Agent."""

    analysis_type: Literal["full", "curve", "gaps", "redundancy"] = Field(
        default="full",
        description=(
            "Type of analysis to perform: "
            "'full' (comprehensive), "
            "'curve' (resource curve only), "
            "'gaps' (coverage gaps), "
            "'redundancy' (backup options)"
        )
    )
    deck_id: Optional[str] = Field(
        default=None,
        description="The deck ID to analyze (if not in context)"
    )
    focus_area: Optional[str] = Field(
        default=None,
        description="Specific area to focus analysis on (e.g., 'combat', 'clues', 'economy')"
    )


class CardSearchInput(BaseModel):
    """Input schema for querying the Action Space Agent."""

    search_query: str = Field(
        description=(
            "What kind of cards to search for. Examples: "
            "'cards that deal damage', "
            "'level 0-2 Seeker assets', "
            "'events that gain resources'"
        )
    )
    max_level: Optional[int] = Field(
        default=None,
        description="Maximum card level (XP) to include in results",
        ge=0,
        le=5,
    )
    card_type: Optional[Literal["asset", "event", "skill"]] = Field(
        default=None,
        description="Filter to specific card type"
    )
    class_filter: Optional[str] = Field(
        default=None,
        description="Filter to specific class (e.g., 'Guardian', 'Seeker', 'Neutral')"
    )
    owned_only: bool = Field(
        default=True,
        description="Only include cards from owned sets"
    )


class ScenarioAnalysisInput(BaseModel):
    """Input schema for querying the Scenario Agent."""

    scenario_name: str = Field(
        description="Name of the scenario to analyze (e.g., 'The Gathering', 'Blood on the Altar')"
    )
    analysis_focus: Literal["threats", "preparation", "strategy", "full"] = Field(
        default="full",
        description=(
            "What to focus on: "
            "'threats' (enemies/treacheries), "
            "'preparation' (deck recommendations), "
            "'strategy' (gameplay tips), "
            "'full' (comprehensive)"
        )
    )
    player_count: int = Field(
        default=1,
        description="Number of players (affects threat analysis)",
        ge=1,
        le=4,
    )


# =============================================================================
# LangGraph Subagent Invocation Tools
# =============================================================================


@tool("consult_rules_agent", args_schema=RulesQueryInput)
def consult_rules_agent(
    question: str,
    investigator_name: Optional[str] = None,
) -> str:
    """Consult the Rules Agent for deckbuilding rules and card legality questions.

    Use this tool when you need to:
    - Check if a card is legal for an investigator
    - Understand deckbuilding restrictions
    - Clarify XP costs and upgrade rules
    - Check taboo list status

    The Rules Agent specializes in game rules and will provide authoritative answers
    with rule citations.
    """
    # This is a routing stub - actual implementation will invoke the subagent
    # For now, return a placeholder that indicates the tool was called
    context = f" for {investigator_name}" if investigator_name else ""
    return f"[Rules Agent Query{context}]: {question}"


@tool("consult_state_agent", args_schema=StateAnalysisInput)
def consult_state_agent(
    analysis_type: str = "full",
    deck_id: Optional[str] = None,
    focus_area: Optional[str] = None,
) -> str:
    """Consult the State Agent for deck composition analysis.

    Use this tool when you need to:
    - Analyze a deck's resource curve
    - Identify gaps in deck coverage
    - Check card type distribution
    - Assess deck consistency and redundancy

    The State Agent specializes in quantitative deck analysis and will provide
    detailed breakdowns with specific numbers.
    """
    parts = [f"[State Agent Analysis: {analysis_type}]"]
    if deck_id:
        parts.append(f"Deck: {deck_id}")
    if focus_area:
        parts.append(f"Focus: {focus_area}")
    return " | ".join(parts)


@tool("consult_action_space_agent", args_schema=CardSearchInput)
def consult_action_space_agent(
    search_query: str,
    max_level: Optional[int] = None,
    card_type: Optional[str] = None,
    class_filter: Optional[str] = None,
    owned_only: bool = True,
) -> str:
    """Consult the Action Space Agent to search for cards.

    Use this tool when you need to:
    - Find cards that meet specific criteria
    - Discover upgrade options for existing cards
    - Search for cards with specific effects or traits
    - Find alternatives or backups for key cards

    The Action Space Agent specializes in card search and filtering, and will
    return relevant options from the available card pool.
    """
    filters = []
    if max_level is not None:
        filters.append(f"level 0-{max_level}")
    if card_type:
        filters.append(card_type)
    if class_filter:
        filters.append(class_filter)
    if owned_only:
        filters.append("owned only")

    filter_str = f" ({', '.join(filters)})" if filters else ""
    return f"[Action Space Agent Search{filter_str}]: {search_query}"


@tool("consult_scenario_agent", args_schema=ScenarioAnalysisInput)
def consult_scenario_agent(
    scenario_name: str,
    analysis_focus: str = "full",
    player_count: int = 1,
) -> str:
    """Consult the Scenario Agent for scenario-specific advice.

    Use this tool when you need to:
    - Understand scenario threats and challenges
    - Get preparation recommendations
    - Learn about key enemies and treacheries
    - Plan strategy for specific scenarios

    The Scenario Agent specializes in encounter analysis and will provide
    actionable advice for scenario preparation.
    """
    return f"[Scenario Agent: {scenario_name}] Focus: {analysis_focus}, Players: {player_count}"


# =============================================================================
# Tool Registries
# =============================================================================


# Subagent invocation tools for the orchestrator
SUBAGENT_TOOLS = [
    consult_rules_agent,
    consult_state_agent,
    consult_action_space_agent,
    consult_scenario_agent,
]

# Map of agent types to their invocation tools
AGENT_TOOL_MAP = {
    "rules": consult_rules_agent,
    "state": consult_state_agent,
    "action_space": consult_action_space_agent,
    "scenario": consult_scenario_agent,
}

# All available agent types
AGENT_TYPES = ["rules", "state", "action_space", "scenario"]
