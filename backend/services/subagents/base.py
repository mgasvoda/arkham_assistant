"""Base subagent pattern using LangGraph.

This module provides the foundational infrastructure for all subagents,
including configuration, error handling, and the abstract base class
that concrete subagent implementations extend.

The subagent pattern uses LangGraph to execute a simple single-node
graph that invokes an LLM with a specialized system prompt and returns
structured responses.
"""

import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from backend.models.subagent_models import SubagentMetadata, SubagentResponse
from backend.services.llm_config import get_llm_config
from backend.services.prompts import AGENT_TYPES, format_subagent_prompt


# =============================================================================
# Exceptions
# =============================================================================


class SubagentError(Exception):
    """Base exception for subagent errors."""

    pass


class SubagentTimeoutError(SubagentError):
    """Raised when a subagent query times out."""

    pass


# =============================================================================
# Configuration
# =============================================================================


@dataclass(frozen=True)
class SubagentConfig:
    """Configuration for subagent execution.

    Attributes:
        temperature: LLM sampling temperature (0.0 = deterministic).
        max_tokens: Maximum tokens in the response.
        timeout_seconds: Maximum time to wait for a response.
        retry_attempts: Number of retries on transient failures.
    """

    temperature: float = 0.0
    max_tokens: int = 2048
    timeout_seconds: float = 30.0
    retry_attempts: int = 2

    @classmethod
    def from_env(cls) -> "SubagentConfig":
        """Create config from environment variables.

        Environment variables (all optional with defaults):
            SUBAGENT_TEMPERATURE: LLM temperature (default: 0.0)
            SUBAGENT_MAX_TOKENS: Max response tokens (default: 2048)
            SUBAGENT_TIMEOUT: Timeout in seconds (default: 30.0)
            SUBAGENT_RETRY_ATTEMPTS: Retry count (default: 2)

        Returns:
            SubagentConfig with values from environment.
        """
        return cls(
            temperature=float(os.getenv("SUBAGENT_TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("SUBAGENT_MAX_TOKENS", "2048")),
            timeout_seconds=float(os.getenv("SUBAGENT_TIMEOUT", "30.0")),
            retry_attempts=int(os.getenv("SUBAGENT_RETRY_ATTEMPTS", "2")),
        )


# =============================================================================
# LangGraph State
# =============================================================================


class SubagentState(BaseModel):
    """State for the subagent LangGraph execution.

    This state flows through the graph nodes, accumulating
    information as the subagent processes a query.
    """

    # Input
    query: str
    context: dict[str, Any] = {}

    # Processing
    system_prompt: str = ""
    error: str | None = None

    # Output
    response: SubagentResponse | None = None


# =============================================================================
# Base Subagent
# =============================================================================


class BaseSubagent(ABC):
    """Abstract base class for all subagents.

    Subagents are specialized AI agents that handle specific aspects
    of deckbuilding assistance. Each subagent:

    1. Receives a query and context from the orchestrator
    2. Uses a specialized system prompt for its domain
    3. Invokes an LLM to process the query
    4. Returns a structured response

    The execution uses LangGraph to provide a consistent pattern
    for all subagent implementations.

    Attributes:
        agent_type: The type identifier for this subagent.
        config: Configuration settings for execution.
        llm: The LangChain chat model instance.
        graph: The compiled LangGraph for execution.
    """

    def __init__(
        self,
        agent_type: Literal["rules", "state", "action_space", "scenario"],
        config: SubagentConfig | None = None,
    ) -> None:
        """Initialize the subagent.

        Args:
            agent_type: The type of subagent (must be a valid AGENT_TYPES value).
            config: Optional configuration. If not provided, loads from environment.

        Raises:
            ValueError: If agent_type is not recognized.
        """
        if agent_type not in AGENT_TYPES:
            raise ValueError(
                f"Unknown agent type: '{agent_type}'. "
                f"Must be one of: {AGENT_TYPES}"
            )

        self.agent_type = agent_type
        self.config = config or SubagentConfig.from_env()
        self.llm = self._create_llm()
        self.graph = self._build_graph()

    def _create_llm(self) -> ChatOpenAI:
        """Create the LLM instance for this subagent.

        Returns:
            Configured ChatOpenAI instance.

        Raises:
            ValueError: If OPENAI_API_KEY is not set.
        """
        llm_config = get_llm_config()
        if not llm_config.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        return ChatOpenAI(
            model=llm_config.subagent_model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            api_key=llm_config.api_key,
        )

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph for subagent execution.

        The graph has a simple linear structure:
        1. prepare_prompt: Format the system prompt with context
        2. invoke_llm: Call the LLM and parse the response
        3. END

        Returns:
            Compiled StateGraph ready for execution.
        """
        # Define the graph
        graph = StateGraph(SubagentState)

        # Add nodes
        graph.add_node("prepare_prompt", self._prepare_prompt_node)
        graph.add_node("invoke_llm", self._invoke_llm_node)

        # Define edges
        graph.set_entry_point("prepare_prompt")
        graph.add_edge("prepare_prompt", "invoke_llm")
        graph.add_edge("invoke_llm", END)

        return graph.compile()

    def _prepare_prompt_node(self, state: SubagentState) -> dict[str, Any]:
        """Prepare the system prompt with context.

        This node formats the subagent-specific system prompt using
        the format_subagent_prompt function from prompts.py.

        Args:
            state: Current graph state with context.

        Returns:
            State update with formatted system prompt.
        """
        try:
            system_prompt = format_subagent_prompt(
                agent_type=self.agent_type,
                investigator_name=state.context.get("investigator_name"),
                deck_id=state.context.get("deck_id"),
                deck_summary=state.context.get("deck_summary"),
                scenario_name=state.context.get("scenario_name"),
                upgrade_xp=state.context.get("upgrade_xp"),
                campaign_name=state.context.get("campaign_name"),
                owned_sets=state.context.get("owned_sets"),
            )
            return {"system_prompt": system_prompt}
        except Exception as e:
            return {"error": f"Failed to prepare prompt: {e}"}

    def _invoke_llm_node(self, state: SubagentState) -> dict[str, Any]:
        """Invoke the LLM and create the response.

        This node calls the LLM with the prepared system prompt
        and user query, then wraps the result in a SubagentResponse.

        Note: LLM invocation errors are re-raised to allow retry logic
        in the query() method to handle them. Only prompt preparation
        errors (from previous nodes) are converted to error responses.

        Args:
            state: Current graph state with prompt and query.

        Returns:
            State update with SubagentResponse.

        Raises:
            SubagentError: If LLM invocation fails (allows retry).
        """
        # Check for errors from previous nodes (these don't retry)
        if state.error:
            return {
                "response": SubagentResponse.error_response(
                    error_message=state.error,
                    agent_type=self.agent_type,
                )
            }

        # Build messages
        messages = [
            SystemMessage(content=state.system_prompt),
            HumanMessage(content=state.query),
        ]

        # Invoke LLM - let exceptions propagate for retry handling
        result = self.llm.invoke(messages)

        # Extract content
        content = (
            result.content
            if isinstance(result.content, str)
            else str(result.content)
        )

        # Build response
        response = SubagentResponse(
            content=content,
            confidence=self._calculate_confidence(content, state),
            sources=self._extract_sources(content, state),
            metadata=SubagentMetadata(
                agent_type=self.agent_type,
                query_type=self._determine_query_type(state.query),
                context_used={
                    k: v for k, v in state.context.items() if v is not None
                },
            ),
        )
        return {"response": response}

    def query(self, query: str, context: dict[str, Any] | None = None) -> SubagentResponse:
        """Execute a query against this subagent.

        This is the main interface for invoking a subagent. The query
        is processed through the LangGraph with the provided context,
        and a structured response is returned.

        Args:
            query: The user's question or request.
            context: Optional context dict with keys like:
                - investigator_name: Name of the investigator
                - deck_id: ID of the current deck
                - deck_summary: Pre-computed deck summary
                - scenario_name: Name of the scenario
                - upgrade_xp: Available XP for upgrades
                - campaign_name: Name of the campaign
                - owned_sets: List of owned expansion names

        Returns:
            SubagentResponse with the query result.

        Raises:
            SubagentTimeoutError: If the query times out.
            SubagentError: For other execution errors.
        """
        context = context or {}

        # Create initial state
        initial_state = SubagentState(query=query, context=context)

        # Execute with retry logic
        last_error: Exception | None = None
        for attempt in range(self.config.retry_attempts + 1):
            try:
                # Execute the graph
                final_state = self.graph.invoke(initial_state)

                # Extract response
                if isinstance(final_state, dict) and "response" in final_state:
                    response = final_state["response"]
                    # Check if this is an error response that should not retry
                    # (e.g., prompt preparation errors)
                    if (
                        response.metadata.query_type == "error"
                        and "prompt" in response.content.lower()
                    ):
                        return response
                    return response

                # Handle unexpected state format
                return SubagentResponse.error_response(
                    error_message="Unexpected graph output format",
                    agent_type=self.agent_type,
                )

            except TimeoutError:
                last_error = SubagentTimeoutError(
                    f"Query timed out after {self.config.timeout_seconds}s"
                )
            except Exception as e:
                last_error = SubagentError(f"LLM invocation failed: {e}")

        # All retries exhausted - return error response
        return SubagentResponse.error_response(
            error_message=str(last_error) if last_error else "Unknown error",
            agent_type=self.agent_type,
        )

    async def aquery(
        self, query: str, context: dict[str, Any] | None = None
    ) -> SubagentResponse:
        """Async version of query.

        Executes the query asynchronously with timeout handling.

        Args:
            query: The user's question or request.
            context: Optional context dict.

        Returns:
            SubagentResponse with the query result.

        Raises:
            SubagentTimeoutError: If the query times out.
        """
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self.query, query, context),
                timeout=self.config.timeout_seconds,
            )
        except asyncio.TimeoutError:
            return SubagentResponse.error_response(
                error_message=f"Query timed out after {self.config.timeout_seconds}s",
                agent_type=self.agent_type,
            )

    # =========================================================================
    # Abstract methods for subclass customization
    # =========================================================================

    @abstractmethod
    def _calculate_confidence(
        self, content: str, state: SubagentState
    ) -> float:
        """Calculate confidence score for the response.

        Subclasses should implement domain-specific confidence
        calculation based on the response content and query context.

        Args:
            content: The LLM response content.
            state: The current graph state.

        Returns:
            Confidence score from 0.0 to 1.0.
        """
        pass

    @abstractmethod
    def _extract_sources(
        self, content: str, state: SubagentState
    ) -> list[str]:
        """Extract source references from the response.

        Subclasses should implement domain-specific source extraction
        to identify rules, cards, scenarios, etc. mentioned in the response.

        Args:
            content: The LLM response content.
            state: The current graph state.

        Returns:
            List of source references.
        """
        pass

    @abstractmethod
    def _determine_query_type(self, query: str) -> str:
        """Determine the type of query being processed.

        Subclasses should implement domain-specific query classification
        to categorize what kind of request is being handled.

        Args:
            query: The user's query string.

        Returns:
            String identifier for the query type.
        """
        pass


# =============================================================================
# Concrete Subagent Implementations (Base versions with default behavior)
# =============================================================================


class RulesSubagent(BaseSubagent):
    """Subagent for deckbuilding rules and card legality questions."""

    def __init__(self, config: SubagentConfig | None = None) -> None:
        super().__init__(agent_type="rules", config=config)

    def _calculate_confidence(
        self, content: str, state: SubagentState
    ) -> float:
        """Calculate confidence for rules responses.

        Higher confidence when the response contains definitive language
        and rule citations.
        """
        content_lower = content.lower()

        # High confidence indicators
        if any(
            phrase in content_lower
            for phrase in ["according to the rules", "the rules state", "is legal", "is not legal"]
        ):
            return 0.9

        # Medium confidence
        if any(
            phrase in content_lower
            for phrase in ["can include", "cannot include", "restricted to"]
        ):
            return 0.75

        # Default confidence
        return 0.6

    def _extract_sources(
        self, content: str, state: SubagentState
    ) -> list[str]:
        """Extract rule and card references from the response."""
        sources = []

        # Add investigator as source if mentioned
        investigator = state.context.get("investigator_name")
        if investigator and investigator.lower() in content.lower():
            sources.append(f"Investigator: {investigator}")

        # Look for rule-related keywords
        if "taboo" in content.lower():
            sources.append("Taboo List")
        if "signature" in content.lower():
            sources.append("Signature Card Rules")

        return sources

    def _determine_query_type(self, query: str) -> str:
        """Classify the type of rules query."""
        query_lower = query.lower()

        if any(word in query_lower for word in ["legal", "include", "can "]):
            return "legality_check"
        if any(word in query_lower for word in ["xp", "experience", "upgrade"]):
            return "xp_rules"
        if "taboo" in query_lower:
            return "taboo_check"

        return "general_rules"


class StateSubagent(BaseSubagent):
    """Subagent for deck composition and state analysis."""

    def __init__(self, config: SubagentConfig | None = None) -> None:
        super().__init__(agent_type="state", config=config)

    def _calculate_confidence(
        self, content: str, state: SubagentState
    ) -> float:
        """Calculate confidence for state analysis responses.

        Higher confidence when the response includes specific numbers
        and quantitative analysis.
        """
        # Check for quantitative language
        has_numbers = any(char.isdigit() for char in content)
        has_percentages = "%" in content

        if has_numbers and has_percentages:
            return 0.9
        if has_numbers:
            return 0.75

        return 0.6

    def _extract_sources(
        self, content: str, state: SubagentState
    ) -> list[str]:
        """Extract deck and card references from the response."""
        sources = []

        deck_id = state.context.get("deck_id")
        if deck_id:
            sources.append(f"Deck: {deck_id}")

        deck_summary = state.context.get("deck_summary")
        if deck_summary and deck_summary.get("deck_name"):
            sources.append(f"Deck Name: {deck_summary['deck_name']}")

        return sources

    def _determine_query_type(self, query: str) -> str:
        """Classify the type of state analysis query."""
        query_lower = query.lower()

        if any(word in query_lower for word in ["curve", "cost", "resource"]):
            return "resource_curve"
        if any(word in query_lower for word in ["gap", "missing", "need"]):
            return "coverage_gaps"
        if any(word in query_lower for word in ["redundan", "backup", "duplicate"]):
            return "redundancy"

        return "full_analysis"


class ActionSpaceSubagent(BaseSubagent):
    """Subagent for card search and filtering."""

    def __init__(self, config: SubagentConfig | None = None) -> None:
        super().__init__(agent_type="action_space", config=config)

    def _calculate_confidence(
        self, content: str, state: SubagentState
    ) -> float:
        """Calculate confidence for card search responses.

        Higher confidence when specific cards are mentioned.
        """
        # Check for card list indicators
        content_lower = content.lower()

        if any(
            phrase in content_lower
            for phrase in ["recommend", "suggest", "consider"]
        ):
            return 0.85

        # Multiple cards mentioned
        if content.count("(") >= 3:  # Card names often have (level X)
            return 0.8

        return 0.65

    def _extract_sources(
        self, content: str, state: SubagentState
    ) -> list[str]:
        """Extract card and filter references from the response."""
        sources = []

        investigator = state.context.get("investigator_name")
        if investigator:
            sources.append(f"Card pool: {investigator}")

        owned_sets = state.context.get("owned_sets")
        if owned_sets:
            sources.append(f"Owned sets: {len(owned_sets)} sets")

        return sources

    def _determine_query_type(self, query: str) -> str:
        """Classify the type of card search query."""
        query_lower = query.lower()

        if any(word in query_lower for word in ["upgrade", "replace", "better"]):
            return "upgrade_search"
        if any(word in query_lower for word in ["synerg", "combo", "work with"]):
            return "synergy_search"
        if any(word in query_lower for word in ["find", "search", "look for"]):
            return "general_search"

        return "card_recommendation"


class ScenarioSubagent(BaseSubagent):
    """Subagent for scenario analysis and preparation."""

    def __init__(self, config: SubagentConfig | None = None) -> None:
        super().__init__(agent_type="scenario", config=config)

    def _calculate_confidence(
        self, content: str, state: SubagentState
    ) -> float:
        """Calculate confidence for scenario analysis responses.

        Higher confidence when specific threats and strategies
        are mentioned.
        """
        content_lower = content.lower()

        # Specific scenario knowledge indicators
        if any(
            phrase in content_lower
            for phrase in ["encounter deck", "agenda", "act", "boss"]
        ):
            return 0.85

        if any(
            phrase in content_lower
            for phrase in ["treachery", "enemy", "location"]
        ):
            return 0.75

        return 0.6

    def _extract_sources(
        self, content: str, state: SubagentState
    ) -> list[str]:
        """Extract scenario references from the response."""
        sources = []

        scenario_name = state.context.get("scenario_name")
        if scenario_name:
            sources.append(f"Scenario: {scenario_name}")

        campaign_name = state.context.get("campaign_name")
        if campaign_name:
            sources.append(f"Campaign: {campaign_name}")

        return sources

    def _determine_query_type(self, query: str) -> str:
        """Classify the type of scenario query."""
        query_lower = query.lower()

        if any(word in query_lower for word in ["threat", "enemy", "danger"]):
            return "threat_analysis"
        if any(word in query_lower for word in ["prepar", "ready", "need"]):
            return "preparation"
        if any(word in query_lower for word in ["strateg", "approach", "how to"]):
            return "strategy"

        return "full_analysis"


# =============================================================================
# Factory Function
# =============================================================================


def create_subagent(
    agent_type: Literal["rules", "state", "action_space", "scenario"],
    config: SubagentConfig | None = None,
) -> BaseSubagent:
    """Factory function to create a subagent of the specified type.

    Args:
        agent_type: The type of subagent to create.
        config: Optional configuration for the subagent.

    Returns:
        A configured subagent instance.

    Raises:
        ValueError: If agent_type is not recognized.
    """
    subagent_classes = {
        "rules": RulesSubagent,
        "state": StateSubagent,
        "action_space": ActionSpaceSubagent,
        "scenario": ScenarioSubagent,
    }

    if agent_type not in subagent_classes:
        raise ValueError(
            f"Unknown agent type: '{agent_type}'. "
            f"Must be one of: {list(subagent_classes.keys())}"
        )

    return subagent_classes[agent_type](config=config)
