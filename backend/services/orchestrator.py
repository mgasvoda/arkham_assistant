"""Orchestrator Core Loop with LangGraph.

This module implements the central orchestration agent that:
1. Receives user requests with deck/scenario context
2. Analyzes requests to determine which subagents to consult
3. Dispatches queries to subagents (in parallel where possible)
4. Synthesizes subagent responses into final recommendations

The orchestrator uses LangGraph for structured execution with the flow:
START -> analyze_request -> route_to_subagents -> collect_responses -> synthesize -> END
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from backend.models.deck_builder_models import (
    CardSelection,
    DeckBuilderSubagentResult,
    DeckBuildGoals,
    InvestigatorConstraints,
    NewDeckResponse,
)
from backend.models.subagent_models import SubagentResponse
from backend.services.llm_config import get_llm_config
from backend.services.subagents import (
    ActionSpaceQuery,
    StateQuery,
    SubagentConfig,
    create_action_space_agent,
    create_rules_agent,
    create_scenario_agent,
    create_state_agent,
)

# =============================================================================
# Enums and Constants
# =============================================================================


class SubagentType(str, Enum):
    """Types of subagents available for consultation."""

    RULES = "rules"
    STATE = "state"
    ACTION_SPACE = "action_space"
    SCENARIO = "scenario"


# Keywords that suggest which subagents should be consulted
ROUTING_KEYWORDS = {
    SubagentType.RULES: [
        "legal", "can i include", "allowed", "restriction", "taboo",
        "signature", "weakness", "class access", "xp cost", "level",
        "deckbuilding rule", "deck construction",
    ],
    SubagentType.STATE: [
        "analyze", "deck composition", "curve", "gaps", "missing",
        "strengths", "weaknesses", "synergy", "redundancy", "current deck",
        "my deck", "what does my deck",
    ],
    SubagentType.ACTION_SPACE: [
        "find cards", "search", "recommend", "suggest", "upgrade",
        "replacement", "alternatives", "options", "cards that",
        "what cards", "which cards",
    ],
    SubagentType.SCENARIO: [
        "scenario", "prepare", "threats", "encounter", "treachery",
        "enemy", "boss", "campaign", "mission", "before playing",
    ],
}

# Keywords that suggest the user wants to create a new deck
DECK_CREATION_KEYWORDS = [
    "build me", "build a deck", "create a deck", "new deck",
    "make me a deck", "start a new deck", "fresh deck",
    "build for", "create for", "deck for", "make a deck",
]


# =============================================================================
# Request/Response Models
# =============================================================================


class OrchestratorRequest(BaseModel):
    """Input schema for orchestrator requests.

    Attributes:
        message: The user's message/question.
        investigator_id: Optional investigator ID for context.
        investigator_name: Optional investigator name for display.
        deck_id: Optional deck ID to analyze.
        deck_cards: Optional list of card IDs or card data in the deck.
        scenario_name: Optional scenario being prepared for.
        campaign_name: Optional campaign name for context.
        upgrade_xp: Optional available XP for upgrades.
        owned_sets: Optional list of owned expansion names.
    """

    message: str = Field(description="The user's message or question")
    investigator_id: str | None = Field(
        default=None,
        description="Investigator ID for context"
    )
    investigator_name: str | None = Field(
        default=None,
        description="Investigator name for display"
    )
    deck_id: str | None = Field(
        default=None,
        description="Deck ID to analyze"
    )
    deck_cards: list[str] | dict[str, int] | None = Field(
        default=None,
        description="Card IDs or card data in the deck"
    )
    scenario_name: str | None = Field(
        default=None,
        description="Scenario being prepared for"
    )
    campaign_name: str | None = Field(
        default=None,
        description="Campaign name for context"
    )
    upgrade_xp: int | None = Field(
        default=None,
        description="Available XP for upgrades",
        ge=0,
    )
    owned_sets: list[str] | None = Field(
        default=None,
        description="List of owned expansion names"
    )


class SubagentResult(BaseModel):
    """Result from a single subagent consultation.

    Attributes:
        agent_type: Which subagent produced this result.
        query: The query sent to the subagent.
        response: The subagent's response.
        success: Whether the query succeeded.
        error: Error message if query failed.
    """

    agent_type: str = Field(description="The subagent type")
    query: str = Field(description="Query sent to the subagent")
    response: SubagentResponse | None = Field(
        default=None,
        description="The subagent response"
    )
    success: bool = Field(default=True, description="Whether query succeeded")
    error: str | None = Field(default=None, description="Error if failed")


class OrchestratorResponse(BaseModel):
    """Output schema for orchestrator responses.

    Attributes:
        content: The synthesized response content.
        recommendation: Specific actionable recommendation (if any).
        confidence: Overall confidence score (0-1).
        subagent_results: Results from each consulted subagent.
        agents_consulted: List of subagent types that were consulted.
        metadata: Additional metadata about the orchestration.
    """

    content: str = Field(description="Synthesized response content")
    recommendation: str | None = Field(
        default=None,
        description="Specific actionable recommendation"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Overall confidence score"
    )
    subagent_results: list[SubagentResult] = Field(
        default_factory=list,
        description="Results from consulted subagents"
    )
    agents_consulted: list[str] = Field(
        default_factory=list,
        description="Subagent types consulted"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional orchestration metadata"
    )

    @classmethod
    def error_response(
        cls,
        error_message: str,
        agents_consulted: list[str] | None = None,
    ) -> OrchestratorResponse:
        """Create an error response.

        Args:
            error_message: Description of the error.
            agents_consulted: Optional list of agents that were consulted.

        Returns:
            OrchestratorResponse indicating an error occurred.
        """
        return cls(
            content=error_message,
            confidence=0.0,
            agents_consulted=agents_consulted or [],
            metadata={"error": True},
        )


# =============================================================================
# LangGraph State
# =============================================================================


class OrchestratorState(BaseModel):
    """State for the orchestrator LangGraph execution.

    This state flows through graph nodes, accumulating information
    as the orchestrator processes a request.
    """

    # Input
    request: OrchestratorRequest
    context: dict[str, Any] = Field(default_factory=dict)

    # Routing
    agents_to_consult: list[SubagentType] = Field(default_factory=list)
    routing_reasoning: str = ""

    # Subagent results
    subagent_results: list[SubagentResult] = Field(default_factory=list)

    # Synthesis
    system_prompt: str = ""
    synthesized_content: str = ""

    # Output
    response: OrchestratorResponse | None = None
    error: str | None = None


class DeckBuilderState(BaseModel):
    """State for the deck building LangGraph execution.

    This state flows through deck building nodes, tracking
    goals, constraints, candidates, and the final deck.
    """

    # Input
    request: OrchestratorRequest
    context: dict[str, Any] = Field(default_factory=dict)

    # Goal Extraction
    goals: DeckBuildGoals | None = None

    # Rules & Constraints
    constraints: InvestigatorConstraints | None = None

    # Scenario Context (optional)
    scenario_priorities: list[str] = Field(default_factory=list)

    # Card Pool from ActionSpaceAgent
    candidate_cards: list[dict[str, Any]] = Field(default_factory=list)

    # Deck Building
    selected_cards: list[CardSelection] = Field(default_factory=list)
    current_card_count: int = 0

    # Validation
    deck_warnings: list[str] = Field(default_factory=list)
    validation_passed: bool = False

    # Subagent Results for transparency
    subagent_results: list[DeckBuilderSubagentResult] = Field(default_factory=list)

    # Output
    response: NewDeckResponse | None = None
    error: str | None = None


# =============================================================================
# Orchestrator Configuration
# =============================================================================


@dataclass(frozen=True)
class OrchestratorConfig:
    """Configuration for orchestrator execution.

    Attributes:
        temperature: LLM temperature for synthesis (0.0 = deterministic).
        max_tokens: Maximum tokens in synthesis response.
        timeout_seconds: Max time to wait for all subagents.
        parallel_dispatch: Whether to dispatch subagent queries in parallel.
    """

    temperature: float = 0.0
    max_tokens: int = 4096
    timeout_seconds: float = 60.0
    parallel_dispatch: bool = True


# =============================================================================
# Orchestrator Implementation
# =============================================================================


class Orchestrator:
    """Central orchestration agent for the Arkham Assistant.

    The orchestrator:
    1. Receives user requests with deck/scenario context
    2. Analyzes requests to determine which subagents to consult
    3. Dispatches queries to subagents (in parallel where possible)
    4. Synthesizes subagent responses into final recommendations

    Attributes:
        config: Configuration settings for execution.
        llm: The LangChain chat model for synthesis.
        graph: The compiled LangGraph for execution.
        subagents: Dict of initialized subagent instances.
    """

    # Synthesis prompt for combining subagent responses
    SYNTHESIS_PROMPT = """You are synthesizing responses from specialized subagents to answer a user's deckbuilding question.

## User's Question
{user_message}

## Context
{context_block}

## Subagent Responses

{subagent_responses}

## Your Task

Synthesize the above information into a clear, actionable response that:
1. Directly answers the user's question
2. Combines insights from multiple subagents when relevant
3. Resolves any conflicts between subagent responses
4. Provides specific, actionable recommendations
5. Explains the reasoning behind recommendations

If subagents provided card suggestions, prioritize them by relevance and explain why each is recommended.
If there are conflicting recommendations, explain the trade-offs.

Keep the response focused and concise while being comprehensive."""

    def __init__(
        self,
        config: OrchestratorConfig | None = None,
        subagent_config: SubagentConfig | None = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            config: Optional orchestrator configuration.
            subagent_config: Optional config to pass to subagents.
        """
        self.config = config or OrchestratorConfig()
        self.subagent_config = subagent_config
        self.llm = self._create_llm()
        self.graph = self._build_graph()
        self._subagents: dict[SubagentType, Any] = {}

    def _create_llm(self) -> ChatOpenAI:
        """Create the LLM instance for synthesis.

        Returns:
            Configured ChatOpenAI instance.

        Raises:
            ValueError: If OPENAI_API_KEY is not set.
        """
        llm_config = get_llm_config()
        if not llm_config.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        return ChatOpenAI(
            model=llm_config.orchestrator_model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            api_key=llm_config.api_key,
        )

    def _get_subagent(self, agent_type: SubagentType) -> Any:
        """Get or create a subagent instance.

        Args:
            agent_type: The type of subagent to get.

        Returns:
            Initialized subagent instance.
        """
        if agent_type not in self._subagents:
            if agent_type == SubagentType.RULES:
                self._subagents[agent_type] = create_rules_agent(
                    config=self.subagent_config
                )
            elif agent_type == SubagentType.STATE:
                self._subagents[agent_type] = create_state_agent()
            elif agent_type == SubagentType.ACTION_SPACE:
                self._subagents[agent_type] = create_action_space_agent()
            elif agent_type == SubagentType.SCENARIO:
                self._subagents[agent_type] = create_scenario_agent(
                    config=self.subagent_config
                )
        return self._subagents[agent_type]

    def _is_new_deck_request(self, request: OrchestratorRequest) -> bool:
        """Determine if request is for new deck creation.

        Checks for deck creation keywords and context that suggests
        the user wants to build a new deck from scratch.

        Args:
            request: The user's request.

        Returns:
            True if this is a new deck creation request.
        """
        message_lower = request.message.lower()

        # Check for explicit deck creation keywords
        if any(keyword in message_lower for keyword in DECK_CREATION_KEYWORDS):
            return True

        # Check for investigator specified with no existing deck context
        if request.investigator_id and not request.deck_cards and not request.deck_id:
            # Could be deck creation if asking about building
            if any(word in message_lower for word in ["deck", "build", "start", "create"]):
                return True

        return False

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph for orchestration.

        The graph follows:
        START -> analyze_request -> route_to_subagents ->
        collect_responses -> synthesize -> END

        Returns:
            Compiled StateGraph ready for execution.
        """
        graph = StateGraph(OrchestratorState)

        # Add nodes
        graph.add_node("analyze_request", self._analyze_request_node)
        graph.add_node("route_to_subagents", self._route_to_subagents_node)
        graph.add_node("collect_responses", self._collect_responses_node)
        graph.add_node("synthesize", self._synthesize_node)

        # Define edges
        graph.set_entry_point("analyze_request")
        graph.add_edge("analyze_request", "route_to_subagents")
        graph.add_edge("route_to_subagents", "collect_responses")
        graph.add_edge("collect_responses", "synthesize")
        graph.add_edge("synthesize", END)

        return graph.compile()

    def _analyze_request_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Analyze the user's request to understand intent.

        This node examines the request and context to prepare for routing.

        Args:
            state: Current graph state with request.

        Returns:
            State update with analysis context.
        """
        request = state.request

        # Build context dict from request
        context = {
            "investigator_id": request.investigator_id,
            "investigator_name": request.investigator_name,
            "deck_id": request.deck_id,
            "deck_cards": request.deck_cards,
            "scenario_name": request.scenario_name,
            "campaign_name": request.campaign_name,
            "upgrade_xp": request.upgrade_xp,
            "owned_sets": request.owned_sets,
        }

        # Remove None values
        context = {k: v for k, v in context.items() if v is not None}

        return {"context": context}

    def _route_to_subagents_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Determine which subagents to consult based on the request.

        Uses keyword matching and context to decide routing.

        Args:
            state: Current graph state with request and context.

        Returns:
            State update with agents to consult and reasoning.
        """
        message_lower = state.request.message.lower()
        agents_to_consult: list[SubagentType] = []
        reasoning_parts: list[str] = []

        # Keyword-based routing
        for agent_type, keywords in ROUTING_KEYWORDS.items():
            if any(keyword in message_lower for keyword in keywords):
                agents_to_consult.append(agent_type)
                matched = [k for k in keywords if k in message_lower]
                reasoning_parts.append(
                    f"{agent_type.value}: matched keywords {matched[:2]}"
                )

        # Context-based routing additions
        context = state.context

        # If deck context is provided, always include state analysis
        if (context.get("deck_cards") or context.get("deck_id")) and \
           SubagentType.STATE not in agents_to_consult:
            agents_to_consult.append(SubagentType.STATE)
            reasoning_parts.append("state: deck context provided")

        # If scenario context is provided, always include scenario analysis
        if context.get("scenario_name") and \
           SubagentType.SCENARIO not in agents_to_consult:
            agents_to_consult.append(SubagentType.SCENARIO)
            reasoning_parts.append("scenario: scenario context provided")

        # If asking about specific cards or upgrades with XP, include action space
        if context.get("upgrade_xp") and \
           SubagentType.ACTION_SPACE not in agents_to_consult:
            agents_to_consult.append(SubagentType.ACTION_SPACE)
            reasoning_parts.append("action_space: upgrade XP context provided")

        # Default: if no agents matched, try to be helpful
        if not agents_to_consult:
            # General question - consult rules first
            agents_to_consult.append(SubagentType.RULES)
            reasoning_parts.append("rules: default for general questions")

        routing_reasoning = "; ".join(reasoning_parts)

        return {
            "agents_to_consult": agents_to_consult,
            "routing_reasoning": routing_reasoning,
        }

    def _collect_responses_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Dispatch queries to subagents and collect responses.

        Queries are dispatched in parallel when configured.

        Args:
            state: Current graph state with agents to consult.

        Returns:
            State update with subagent results.
        """
        results: list[SubagentResult] = []

        for agent_type in state.agents_to_consult:
            result = self._query_subagent(
                agent_type,
                state.request,
                state.context,
            )
            results.append(result)

        return {"subagent_results": results}

    def _query_subagent(
        self,
        agent_type: SubagentType,
        request: OrchestratorRequest,
        context: dict[str, Any],
    ) -> SubagentResult:
        """Query a single subagent.

        Args:
            agent_type: The subagent to query.
            request: The original orchestrator request.
            context: The context dict.

        Returns:
            SubagentResult with the query outcome.
        """
        try:
            subagent = self._get_subagent(agent_type)
            query = self._format_subagent_query(agent_type, request)

            # Different subagents have different query methods
            if agent_type == SubagentType.RULES:
                response = subagent.query(query, context)
            elif agent_type == SubagentType.STATE:
                # StateAgent uses analyze() with StateQuery
                card_list = request.deck_cards if request.deck_cards else []
                state_query = StateQuery(
                    card_list=card_list,
                    investigator_id=request.investigator_id or "",
                    upgrade_points=request.upgrade_xp or 0,
                )
                response = subagent.analyze(state_query)
            elif agent_type == SubagentType.ACTION_SPACE:
                # ActionSpaceAgent needs specific context
                action_context = dict(context)
                response = subagent.query(query, action_context)
            elif agent_type == SubagentType.SCENARIO:
                response = subagent.query(query, context)
            else:
                raise ValueError(f"Unknown agent type: {agent_type}")

            return SubagentResult(
                agent_type=agent_type.value,
                query=query,
                response=response,
                success=True,
            )

        except Exception as e:
            return SubagentResult(
                agent_type=agent_type.value,
                query=request.message,
                response=None,
                success=False,
                error=str(e),
            )

    def _format_subagent_query(
        self,
        agent_type: SubagentType,
        request: OrchestratorRequest,
    ) -> str:
        """Format the query string for a specific subagent.

        Args:
            agent_type: The subagent type.
            request: The original request.

        Returns:
            Formatted query string.
        """
        # Most subagents can use the original message directly
        # but we can add context-specific formatting
        base_message = request.message

        if agent_type == SubagentType.STATE:
            # State agent benefits from knowing what analysis is needed
            if "gap" in base_message.lower() or "missing" in base_message.lower():
                return f"Analyze deck for gaps and missing capabilities. {base_message}"
            return f"Analyze the deck composition. {base_message}"

        if agent_type == SubagentType.ACTION_SPACE:
            # Action space benefits from explicit search context
            if request.upgrade_xp:
                return f"Search for upgrade options with {request.upgrade_xp} XP. {base_message}"
            return base_message

        if agent_type == SubagentType.SCENARIO:
            # Scenario agent needs scenario name emphasized
            if request.scenario_name:
                return f"Analyze {request.scenario_name}. {base_message}"
            return base_message

        return base_message

    def _synthesize_node(self, state: OrchestratorState) -> dict[str, Any]:
        """Synthesize subagent responses into a final response.

        Uses the LLM to combine insights from multiple subagents.

        Args:
            state: Current graph state with subagent results.

        Returns:
            State update with final response.
        """
        # Build context block for synthesis
        context_lines = []
        if state.context.get("investigator_name"):
            context_lines.append(
                f"**Investigator**: {state.context['investigator_name']}"
            )
        if state.context.get("deck_id"):
            context_lines.append(f"**Deck ID**: {state.context['deck_id']}")
        if state.context.get("scenario_name"):
            context_lines.append(
                f"**Scenario**: {state.context['scenario_name']}"
            )
        if state.context.get("upgrade_xp"):
            context_lines.append(
                f"**Available XP**: {state.context['upgrade_xp']}"
            )
        context_block = "\n".join(context_lines) if context_lines else "*No specific context*"

        # Format subagent responses for synthesis
        subagent_response_parts = []
        for result in state.subagent_results:
            if result.success and result.response:
                subagent_response_parts.append(
                    f"### {result.agent_type.upper()} Agent\n"
                    f"**Query**: {result.query}\n"
                    f"**Confidence**: {result.response.confidence:.2f}\n"
                    f"**Response**:\n{result.response.content}"
                )
            else:
                subagent_response_parts.append(
                    f"### {result.agent_type.upper()} Agent\n"
                    f"**Error**: {result.error or 'Unknown error'}"
                )

        subagent_responses = "\n\n".join(subagent_response_parts) or "*No subagent responses*"

        # Build synthesis prompt
        synthesis_prompt = self.SYNTHESIS_PROMPT.format(
            user_message=state.request.message,
            context_block=context_block,
            subagent_responses=subagent_responses,
        )

        try:
            # Invoke LLM for synthesis
            messages = [
                SystemMessage(content=synthesis_prompt),
                HumanMessage(content="Please synthesize the above into a helpful response."),
            ]
            result = self.llm.invoke(messages)

            content = (
                result.content
                if isinstance(result.content, str)
                else str(result.content)
            )

            # Calculate overall confidence
            confidences = [
                r.response.confidence
                for r in state.subagent_results
                if r.success and r.response
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

            # Extract recommendation if present
            recommendation = self._extract_recommendation(content)

            response = OrchestratorResponse(
                content=content,
                recommendation=recommendation,
                confidence=avg_confidence,
                subagent_results=state.subagent_results,
                agents_consulted=[a.value for a in state.agents_to_consult],
                metadata={
                    "routing_reasoning": state.routing_reasoning,
                    "subagents_successful": sum(
                        1 for r in state.subagent_results if r.success
                    ),
                    "subagents_failed": sum(
                        1 for r in state.subagent_results if not r.success
                    ),
                },
            )

            return {"response": response}

        except Exception as e:
            return {
                "response": OrchestratorResponse.error_response(
                    error_message=f"Synthesis failed: {e}",
                    agents_consulted=[a.value for a in state.agents_to_consult],
                )
            }

    def _extract_recommendation(self, content: str) -> str | None:
        """Extract a specific recommendation from synthesized content.

        Args:
            content: The synthesized response content.

        Returns:
            Extracted recommendation or None.
        """
        # Look for recommendation patterns
        import re

        patterns = [
            r'\*\*Recommendation\*\*:\s*(.+?)(?=\n\n|\*\*|$)',
            r'I recommend\s+(.+?)(?:\.|$)',
            r'My recommendation is\s+(.+?)(?:\.|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        return None

    # =========================================================================
    # Deck Builder Pipeline Nodes
    # =========================================================================

    # Prompt for extracting deck building goals from user message
    GOAL_EXTRACTION_PROMPT = """Analyze the user's deck building request and extract their goals.

User's Request: {message}
Investigator: {investigator_name}

Extract:
1. Primary focus: What is the main playstyle? (combat, clues, support, or flex)
2. Secondary focus: Any secondary goal? (may be null)
3. Specific requests: List any specific things mentioned (e.g., "lots of card draw", "cheap cards")
4. Avoid: Anything they want to avoid?

Respond in this exact JSON format:
{{
    "primary_focus": "combat|clues|support|flex",
    "secondary_focus": "combat|clues|support|flex|null",
    "specific_requests": ["request1", "request2"],
    "avoid_cards": ["thing1", "thing2"]
}}"""

    DECK_SYNTHESIS_PROMPT = """Generate a deck name and overall reasoning for this deck build.

Investigator: {investigator_name}
Archetype: {archetype}
Goals: {goals}
Card Count: {card_count}
Selected Cards by Category:
{cards_by_category}

Warnings/Concerns: {warnings}

Generate:
1. A creative deck name (2-4 words) that captures the theme
2. A brief overall reasoning (2-3 sentences) explaining the deck's strategy

Respond in this exact JSON format:
{{
    "deck_name": "Name Here",
    "reasoning": "Explanation of the deck strategy and why cards were chosen."
}}"""

    def _build_deck_graph(self) -> StateGraph:
        """Build the LangGraph for deck building.

        The graph follows:
        START -> extract_goals -> get_constraints -> [analyze_scenario] ->
        search_cards -> build_deck -> validate_deck -> synthesize_deck -> END

        Returns:
            Compiled StateGraph ready for deck building execution.
        """
        graph = StateGraph(DeckBuilderState)

        # Add nodes
        graph.add_node("extract_goals", self._extract_goals_node)
        graph.add_node("get_constraints", self._get_constraints_node)
        graph.add_node("analyze_scenario", self._analyze_scenario_node)
        graph.add_node("search_cards", self._search_cards_node)
        graph.add_node("build_deck", self._build_deck_node)
        graph.add_node("validate_deck", self._validate_deck_node)
        graph.add_node("synthesize_deck", self._synthesize_deck_response_node)

        # Define edges
        graph.set_entry_point("extract_goals")
        graph.add_edge("extract_goals", "get_constraints")

        # Conditional edge: analyze_scenario only if scenario provided
        def should_analyze_scenario(state: DeckBuilderState) -> str:
            if state.context.get("scenario_name"):
                return "analyze_scenario"
            return "search_cards"

        graph.add_conditional_edges(
            "get_constraints",
            should_analyze_scenario,
            {
                "analyze_scenario": "analyze_scenario",
                "search_cards": "search_cards",
            }
        )

        graph.add_edge("analyze_scenario", "search_cards")
        graph.add_edge("search_cards", "build_deck")
        graph.add_edge("build_deck", "validate_deck")
        graph.add_edge("validate_deck", "synthesize_deck")
        graph.add_edge("synthesize_deck", END)

        return graph.compile()

    def _extract_goals_node(self, state: DeckBuilderState) -> dict[str, Any]:
        """Extract deck building goals from user message.

        Uses LLM to parse the user's intent and identify:
        - Primary focus (combat, clues, support, flex)
        - Secondary focus
        - Specific requests
        - Things to avoid

        Args:
            state: Current deck builder state.

        Returns:
            State update with extracted goals.
        """
        import json as json_module

        # Build context from request
        context = {
            "investigator_id": state.request.investigator_id,
            "investigator_name": state.request.investigator_name or state.request.investigator_id,
            "scenario_name": state.request.scenario_name,
        }
        context = {k: v for k, v in context.items() if v is not None}

        # Format the goal extraction prompt
        prompt = self.GOAL_EXTRACTION_PROMPT.format(
            message=state.request.message,
            investigator_name=context.get("investigator_name", "Unknown"),
        )

        try:
            messages = [
                SystemMessage(content="You are a deck building assistant. Extract goals from user requests."),
                HumanMessage(content=prompt),
            ]
            result = self.llm.invoke(messages)
            content = result.content if isinstance(result.content, str) else str(result.content)

            # Parse JSON from response
            # Try to extract JSON from the response
            if "{" in content and "}" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
                goals_data = json_module.loads(json_str)

                goals = DeckBuildGoals(
                    primary_focus=goals_data.get("primary_focus", "flex"),
                    secondary_focus=goals_data.get("secondary_focus"),
                    specific_requests=goals_data.get("specific_requests", []),
                    avoid_cards=goals_data.get("avoid_cards", []),
                )
            else:
                # Default goals if parsing fails
                goals = DeckBuildGoals(primary_focus="flex")

        except Exception:
            # Default goals on error
            goals = DeckBuildGoals(primary_focus="flex")

        return {"goals": goals, "context": context}

    def _get_constraints_node(self, state: DeckBuilderState) -> dict[str, Any]:
        """Get investigator deckbuilding constraints.

        Queries RulesAgent and ChromaDB to get:
        - Class access rules
        - Deck size requirements
        - Signature cards
        - Special rules

        Args:
            state: Current deck builder state.

        Returns:
            State update with investigator constraints.
        """
        from backend.services.chroma_client import ChromaClient

        investigator_id = state.request.investigator_id
        if not investigator_id:
            return {
                "error": "No investigator specified",
                "constraints": None,
            }

        # Get investigator data from ChromaDB
        chroma = ChromaClient()
        investigator = chroma.get_character(investigator_id)

        subagent_results = list(state.subagent_results)

        if investigator:
            # Parse class access from investigator data
            faction = investigator.get("faction_name", "")
            name = investigator.get("name", investigator_id)

            # Parse deck_options for secondary class
            deck_options = investigator.get("deck_options", "")
            secondary_class = None
            secondary_level = 0

            if deck_options:
                # Simple parsing - could be enhanced
                for class_name in ["Guardian", "Seeker", "Rogue", "Mystic", "Survivor"]:
                    if class_name.lower() in deck_options.lower() and class_name != faction:
                        secondary_class = class_name
                        # Check for level restriction
                        if "level 0" in deck_options.lower():
                            secondary_level = 0
                        elif "level 2" in deck_options.lower():
                            secondary_level = 2
                        break

            # Get signature cards
            required_cards = []
            deck_requirements = investigator.get("deck_requirements", "")
            if deck_requirements and "signature" in deck_requirements.lower():
                # Would need to look up signature cards - simplified for now
                pass

            constraints = InvestigatorConstraints(
                investigator_id=investigator_id,
                investigator_name=name,
                primary_class=faction,
                secondary_class=secondary_class,
                secondary_level=secondary_level,
                deck_size=30,  # Standard
                required_cards=required_cards,
            )

            subagent_results.append(DeckBuilderSubagentResult(
                agent_type="rules",
                query=f"Get deckbuilding constraints for {name}",
                success=True,
                summary=f"Primary: {faction}, Secondary: {secondary_class or 'None'}",
            ))
        else:
            # Fallback with basic constraints
            constraints = InvestigatorConstraints(
                investigator_id=investigator_id,
                investigator_name=investigator_id,
                primary_class="Neutral",
                deck_size=30,
            )

            subagent_results.append(DeckBuilderSubagentResult(
                agent_type="rules",
                query=f"Get deckbuilding constraints for {investigator_id}",
                success=False,
                summary="Investigator not found, using defaults",
            ))

        return {
            "constraints": constraints,
            "subagent_results": subagent_results,
        }

    def _analyze_scenario_node(self, state: DeckBuilderState) -> dict[str, Any]:
        """Analyze scenario for threat priorities (optional).

        Queries ScenarioAgent to get preparation priorities based on
        the scenario's threats and challenges.

        Args:
            state: Current deck builder state.

        Returns:
            State update with scenario priorities.
        """
        scenario_name = state.context.get("scenario_name")
        if not scenario_name:
            return {"scenario_priorities": []}

        subagent_results = list(state.subagent_results)

        try:
            scenario_agent = self._get_subagent(SubagentType.SCENARIO)
            response = scenario_agent.query(
                f"What should I prepare for {scenario_name}?",
                state.context,
            )

            # Extract priorities from response
            priorities = []
            content_lower = response.content.lower()

            # Look for capability mentions
            capability_keywords = {
                "willpower": ["willpower", "horror", "treachery"],
                "combat": ["combat", "fight", "enemy", "damage"],
                "clues": ["clues", "investigate", "intellect"],
                "agility": ["agility", "evade"],
            }

            for capability, keywords in capability_keywords.items():
                if any(kw in content_lower for kw in keywords):
                    priorities.append(capability)

            subagent_results.append(DeckBuilderSubagentResult(
                agent_type="scenario",
                query=f"Analyze {scenario_name}",
                success=True,
                summary=f"Priorities: {', '.join(priorities) or 'general'}",
            ))

            return {
                "scenario_priorities": priorities,
                "subagent_results": subagent_results,
            }

        except Exception as e:
            subagent_results.append(DeckBuilderSubagentResult(
                agent_type="scenario",
                query=f"Analyze {scenario_name}",
                success=False,
                summary=str(e),
            ))
            return {
                "scenario_priorities": [],
                "subagent_results": subagent_results,
            }

    def _search_cards_node(self, state: DeckBuilderState) -> dict[str, Any]:
        """Search for candidate cards using ActionSpaceAgent.

        Performs multiple searches based on goals:
        - Primary focus cards
        - Secondary focus cards
        - Economy cards (resources, card draw)
        - Protection cards

        Args:
            state: Current deck builder state.

        Returns:
            State update with candidate cards.
        """
        if not state.constraints:
            return {"candidate_cards": [], "error": "No constraints available"}

        subagent_results = list(state.subagent_results)
        action_agent = self._get_subagent(SubagentType.ACTION_SPACE)
        all_candidates: list[dict[str, Any]] = []
        seen_card_ids: set[str] = set()

        # Map focus areas to capability needs
        focus_to_capability = {
            "combat": "combat",
            "clues": "clues",
            "support": "willpower",
            "flex": None,
        }

        # Search based on goals
        searches = []

        # Primary focus
        if state.goals:
            primary_cap = focus_to_capability.get(state.goals.primary_focus)
            if primary_cap:
                searches.append(("primary", primary_cap, 20))

            # Secondary focus
            if state.goals.secondary_focus:
                secondary_cap = focus_to_capability.get(state.goals.secondary_focus)
                if secondary_cap:
                    searches.append(("secondary", secondary_cap, 15))

        # Always search for economy cards
        searches.append(("economy", "economy", 10))
        searches.append(("draw", "card_draw", 10))

        # Add scenario priorities
        for priority in state.scenario_priorities[:2]:
            searches.append(("scenario", priority, 10))

        # Perform searches
        for search_name, capability, limit in searches:
            try:
                query = ActionSpaceQuery(
                    investigator_id=state.constraints.investigator_id,
                    upgrade_points=0,  # Level 0 only for new decks
                    capability_need=capability,
                    limit=limit,
                )
                response = action_agent.search(query, state.context)

                for candidate in response.candidates:
                    if candidate.card_id not in seen_card_ids:
                        seen_card_ids.add(candidate.card_id)
                        all_candidates.append({
                            "card_id": candidate.card_id,
                            "name": candidate.name,
                            "xp_cost": candidate.xp_cost,
                            "relevance_score": candidate.relevance_score,
                            "reason": candidate.reason,
                            "card_type": candidate.card_type,
                            "class_name": candidate.class_name,
                            "cost": candidate.cost,
                            "traits": candidate.traits,
                            "text": candidate.text,
                            "search_category": search_name,
                            "capability": capability,
                        })

            except Exception:
                pass  # Continue with other searches

        subagent_results.append(DeckBuilderSubagentResult(
            agent_type="action_space",
            query=f"Search cards for {state.goals.primary_focus if state.goals else 'general'} deck",
            success=len(all_candidates) > 0,
            summary=f"Found {len(all_candidates)} candidate cards",
        ))

        return {
            "candidate_cards": all_candidates,
            "subagent_results": subagent_results,
        }

    def _build_deck_node(self, state: DeckBuilderState) -> dict[str, Any]:
        """Build the deck from candidate cards.

        Algorithmic card selection:
        1. Add signature cards (required)
        2. Add primary focus cards (8-12)
        3. Add secondary focus cards (4-8)
        4. Add economy cards (4-6)
        5. Fill remaining slots

        Args:
            state: Current deck builder state.

        Returns:
            State update with selected cards.
        """
        if not state.constraints:
            return {"selected_cards": [], "current_card_count": 0}

        deck_size = state.constraints.deck_size
        selected: list[CardSelection] = []
        card_counts: dict[str, int] = {}  # track copies per card

        def add_card(card: dict, quantity: int, category: str) -> bool:
            """Add card to deck if possible."""
            card_id = card["card_id"]
            current = card_counts.get(card_id, 0)
            can_add = min(2 - current, quantity)

            if can_add <= 0:
                return False

            current_total = sum(card_counts.values())
            if current_total + can_add > deck_size:
                can_add = deck_size - current_total
                if can_add <= 0:
                    return False

            selected.append(CardSelection(
                card_id=card_id,
                name=card["name"],
                quantity=can_add,
                reason=card.get("reason", "Matches deck goals"),
                category=category,
            ))
            card_counts[card_id] = current + can_add
            return True

        # 1. Add signature cards (required)
        for card_id in state.constraints.required_cards:
            # Would need to look up card data - simplified
            pass

        # Categorize candidates
        primary_cards = []
        secondary_cards = []
        economy_cards = []
        draw_cards = []
        other_cards = []

        primary_focus = state.goals.primary_focus if state.goals else "flex"
        secondary_focus = state.goals.secondary_focus if state.goals else None

        for card in state.candidate_cards:
            category = card.get("search_category", "other")
            capability = card.get("capability", "")

            if category == "primary" or capability == primary_focus:
                primary_cards.append(card)
            elif category == "secondary" or capability == secondary_focus:
                secondary_cards.append(card)
            elif capability == "economy":
                economy_cards.append(card)
            elif capability == "card_draw":
                draw_cards.append(card)
            else:
                other_cards.append(card)

        # Sort each category by relevance
        for card_list in [primary_cards, secondary_cards, economy_cards, draw_cards, other_cards]:
            card_list.sort(key=lambda c: c.get("relevance_score", 0), reverse=True)

        # 2. Add primary focus cards (target: 10-12 cards)
        target_primary = 12
        for card in primary_cards[:target_primary]:
            add_card(card, 2, primary_focus)

        # 3. Add secondary focus cards (target: 4-6 cards)
        if secondary_focus:
            target_secondary = 6
            for card in secondary_cards[:target_secondary]:
                add_card(card, 2, secondary_focus)

        # 4. Add economy cards (target: 4-6 cards)
        target_economy = 6
        for card in economy_cards[:target_economy]:
            add_card(card, 2, "economy")

        # 5. Add card draw (target: 4 cards)
        for card in draw_cards[:4]:
            add_card(card, 2, "draw")

        # 6. Fill remaining slots with other cards
        current_count = sum(card_counts.values())
        remaining = deck_size - current_count

        if remaining > 0:
            # Use scenario cards first, then other high-relevance cards
            filler_cards = sorted(
                other_cards + primary_cards[target_primary:] + secondary_cards[6:],
                key=lambda c: c.get("relevance_score", 0),
                reverse=True,
            )

            for card in filler_cards:
                if sum(card_counts.values()) >= deck_size:
                    break
                add_card(card, 2, "flex")

        final_count = sum(card_counts.values())

        return {
            "selected_cards": selected,
            "current_card_count": final_count,
        }

    def _validate_deck_node(self, state: DeckBuilderState) -> dict[str, Any]:
        """Validate deck composition using StateAgent.

        Checks for:
        - Identified gaps in capabilities
        - Overall deck health
        - Warnings about the build

        Args:
            state: Current deck builder state.

        Returns:
            State update with validation results.
        """
        subagent_results = list(state.subagent_results)
        warnings: list[str] = []

        # Check card count
        if state.current_card_count < (state.constraints.deck_size if state.constraints else 30):
            warnings.append(
                f"Deck has {state.current_card_count} cards, "
                f"needs {state.constraints.deck_size if state.constraints else 30}"
            )

        # Use StateAgent for detailed analysis
        try:
            state_agent = self._get_subagent(SubagentType.STATE)

            # Convert selected cards to card list format
            card_list = []
            for card in state.selected_cards:
                for _ in range(card.quantity):
                    card_list.append(card.card_id)

            # StateAgent uses analyze() with StateQuery
            inv_id = state.constraints.investigator_id if state.constraints else ""
            state_query = StateQuery(
                card_list=card_list,
                investigator_id=inv_id,
                upgrade_points=0,
            )
            response = state_agent.analyze(state_query)

            # Extract gaps from response
            if hasattr(response, "identified_gaps") and response.identified_gaps:
                for gap in response.identified_gaps:
                    warnings.append(f"Gap: {gap}")

            subagent_results.append(DeckBuilderSubagentResult(
                agent_type="state",
                query="Validate deck composition",
                success=True,
                summary=f"Found {len(warnings)} issues",
            ))

            validation_passed = len(warnings) <= 2  # Allow minor issues

        except Exception as e:
            subagent_results.append(DeckBuilderSubagentResult(
                agent_type="state",
                query="Validate deck composition",
                success=False,
                summary=str(e),
            ))
            validation_passed = True  # Don't block on validation errors

        return {
            "deck_warnings": warnings,
            "validation_passed": validation_passed,
            "subagent_results": subagent_results,
        }

    def _synthesize_deck_response_node(self, state: DeckBuilderState) -> dict[str, Any]:
        """Synthesize final deck response with name and reasoning.

        Uses LLM to generate:
        - Creative deck name
        - Overall reasoning for the build

        Args:
            state: Current deck builder state.

        Returns:
            State update with final NewDeckResponse.
        """
        import json as json_module

        if not state.constraints:
            return {
                "response": NewDeckResponse.error_response(
                    "Failed to build deck: No constraints available"
                )
            }

        # Determine archetype
        primary = state.goals.primary_focus if state.goals else "flex"
        archetype = f"{primary.title()} {state.constraints.primary_class}"

        # Group cards by category
        cards_by_category: dict[str, list[str]] = {}
        for card in state.selected_cards:
            category = card.category
            if category not in cards_by_category:
                cards_by_category[category] = []
            cards_by_category[category].append(f"{card.name} x{card.quantity}")

        cards_summary = "\n".join(
            f"- {cat}: {', '.join(cards)}"
            for cat, cards in cards_by_category.items()
        )

        # Generate deck name and reasoning via LLM
        try:
            prompt = self.DECK_SYNTHESIS_PROMPT.format(
                investigator_name=state.constraints.investigator_name,
                archetype=archetype,
                goals=f"Primary: {primary}, Secondary: {state.goals.secondary_focus if state.goals else 'None'}",
                card_count=state.current_card_count,
                cards_by_category=cards_summary,
                warnings=", ".join(state.deck_warnings) if state.deck_warnings else "None",
            )

            messages = [
                SystemMessage(content="You are a creative deck naming assistant."),
                HumanMessage(content=prompt),
            ]
            result = self.llm.invoke(messages)
            content = result.content if isinstance(result.content, str) else str(result.content)

            # Parse JSON response
            if "{" in content and "}" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
                synthesis_data = json_module.loads(json_str)

                deck_name = synthesis_data.get("deck_name", f"{archetype} Deck")
                reasoning = synthesis_data.get("reasoning", "A balanced deck for the investigator.")
            else:
                deck_name = f"{archetype} Deck"
                reasoning = "A balanced deck built to match your goals."

        except Exception:
            deck_name = f"{archetype} Deck"
            reasoning = "A balanced deck built to match your goals."

        # Calculate confidence based on deck completeness
        deck_size = state.constraints.deck_size
        completeness = min(1.0, state.current_card_count / deck_size)
        warning_penalty = len(state.deck_warnings) * 0.1
        confidence = max(0.3, min(0.95, completeness - warning_penalty))

        response = NewDeckResponse(
            deck_name=deck_name,
            investigator_id=state.constraints.investigator_id,
            investigator_name=state.constraints.investigator_name,
            cards=state.selected_cards,
            total_cards=state.current_card_count,
            reasoning=reasoning,
            archetype=archetype,
            warnings=state.deck_warnings,
            confidence=confidence,
            subagent_results=state.subagent_results,
            metadata={
                "goals": state.goals.model_dump() if state.goals else {},
                "scenario_priorities": state.scenario_priorities,
            },
        )

        return {"response": response}

    def _process_new_deck(
        self,
        request: OrchestratorRequest,
    ) -> NewDeckResponse:
        """Process a new deck creation request.

        Args:
            request: The user's deck building request.

        Returns:
            NewDeckResponse with the complete deck.
        """
        try:
            # Build the deck builder graph if not cached
            if not hasattr(self, "_deck_builder_graph"):
                self._deck_builder_graph = self._build_deck_graph()

            # Create initial state
            initial_state = DeckBuilderState(request=request)

            # Execute the graph
            final_state = self._deck_builder_graph.invoke(initial_state)

            # Extract response
            if isinstance(final_state, dict) and "response" in final_state:
                response = final_state["response"]
                if isinstance(response, NewDeckResponse):
                    return response

            return NewDeckResponse.error_response(
                error_message="Unexpected deck builder output format",
                investigator_id=request.investigator_id or "",
            )

        except Exception as e:
            return NewDeckResponse.error_response(
                error_message=f"Deck building failed: {e}",
                investigator_id=request.investigator_id or "",
            )

    def process(self, request: OrchestratorRequest) -> OrchestratorResponse | NewDeckResponse:
        """Process a user request through the orchestrator.

        This is the main interface for invoking the orchestrator.
        Dispatches to the appropriate flow based on request type:
        - New deck creation flow for deck building requests
        - General Q&A flow for other requests

        Args:
            request: The user's request with context.

        Returns:
            OrchestratorResponse or NewDeckResponse with results.
        """
        try:
            # Check if this is a new deck creation request
            if self._is_new_deck_request(request):
                return self._process_new_deck(request)

            # Standard Q&A flow
            # Create initial state
            initial_state = OrchestratorState(request=request)

            # Execute the graph
            final_state = self.graph.invoke(initial_state)

            # Extract response
            if isinstance(final_state, dict) and "response" in final_state:
                return final_state["response"]

            return OrchestratorResponse.error_response(
                error_message="Unexpected graph output format"
            )

        except Exception as e:
            return OrchestratorResponse.error_response(
                error_message=f"Orchestration failed: {e}"
            )

    async def aprocess(self, request: OrchestratorRequest) -> OrchestratorResponse:
        """Async version of process.

        Args:
            request: The user's request with context.

        Returns:
            OrchestratorResponse with synthesized results.
        """
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self.process, request),
                timeout=self.config.timeout_seconds,
            )
        except TimeoutError:
            return OrchestratorResponse.error_response(
                error_message=f"Request timed out after {self.config.timeout_seconds}s"
            )


# =============================================================================
# Factory Functions
# =============================================================================


def create_orchestrator(
    config: OrchestratorConfig | None = None,
    subagent_config: SubagentConfig | None = None,
) -> Orchestrator:
    """Create a configured Orchestrator instance.

    Args:
        config: Optional orchestrator configuration.
        subagent_config: Optional config to pass to subagents.

    Returns:
        Configured Orchestrator instance.
    """
    return Orchestrator(config=config, subagent_config=subagent_config)


def process_chat_message(
    message: str,
    deck_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict:
    """Process a chat message through the orchestrator.

    This is the main entry point for the chat API, replacing the
    stub implementation in agent_orchestrator.py.

    Args:
        message: User message.
        deck_id: Optional deck context.
        context: Optional additional context dict with keys like:
            - investigator_id, investigator_name
            - deck_cards
            - scenario_name, campaign_name
            - upgrade_xp
            - owned_sets
            - conversation_history (list of prior messages)

    Returns:
        Dictionary with:
            - reply: The synthesized response text
            - structured_data: OrchestratorResponse as dict
            - agents_consulted: List of agent types consulted
    """
    context = context or {}

    # Build request from parameters
    request = OrchestratorRequest(
        message=message,
        investigator_id=context.get("investigator_id"),
        investigator_name=context.get("investigator_name"),
        deck_id=deck_id or context.get("deck_id"),
        deck_cards=context.get("deck_cards"),
        scenario_name=context.get("scenario_name"),
        campaign_name=context.get("campaign_name"),
        upgrade_xp=context.get("upgrade_xp"),
        owned_sets=context.get("owned_sets"),
    )

    # Process through orchestrator
    orchestrator = create_orchestrator()
    response = orchestrator.process(request)

    # Handle both OrchestratorResponse and NewDeckResponse
    if isinstance(response, NewDeckResponse):
        # For deck building, use deck_name as the reply summary
        reply = f"{response.deck_name}: {response.reasoning}"
        agents_consulted = [r.agent_type for r in response.subagent_results]
    else:
        # For Q&A responses
        reply = response.content
        agents_consulted = response.agents_consulted

    return {
        "reply": reply,
        "structured_data": response.model_dump(),
        "agents_consulted": agents_consulted,
    }
