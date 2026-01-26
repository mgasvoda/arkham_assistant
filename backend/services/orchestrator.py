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
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from backend.models.subagent_models import SubagentMetadata, SubagentResponse
from backend.services.llm_config import get_llm_config
from backend.services.prompts import format_orchestrator_prompt
from backend.services.subagents import (
    ActionSpaceAgent,
    ActionSpaceQuery,
    ActionSpaceResponse,
    RulesAgent,
    RulesQuery,
    RulesResponse,
    ScenarioAgent,
    ScenarioQuery,
    ScenarioResponse,
    StateAgent,
    StateQuery,
    StateResponse,
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
    ) -> "OrchestratorResponse":
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
                # StateAgent needs deck_cards in context
                state_context = dict(context)
                if request.deck_cards:
                    state_context["deck_cards"] = request.deck_cards
                response = subagent.query(query, state_context)
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

    def process(self, request: OrchestratorRequest) -> OrchestratorResponse:
        """Process a user request through the orchestrator.

        This is the main interface for invoking the orchestrator.

        Args:
            request: The user's request with context.

        Returns:
            OrchestratorResponse with synthesized results.
        """
        try:
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

    return {
        "reply": response.content,
        "structured_data": response.model_dump(),
        "agents_consulted": response.agents_consulted,
    }
