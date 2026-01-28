"""AI chat API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.orchestrator import process_chat_message

router = APIRouter()


class ChatMessage(BaseModel):
    """Chat message model for orchestrator requests.

    Attributes:
        message: The user's message/question.
        deck_id: Optional deck ID for context.
        investigator_id: Optional investigator ID for context.
        investigator_name: Optional investigator name for display.
        scenario_name: Optional scenario being prepared for.
        upgrade_xp: Optional available XP for upgrades.
        context: Optional additional context dict.
    """

    message: str = Field(description="The user's message or question")
    deck_id: str | None = Field(
        default=None,
        description="Deck ID for context"
    )
    investigator_id: str | None = Field(
        default=None,
        description="Investigator ID for context"
    )
    investigator_name: str | None = Field(
        default=None,
        description="Investigator name for display"
    )
    scenario_name: str | None = Field(
        default=None,
        description="Scenario being prepared for"
    )
    upgrade_xp: int | None = Field(
        default=None,
        ge=0,
        description="Available XP for upgrades"
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Additional context dict"
    )


class ChatResponse(BaseModel):
    """Response from the chat endpoint.

    Attributes:
        reply: The main response text.
        structured_data: Full orchestrator response as dict.
        agents_consulted: List of agent types that were consulted.
    """

    reply: str = Field(description="The main response text")
    structured_data: dict[str, Any] = Field(
        description="Full orchestrator response"
    )
    agents_consulted: list[str] = Field(
        default_factory=list,
        description="Agent types consulted"
    )


@router.post("/", response_model=ChatResponse)
async def chat(message: ChatMessage) -> ChatResponse:
    """Send a message to the AI agent.

    Processes the message through the orchestrator, which will route
    to appropriate subagents (Rules, State, ActionSpace, Scenario)
    based on the query content and context.

    For deck building requests (e.g., "Build me a combat deck"),
    returns a NewDeckResponse with the complete deck list.

    For Q&A requests, returns an OrchestratorResponse with
    synthesized insights from relevant subagents.

    Args:
        message: The chat message with optional context.

    Returns:
        ChatResponse with reply text and structured data.

    Raises:
        HTTPException: 500 if orchestration fails.
    """
    # Build context dict from ChatMessage fields
    context = message.context.copy() if message.context else {}

    # Add explicit fields to context
    if message.investigator_id:
        context["investigator_id"] = message.investigator_id
    if message.investigator_name:
        context["investigator_name"] = message.investigator_name
    if message.scenario_name:
        context["scenario_name"] = message.scenario_name
    if message.upgrade_xp is not None:
        context["upgrade_xp"] = message.upgrade_xp

    try:
        result = process_chat_message(
            message=message.message,
            deck_id=message.deck_id,
            context=context,
        )

        return ChatResponse(
            reply=result["reply"],
            structured_data=result["structured_data"],
            agents_consulted=result.get("agents_consulted", []),
        )

    except ValueError as e:
        # Configuration errors (e.g., missing API key)
        raise HTTPException(
            status_code=500,
            detail=f"Configuration error: {e}"
        )
    except Exception as e:
        # Unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Orchestration failed: {e}"
        )

