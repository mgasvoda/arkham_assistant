"""AI chat API endpoints."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ChatMessage(BaseModel):
    """Chat message model."""

    deck_id: Optional[str] = None
    message: str
    context: Optional[list[dict]] = None


@router.post("/")
async def chat(message: ChatMessage):
    """Send a message to the AI agent."""
    # TODO: Implement AI agent chat
    return {
        "reply": "AI agent not yet implemented. Echo: " + message.message,
        "structured_data": None,
        "tool_calls": [],
    }

