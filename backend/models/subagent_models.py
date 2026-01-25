"""Pydantic response models for subagents.

This module defines the structured response schemas that all subagents
use to return their results. Using Pydantic models ensures type safety
and enables LangChain's structured output parsing.
"""

from typing import Any

from pydantic import BaseModel, Field


class SubagentMetadata(BaseModel):
    """Agent-specific metadata attached to responses.

    This flexible schema allows each subagent type to include
    relevant metadata specific to its domain.
    """

    agent_type: str = Field(
        description="The type of subagent that generated this response"
    )
    query_type: str | None = Field(
        default=None,
        description="The specific type of query that was processed"
    )
    context_used: dict[str, Any] = Field(
        default_factory=dict,
        description="Context parameters that were available during processing"
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional agent-specific metadata"
    )


class SubagentResponse(BaseModel):
    """Structured response from a subagent.

    All subagents return their results using this schema, enabling
    consistent handling by the orchestrator and typed access to
    response components.

    Attributes:
        content: The main response content from the subagent.
        confidence: A score from 0-1 indicating how confident the
            subagent is in its response. Lower confidence may indicate
            ambiguous queries or incomplete information.
        sources: References used to generate the response, such as
            rule citations, card names, or scenario details.
        metadata: Agent-specific metadata with additional context
            about how the response was generated.
    """

    content: str = Field(
        description="Main response content from the subagent"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score from 0-1"
    )
    sources: list[str] = Field(
        default_factory=list,
        description="References used (rules, cards, scenarios, etc.)"
    )
    metadata: SubagentMetadata = Field(
        description="Agent-specific metadata"
    )

    @classmethod
    def error_response(
        cls,
        error_message: str,
        agent_type: str,
        confidence: float = 0.0,
    ) -> "SubagentResponse":
        """Create an error response for graceful degradation.

        Args:
            error_message: Description of the error that occurred.
            agent_type: The type of subagent that encountered the error.
            confidence: Confidence score (typically 0 for errors).

        Returns:
            A SubagentResponse indicating an error occurred.
        """
        return cls(
            content=error_message,
            confidence=confidence,
            sources=[],
            metadata=SubagentMetadata(
                agent_type=agent_type,
                query_type="error",
                extra={"error": True},
            ),
        )
