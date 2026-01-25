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

from backend.services.subagents.action_space_agent import (
    ActionSpaceAgent,
    ActionSpaceQuery,
    ActionSpaceResponse,
    CardCandidate,
    create_action_space_agent,
)
from backend.services.subagents.base import (
    ActionSpaceSubagent,
    # Base classes and exceptions
    BaseSubagent,
    # Basic implementations
    RulesSubagent,
    ScenarioSubagent,
    StateSubagent,
    SubagentConfig,
    SubagentError,
    SubagentTimeoutError,
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
from backend.services.subagents.scenario_agent import (
    Priority,
    # ScenarioAgent with scenario data integration
    ScenarioAgent,
    ScenarioQuery,
    ScenarioResponse,
    ThreatProfile,
    create_scenario_agent,
)
from backend.services.subagents.state_agent import (
    # StateAgent for deck composition analysis
    StateAgent,
    StateQuery,
    StateResponse,
    SynergyInfo,
    create_state_agent,
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
    # ActionSpaceAgent (full implementation)
    "ActionSpaceAgent",
    "ActionSpaceQuery",
    "ActionSpaceResponse",
    "CardCandidate",
    "create_action_space_agent",
    # Enhanced RulesAgent with hybrid retrieval
    "RulesAgent",
    "RulesQuery",
    "RulesResponse",
    "RulesRetriever",
    # Caching layer
    "CacheConfig",
    "CacheEntry",
    "CacheMetrics",
    "SubagentCache",
    "get_subagent_cache",
    "reset_subagent_cache",
    # ScenarioAgent (full implementation)
    "ScenarioAgent",
    "ScenarioQuery",
    "ScenarioResponse",
    "ThreatProfile",
    "Priority",
    "create_scenario_agent",
    # StateAgent (full implementation)
    "StateAgent",
    "StateQuery",
    "StateResponse",
    "SynergyInfo",
    "create_state_agent",
    # Factory functions
    "create_subagent",
    "create_rules_agent",
]
