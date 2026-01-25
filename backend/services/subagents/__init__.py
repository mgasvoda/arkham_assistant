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
    # Factory function
    "create_subagent",
]
