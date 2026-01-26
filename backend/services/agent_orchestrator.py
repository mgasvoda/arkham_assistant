"""AI agent orchestration with LLM.

This module provides the main entry point for chat message processing.
It delegates to the orchestrator module for the actual implementation.

This file is kept for backward compatibility with existing imports.
"""

from typing import Any, Optional

from backend.services.orchestrator import (
    Orchestrator,
    OrchestratorConfig,
    OrchestratorRequest,
    OrchestratorResponse,
    SubagentResult,
    SubagentType,
    create_orchestrator,
    process_chat_message,
)

# Re-export for backward compatibility
__all__ = [
    "Orchestrator",
    "OrchestratorConfig",
    "OrchestratorRequest",
    "OrchestratorResponse",
    "SubagentResult",
    "SubagentType",
    "create_orchestrator",
    "process_chat_message",
]
