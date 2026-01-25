"""Subagent infrastructure for the Arkham Assistant.

This package provides the base subagent pattern and implementations
for specialized AI agents that handle specific aspects of deckbuilding
assistance.

Subagent Types:
- rules: Deckbuilding rules and card legality (with hybrid retrieval)
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
    # Basic implementations
    RulesSubagent,
    StateSubagent,
    ActionSpaceSubagent,
    ScenarioSubagent,
    # Factory function
    create_subagent,
)

from backend.services.subagents.rules_agent import (
    # Enhanced RulesAgent with hybrid retrieval
    RulesAgent,
    RulesQuery,
    RulesResponse,
    RulesRetriever,
    create_rules_agent,
)

__all__ = [
    # Base classes and exceptions
    "BaseSubagent",
    "SubagentConfig",
    "SubagentError",
    "SubagentTimeoutError",
    # Basic implementations
    "RulesSubagent",
    "StateSubagent",
    "ActionSpaceSubagent",
    "ScenarioSubagent",
    # Enhanced RulesAgent with hybrid retrieval
    "RulesAgent",
    "RulesQuery",
    "RulesResponse",
    "RulesRetriever",
    # Factory functions
    "create_subagent",
    "create_rules_agent",
]
