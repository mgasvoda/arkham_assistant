"""AI agent orchestration with LLM."""

from typing import Optional


def process_chat_message(
    message: str,
    deck_id: Optional[str] = None,
    context: Optional[list[dict]] = None,
) -> dict:
    """Process a chat message through the AI agent.

    Args:
        message: User message
        deck_id: Optional deck context
        context: Optional conversation history

    Returns:
        Dictionary with reply, structured data, and tool calls
    """
    # TODO: Implement LLM orchestration with tool calling
    return {
        "reply": "AI agent not yet implemented",
        "structured_data": None,
        "tool_calls": [],
    }

