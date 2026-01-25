"""Pydantic response models for subagents.

This module defines the structured response schemas that all subagents
use to return their results. Using Pydantic models ensures type safety
and enables LangChain's structured output parsing.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, Field


# Type variable for generic class methods
T = TypeVar("T", bound="SubagentResponse")


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
    def _get_error_defaults(cls) -> dict[str, Any]:
        """Get default field values for error responses.

        Override in subclasses to provide domain-specific default values
        for custom fields when creating error responses.

        Returns:
            Dict of field_name -> default_value for error responses.

        Example:
            >>> class RulesResponse(SubagentResponse):
            ...     rule_text: str = ""
            ...
            ...     @classmethod
            ...     def _get_error_defaults(cls) -> dict[str, Any]:
            ...         return {"rule_text": ""}
        """
        return {}

    @classmethod
    def error_response(
        cls: type[T],
        error_message: str,
        agent_type: str,
        confidence: float = 0.0,
    ) -> T:
        """Create an error response for graceful degradation.

        This method automatically handles custom fields in subclasses
        by calling _get_error_defaults() to get appropriate default values.

        Args:
            error_message: Description of the error that occurred.
            agent_type: The type of subagent that encountered the error.
            confidence: Confidence score (typically 0 for errors).

        Returns:
            A SubagentResponse (or subclass) indicating an error occurred.
        """
        defaults = cls._get_error_defaults()
        return cls(
            content=error_message,
            confidence=confidence,
            sources=[],
            metadata=SubagentMetadata(
                agent_type=agent_type,
                query_type="error",
                extra={"error": True},
            ),
            **defaults,
        )

    @classmethod
    def from_base_response(
        cls: type[T],
        base_response: SubagentResponse,
        **extra_fields: Any,
    ) -> T:
        """Create a subclass instance from a base SubagentResponse.

        This is useful when an LLM returns a base SubagentResponse and
        you need to convert it to a specialized response type with
        additional fields.

        Args:
            base_response: The base response to extend.
            **extra_fields: Additional fields for the subclass.

        Returns:
            Instance of the subclass with all fields populated.

        Example:
            >>> rules_response = RulesResponse.from_base_response(
            ...     base_response,
            ...     rule_text="According to the rules...",
            ...     interpretation="This means...",
            ... )
        """
        return cls(
            content=base_response.content,
            confidence=base_response.confidence,
            sources=base_response.sources,
            metadata=base_response.metadata,
            **extra_fields,
        )
