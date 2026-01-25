"""ScenarioAgent for scenario threat analysis and preparation recommendations.

This module implements the ScenarioAgent subagent that analyzes upcoming scenario
threats and recommends preparation priorities. It uses the scenario data from
the scenario loader to provide data-driven recommendations.

The agent handles:
- Identifying key threats in upcoming scenarios
- Categorizing threats (enemies, treacheries, locations, skill tests)
- Recommending preparation priorities
- Suggesting cards that address specific threats
"""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from backend.models.subagent_models import SubagentMetadata, SubagentResponse
from backend.services.scenario_loader import (
    ScenarioData,
    ScenarioLoader,
    get_scenario_loader,
)
from backend.services.subagents.base import (
    BaseSubagent,
    SubagentConfig,
    SubagentState,
)

# =============================================================================
# Input/Output Schemas
# =============================================================================


class ScenarioQuery(BaseModel):
    """Input schema for scenario queries.

    Attributes:
        scenario_id: Scenario identifier (ID or name).
        campaign: Optional campaign context for narrowing search.
        investigator_id: Optional investigator ID for class-specific recommendations.
    """

    scenario_id: str = Field(
        description="Scenario identifier or name"
    )
    campaign: str | None = Field(
        default=None,
        description="Campaign context to help identify scenario"
    )
    investigator_id: str | None = Field(
        default=None,
        description="Investigator ID for class-specific recommendations"
    )


class ThreatProfile(BaseModel):
    """Profile of threats in a scenario.

    Attributes:
        enemy_density: Enemy density level (low, medium, high).
        treachery_types: List of treachery test types present.
        key_skill_tests: Most common skill tests required.
        special_mechanics: Special mechanics in the scenario.
    """

    enemy_density: str = Field(
        description="Enemy density level: low, medium, or high"
    )
    treachery_types: list[str] = Field(
        default_factory=list,
        description="Types of treachery tests present (willpower, agility, etc.)"
    )
    key_skill_tests: list[str] = Field(
        default_factory=list,
        description="Most common skill tests required"
    )
    special_mechanics: list[str] = Field(
        default_factory=list,
        description="Special mechanics in the scenario"
    )


class Priority(BaseModel):
    """A preparation priority for a scenario.

    Attributes:
        capability: The capability needed (e.g., 'willpower icons', 'combat').
        importance: Priority level: critical, important, or nice-to-have.
        reason: Explanation of why this matters for this scenario.
    """

    capability: str = Field(
        description="The capability or card type needed"
    )
    importance: str = Field(
        description="Priority level: critical, important, or nice-to-have"
    )
    reason: str = Field(
        description="Why this matters for this scenario"
    )


class ScenarioResponse(SubagentResponse):
    """Structured response for scenario analysis queries.

    Extends SubagentResponse with scenario-specific fields.

    Attributes:
        scenario_name: Name of the analyzed scenario.
        threat_profile: Categorized threat information.
        preparation_priorities: List of preparation priorities.
        recommended_capabilities: List of recommended card capabilities.
    """

    scenario_name: str = Field(
        default="",
        description="Name of the analyzed scenario"
    )
    threat_profile: ThreatProfile | None = Field(
        default=None,
        description="Categorized threat information"
    )
    preparation_priorities: list[Priority] = Field(
        default_factory=list,
        description="Ordered list of preparation priorities"
    )
    recommended_capabilities: list[str] = Field(
        default_factory=list,
        description="List of recommended card capabilities"
    )

    @classmethod
    def from_base_response(
        cls,
        base_response: SubagentResponse,
        scenario_name: str = "",
        threat_profile: ThreatProfile | None = None,
        preparation_priorities: list[Priority] | None = None,
        recommended_capabilities: list[str] | None = None,
    ) -> "ScenarioResponse":
        """Create a ScenarioResponse from a base SubagentResponse.

        Args:
            base_response: The base response to extend.
            scenario_name: Name of the scenario.
            threat_profile: Threat profile data.
            preparation_priorities: List of priorities.
            recommended_capabilities: List of capabilities.

        Returns:
            ScenarioResponse with all fields populated.
        """
        return cls(
            content=base_response.content,
            confidence=base_response.confidence,
            sources=base_response.sources,
            metadata=base_response.metadata,
            scenario_name=scenario_name,
            threat_profile=threat_profile,
            preparation_priorities=preparation_priorities or [],
            recommended_capabilities=recommended_capabilities or [],
        )

    @classmethod
    def error_response(
        cls,
        error_message: str,
        agent_type: str = "scenario",
        confidence: float = 0.0,
    ) -> "ScenarioResponse":
        """Create an error response for graceful degradation.

        Args:
            error_message: Description of the error.
            agent_type: The agent type (default: "scenario").
            confidence: Confidence score (typically 0 for errors).

        Returns:
            A ScenarioResponse indicating an error occurred.
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
            scenario_name="",
            threat_profile=None,
            preparation_priorities=[],
            recommended_capabilities=[],
        )

    @classmethod
    def unknown_scenario_response(
        cls,
        scenario_query: str,
        agent_type: str = "scenario",
    ) -> "ScenarioResponse":
        """Create a response for unknown scenarios.

        Args:
            scenario_query: The scenario that was queried.
            agent_type: The agent type.

        Returns:
            A ScenarioResponse indicating scenario was not found.
        """
        return cls(
            content=(
                f"Scenario '{scenario_query}' was not found in the database. "
                "Please check the scenario name or try a different search term. "
                "Available campaigns include Night of the Zealot and The Dunwich Legacy."
            ),
            confidence=0.3,
            sources=[],
            metadata=SubagentMetadata(
                agent_type=agent_type,
                query_type="unknown_scenario",
                extra={"scenario_query": scenario_query},
            ),
            scenario_name="",
            threat_profile=None,
            preparation_priorities=[],
            recommended_capabilities=[],
        )


# =============================================================================
# ScenarioAgent Implementation
# =============================================================================


class ScenarioAgent(BaseSubagent):
    """ScenarioAgent for scenario threat analysis and preparation recommendations.

    This agent extends the base subagent pattern with:
    1. Scenario data retrieval from the scenario loader
    2. Threat profile generation based on scenario data
    3. Priority calculation for preparation recommendations
    4. LLM-powered detailed analysis and card suggestions

    The agent handles:
    - Identifying key threats in upcoming scenarios
    - Categorizing threats (enemies, treacheries, mechanics)
    - Recommending preparation priorities
    - Suggesting cards that address specific threats
    """

    # Prompt template for scenario analysis
    SCENARIO_PROMPT_TEMPLATE = """You are the Scenario Agent, a specialist in Arkham Horror LCG \
scenario analysis and preparation.

## Scenario Data

You are analyzing: **{scenario_name}** from *{campaign}*

### Threat Profile
- **Enemy Density**: {enemy_density}
- **Key Skill Tests**: {key_tests}
- **Special Mechanics**: {mechanics}

### Treachery Distribution
{treachery_info}

### Notable Enemies
{enemy_info}

### Scenario Tips from Reference
{tips}

## Your Task

Based on the scenario data above and the user's question, provide specific preparation \
advice. Consider:

1. **What threats are most dangerous** in this scenario
2. **What skills/capabilities** the investigator should prioritize
3. **Specific card types or effects** that counter scenario threats
4. **Tempo considerations** (is this a fast or slow scenario?)

## Response Format

Provide your analysis with:
- **Key Threats**: The most dangerous aspects of this scenario
- **Skill Priorities**: Which skills matter most and why
- **Recommended Cards/Effects**: Types of cards that help (not specific names unless relevant)
- **Strategy Tips**: How to approach the scenario

{context_block}"""

    def __init__(
        self,
        config: SubagentConfig | None = None,
        scenario_loader: ScenarioLoader | None = None,
    ) -> None:
        """Initialize the ScenarioAgent.

        Args:
            config: Optional configuration for the subagent.
            scenario_loader: Optional custom scenario loader.
        """
        super().__init__(agent_type="scenario", config=config)
        self.scenario_loader = scenario_loader or get_scenario_loader()

    def _prepare_prompt_node(self, state: SubagentState) -> dict[str, Any]:
        """Prepare the system prompt with scenario data context.

        This overrides the base implementation to inject scenario data
        into the prompt.

        Args:
            state: Current graph state with query and context.

        Returns:
            State update with formatted system prompt and updated context.
        """
        try:
            # Extract scenario identifier from query or context
            scenario_id = state.context.get("scenario_id") or state.query
            campaign_hint = state.context.get("campaign_name")

            # Try to find the scenario
            scenario = self._find_scenario(scenario_id, campaign_hint)

            if not scenario:
                # Return early with unknown scenario state
                return {
                    "error": f"scenario_not_found:{scenario_id}",
                    "context": {**state.context, "_scenario_not_found": True},
                }

            # Build threat profile
            threat_profile = self._build_threat_profile(scenario)

            # Format scenario information for prompt
            treachery_info = self._format_treachery_info(scenario)
            enemy_info = self._format_enemy_info(scenario)
            tips = self._format_tips(scenario)

            # Build context block
            context_lines = []
            if state.context.get("investigator_name"):
                context_lines.append(
                    f"**Investigator**: {state.context['investigator_name']}"
                )
            if state.context.get("deck_id"):
                context_lines.append(f"**Deck ID**: {state.context['deck_id']}")

            context_block = (
                "## Current Context\n" + "\n".join(context_lines)
                if context_lines
                else ""
            )

            # Format the prompt
            system_prompt = self.SCENARIO_PROMPT_TEMPLATE.format(
                scenario_name=scenario.name,
                campaign=scenario.campaign,
                enemy_density=scenario.enemy_density,
                key_tests=", ".join(scenario.key_tests) or "None specified",
                mechanics=", ".join(scenario.mechanics) or "None specified",
                treachery_info=treachery_info,
                enemy_info=enemy_info,
                tips=tips,
                context_block=context_block,
            )

            # Update context with scenario data
            updated_context = dict(state.context)
            updated_context["_scenario_data"] = scenario
            updated_context["_threat_profile"] = threat_profile

            return {"system_prompt": system_prompt, "context": updated_context}

        except Exception as e:
            return {"error": f"Failed to prepare prompt: {e}"}

    def _invoke_llm_node(self, state: SubagentState) -> dict[str, Any]:
        """Invoke the LLM and create a ScenarioResponse.

        This overrides the base implementation to return a ScenarioResponse
        instead of a generic SubagentResponse.

        Args:
            state: Current graph state with prompt and query.

        Returns:
            State update with ScenarioResponse.
        """
        # Check for scenario not found error
        if state.error and "scenario_not_found" in state.error:
            scenario_query = state.error.split(":")[-1]
            return {"response": ScenarioResponse.unknown_scenario_response(scenario_query)}

        # Check for other errors from previous nodes
        if state.error:
            return {
                "response": ScenarioResponse.error_response(
                    error_message=state.error,
                    agent_type=self.agent_type,
                )
            }

        # Build messages
        messages = [
            SystemMessage(content=state.system_prompt),
            HumanMessage(content=state.query),
        ]

        try:
            # Invoke LLM
            result = self.llm.invoke(messages)

            # Extract content
            content = (
                result.content
                if isinstance(result.content, str)
                else str(result.content)
            )

            # Get scenario data from context
            scenario: ScenarioData | None = state.context.get("_scenario_data")
            threat_profile: ThreatProfile | None = state.context.get("_threat_profile")

            # Build priorities from scenario data
            priorities = self._build_priorities(scenario) if scenario else []

            # Build recommended capabilities
            capabilities = self._build_capabilities(scenario) if scenario else []

            # Build sources
            sources = self._extract_sources(content, state)
            if scenario:
                sources.append(f"Scenario: {scenario.name}")
                sources.append(f"Campaign: {scenario.campaign}")

            # Build response
            response = ScenarioResponse(
                content=content,
                confidence=self._calculate_confidence(content, state),
                sources=sources,
                metadata=SubagentMetadata(
                    agent_type=self.agent_type,
                    query_type=self._determine_query_type(state.query),
                    context_used={
                        k: v
                        for k, v in state.context.items()
                        if v is not None and not k.startswith("_")
                    },
                    extra={
                        "scenario_found": scenario is not None,
                        "has_threat_profile": threat_profile is not None,
                    },
                ),
                scenario_name=scenario.name if scenario else "",
                threat_profile=threat_profile,
                preparation_priorities=priorities,
                recommended_capabilities=capabilities,
            )
            return {"response": response}

        except Exception as e:
            return {
                "response": ScenarioResponse.error_response(
                    error_message=f"LLM invocation failed: {e}",
                    agent_type=self.agent_type,
                )
            }

    def _find_scenario(
        self,
        scenario_query: str,
        campaign_hint: str | None = None,
    ) -> ScenarioData | None:
        """Find a scenario by ID or name.

        Args:
            scenario_query: Scenario ID or name to search for.
            campaign_hint: Optional campaign name to narrow search.

        Returns:
            ScenarioData if found, None otherwise.
        """
        # Try exact ID match first
        scenario = self.scenario_loader.get_scenario(scenario_query)
        if scenario:
            return scenario

        # Try name match
        scenario = self.scenario_loader.get_scenario_by_name(scenario_query)
        if scenario:
            # Verify campaign hint if provided
            if campaign_hint and campaign_hint.lower() not in scenario.campaign.lower():
                # Keep looking
                pass
            else:
                return scenario

        # Try search with campaign filter
        if campaign_hint:
            results = self.scenario_loader.search_scenarios(
                query=scenario_query,
                campaign=campaign_hint,
            )
            if results:
                return results[0]

        # Fall back to general search
        results = self.scenario_loader.search_scenarios(query=scenario_query)
        if results:
            return results[0]

        return None

    def _build_threat_profile(self, scenario: ScenarioData) -> ThreatProfile:
        """Build a ThreatProfile from scenario data.

        Args:
            scenario: The scenario data.

        Returns:
            ThreatProfile with categorized threats.
        """
        # Extract treachery types from profile
        treachery_types = [
            skill for skill, count in scenario.treachery_profile.items()
            if count > 0
        ]

        return ThreatProfile(
            enemy_density=scenario.enemy_density,
            treachery_types=treachery_types,
            key_skill_tests=scenario.key_tests,
            special_mechanics=scenario.mechanics,
        )

    def _build_priorities(self, scenario: ScenarioData) -> list[Priority]:
        """Build preparation priorities from scenario data.

        Args:
            scenario: The scenario data.

        Returns:
            List of Priority objects.
        """
        priorities = []

        # Treachery-based priorities
        treachery_profile = scenario.treachery_profile
        if treachery_profile.get("willpower", 0) >= 4:
            priorities.append(Priority(
                capability="willpower_icons",
                importance="critical",
                reason=f"High willpower treachery count ({treachery_profile['willpower']})",
            ))
        elif treachery_profile.get("willpower", 0) >= 2:
            priorities.append(Priority(
                capability="willpower_icons",
                importance="important",
                reason="Moderate willpower treachery presence",
            ))

        if treachery_profile.get("agility", 0) >= 3:
            priorities.append(Priority(
                capability="agility_icons",
                importance="important",
                reason=f"Agility tests common ({treachery_profile['agility']})",
            ))

        # Combat-based priorities
        if scenario.enemy_density == "high":
            priorities.append(Priority(
                capability="combat",
                importance="critical",
                reason="High enemy density scenario",
            ))
        elif scenario.enemy_density == "medium":
            priorities.append(Priority(
                capability="combat",
                importance="important",
                reason="Moderate enemy presence",
            ))

        # Elite enemy priorities
        elite_enemies = [e for e in scenario.enemies if e.type in ("elite", "ancient_one")]
        if elite_enemies:
            max_health = max(e.health for e in elite_enemies)
            if max_health >= 6:
                priorities.append(Priority(
                    capability="high_damage",
                    importance="critical",
                    reason=f"Elite enemy with {max_health} health",
                ))

        # Horror assessment
        horror_dealing = sum(e.horror for e in scenario.enemies)
        if horror_dealing >= 5 or treachery_profile.get("willpower", 0) >= 4:
            priorities.append(Priority(
                capability="horror_soak",
                importance="important",
                reason="Multiple horror sources",
            ))

        # Mechanic-based priorities
        mechanics_lower = [m.lower() for m in scenario.mechanics]
        if "doom" in mechanics_lower:
            priorities.append(Priority(
                capability="doom_management",
                importance="important",
                reason="Doom mechanic present - time pressure",
            ))

        return priorities

    def _build_capabilities(self, scenario: ScenarioData) -> list[str]:
        """Build list of recommended capabilities from scenario data.

        Args:
            scenario: The scenario data.

        Returns:
            List of capability strings.
        """
        capabilities = []

        # Based on key tests
        for test in scenario.key_tests:
            capabilities.append(f"{test}_boost")

        # Based on enemy density
        if scenario.enemy_density in ("medium", "high"):
            capabilities.append("damage_dealing")
            capabilities.append("enemy_handling")

        # Based on mechanics
        mechanics_lower = [m.lower() for m in scenario.mechanics]
        if "doom" in mechanics_lower:
            capabilities.append("ward_of_protection")
            capabilities.append("extra_actions")

        if "horror" in mechanics_lower or any(
            e.horror >= 2 for e in scenario.enemies
        ):
            capabilities.append("horror_healing")
            capabilities.append("sanity_soak")

        # Based on treachery profile
        if scenario.treachery_profile.get("willpower", 0) >= 3:
            capabilities.append("willpower_commit")
            capabilities.append("treachery_cancel")

        return list(set(capabilities))  # Remove duplicates

    def _format_treachery_info(self, scenario: ScenarioData) -> str:
        """Format treachery information for the prompt.

        Args:
            scenario: The scenario data.

        Returns:
            Formatted string with treachery info.
        """
        lines = []

        # Profile summary
        profile = scenario.treachery_profile
        if profile:
            profile_parts = [f"{skill}: {count}" for skill, count in profile.items() if count > 0]
            if profile_parts:
                lines.append(f"Test distribution: {', '.join(profile_parts)}")

        # Individual treacheries
        if scenario.treacheries:
            lines.append("\nNotable treacheries:")
            for t in scenario.treacheries[:5]:  # Limit to 5
                test_info = f"({t.test} {t.difficulty})" if t.test != "none" else "(no test)"
                lines.append(f"- **{t.name}** {test_info}: {t.effect}")
                if t.notes:
                    lines.append(f"  *{t.notes}*")

        return "\n".join(lines) if lines else "No specific treachery data available"

    def _format_enemy_info(self, scenario: ScenarioData) -> str:
        """Format enemy information for the prompt.

        Args:
            scenario: The scenario data.

        Returns:
            Formatted string with enemy info.
        """
        if not scenario.enemies:
            return "No specific enemy data available"

        lines = []
        for enemy in scenario.enemies[:5]:  # Limit to 5
            stats = f"Fight {enemy.fight}, Health {enemy.health}, Evade {enemy.evade}"
            threat = f"Deals {enemy.damage} damage, {enemy.horror} horror"
            lines.append(f"- **{enemy.name}** ({enemy.type}): {stats}")
            lines.append(f"  {threat}")
            if enemy.notes:
                lines.append(f"  *{enemy.notes}*")

        return "\n".join(lines)

    def _format_tips(self, scenario: ScenarioData) -> str:
        """Format tips for the prompt.

        Args:
            scenario: The scenario data.

        Returns:
            Formatted string with tips.
        """
        if not scenario.tips:
            return "No specific tips available"

        return "\n".join(f"- {tip}" for tip in scenario.tips)

    def _calculate_confidence(
        self, content: str, state: SubagentState
    ) -> float:
        """Calculate confidence for scenario responses.

        Higher confidence when:
        - Scenario data was found
        - Response contains specific threats and strategies

        Args:
            content: The LLM response content.
            state: The current graph state.

        Returns:
            Confidence score from 0.0 to 1.0.
        """
        base_confidence = 0.5

        # Boost for having scenario data
        if state.context.get("_scenario_data"):
            base_confidence += 0.25

        # Boost for specific content
        content_lower = content.lower()
        if any(
            phrase in content_lower
            for phrase in ["key threat", "priority", "recommend", "prepare"]
        ):
            base_confidence += 0.1

        if any(
            phrase in content_lower
            for phrase in ["willpower", "agility", "combat", "intellect"]
        ):
            base_confidence += 0.05

        # Penalty for uncertainty
        if any(
            phrase in content_lower
            for phrase in ["not sure", "unclear", "might", "possibly"]
        ):
            base_confidence -= 0.1

        return min(max(base_confidence, 0.1), 0.95)

    def _extract_sources(
        self, content: str, state: SubagentState
    ) -> list[str]:
        """Extract source references from the response.

        Args:
            content: The LLM response content.
            state: The current graph state.

        Returns:
            List of source references.
        """
        sources = []
        content_lower = content.lower()

        # Look for scenario-related keywords
        if "encounter deck" in content_lower:
            sources.append("Encounter Deck Analysis")
        if "agenda" in content_lower or "act" in content_lower:
            sources.append("Scenario Structure")
        if "boss" in content_lower:
            sources.append("Boss Enemy Data")

        return sources

    def _determine_query_type(self, query: str) -> str:
        """Classify the type of scenario query.

        Args:
            query: The user's query string.

        Returns:
            String identifier for the query type.
        """
        query_lower = query.lower()

        if any(word in query_lower for word in ["threat", "enemy", "danger"]):
            return "threat_analysis"
        if any(word in query_lower for word in ["prepar", "ready", "need", "bring"]):
            return "preparation"
        if any(word in query_lower for word in ["strateg", "approach", "how to", "play"]):
            return "strategy"
        if any(word in query_lower for word in ["treacher", "encounter"]):
            return "encounter_analysis"

        return "full_analysis"

    def query_scenario(
        self,
        scenario_query: ScenarioQuery,
        context: dict[str, Any] | None = None,
    ) -> ScenarioResponse:
        """Execute a scenario query with the ScenarioQuery input schema.

        This is a convenience method that accepts a ScenarioQuery object
        and merges its fields into the context.

        Args:
            scenario_query: The structured scenario query.
            context: Optional additional context.

        Returns:
            ScenarioResponse with the query result.
        """
        context = context or {}

        # Merge ScenarioQuery fields into context
        context["scenario_id"] = scenario_query.scenario_id
        if scenario_query.campaign:
            context["campaign_name"] = scenario_query.campaign
        if scenario_query.investigator_id:
            context["investigator_id"] = scenario_query.investigator_id

        # Build query from scenario ID
        query = f"Analyze the scenario: {scenario_query.scenario_id}"

        # Execute query
        response = self.query(query, context)

        # Ensure we return a ScenarioResponse
        if isinstance(response, ScenarioResponse):
            return response

        # Convert SubagentResponse to ScenarioResponse
        return ScenarioResponse.from_base_response(response)


# =============================================================================
# Factory function
# =============================================================================


def create_scenario_agent(
    config: SubagentConfig | None = None,
    scenario_loader: ScenarioLoader | None = None,
) -> ScenarioAgent:
    """Create a configured ScenarioAgent instance.

    Args:
        config: Optional configuration for the subagent.
        scenario_loader: Optional custom scenario loader.

    Returns:
        Configured ScenarioAgent instance.
    """
    return ScenarioAgent(config=config, scenario_loader=scenario_loader)
