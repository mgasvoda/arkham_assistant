"""Subagent infrastructure for the Arkham Assistant.

This package provides the base subagent pattern and implementations
for specialized AI agents that handle specific aspects of deckbuilding
assistance.

Subagent Types:
- rules: Deckbuilding rules and card legality
- state: Deck composition analysis
- action_space: Card search and filtering
- scenario: Scenario threats and preparation
"""

from backend.services.subagents.base import (
    # Base classes and exceptions
    BaseSubagent,
    SubagentConfig,
    SubagentError,
    SubagentTimeoutError,
    # Concrete implementations
    RulesSubagent,
    StateSubagent,
    ActionSpaceSubagent,
    ScenarioSubagent,
    # Factory function
    create_subagent,
)
from backend.services.subagents.action_space_agent import (
    ActionSpaceAgent,
    ActionSpaceQuery,
    ActionSpaceResponse,
    CardCandidate,
    create_action_space_agent,
)

__all__ = [
    # Base classes and exceptions
    "BaseSubagent",
    "SubagentConfig",
    "SubagentError",
    "SubagentTimeoutError",
    # Concrete implementations
    "RulesSubagent",
    "StateSubagent",
    "ActionSpaceSubagent",
    "ScenarioSubagent",
    # ActionSpaceAgent (full implementation)
    "ActionSpaceAgent",
    "ActionSpaceQuery",
    "ActionSpaceResponse",
    "CardCandidate",
    "create_action_space_agent",
    # Factory function
    "create_subagent",
]
