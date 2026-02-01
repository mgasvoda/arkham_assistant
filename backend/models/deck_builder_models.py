"""Pydantic models for deck building functionality.

This module defines the structured schemas for the deck building flow,
including card selections, build goals, investigator constraints,
and the final deck response.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CardSelection(BaseModel):
    """A card selected for the deck with reasoning.

    Attributes:
        card_id: The unique identifier of the card.
        name: The display name of the card.
        quantity: Number of copies (1 or 2).
        reason: Why this card was included.
        category: The role this card fills (combat, clues, economy, etc.).
    """

    card_id: str = Field(description="Unique card identifier")
    name: str = Field(description="Display name of the card")
    quantity: int = Field(ge=1, le=2, description="Number of copies (1 or 2)")
    reason: str = Field(description="Why this card was included")
    category: str = Field(description="Role this card fills (combat, clues, economy, draw, etc.)")


class DeckBuildGoals(BaseModel):
    """Extracted goals from the user's deck building request.

    Attributes:
        primary_focus: Main playstyle focus (combat, clues, support, flex).
        secondary_focus: Optional secondary focus.
        specific_requests: Specific user requests (e.g., "lots of card draw").
        avoid_cards: Cards or types to avoid.
    """

    primary_focus: str = Field(description="Main playstyle focus: combat, clues, support, or flex")
    secondary_focus: str | None = Field(default=None, description="Optional secondary focus")
    specific_requests: list[str] = Field(
        default_factory=list, description="Specific user requests extracted from message"
    )
    avoid_cards: list[str] = Field(default_factory=list, description="Cards or types to avoid")


class InvestigatorConstraints(BaseModel):
    """Deckbuilding constraints for an investigator.

    Attributes:
        investigator_id: The investigator's unique ID.
        investigator_name: Display name.
        primary_class: Main class (Guardian, Seeker, etc.).
        secondary_class: Off-class access if any.
        secondary_level: Max level for secondary class cards.
        deck_size: Required deck size (usually 30).
        required_cards: Signature cards that must be included.
        forbidden_traits: Traits that cannot be included.
        special_rules: Any special deckbuilding rules.
    """

    investigator_id: str = Field(description="Investigator unique ID")
    investigator_name: str = Field(description="Investigator display name")
    primary_class: str = Field(description="Main class")
    secondary_class: str | None = Field(default=None, description="Off-class access if any")
    secondary_level: int = Field(
        default=0, ge=0, le=5, description="Max level for secondary class cards"
    )
    deck_size: int = Field(default=30, ge=20, le=50, description="Required deck size")
    required_cards: list[str] = Field(
        default_factory=list, description="Signature card IDs that must be included"
    )
    forbidden_traits: list[str] = Field(
        default_factory=list, description="Traits that cannot be included"
    )
    special_rules: str = Field(default="", description="Any special deckbuilding rules")


class DeckBuilderSubagentResult(BaseModel):
    """Simplified subagent result for deck building responses.

    Attributes:
        agent_type: Which subagent produced this result.
        query: The query sent to the subagent.
        success: Whether the query succeeded.
        summary: Brief summary of the response.
    """

    agent_type: str = Field(description="The subagent type")
    query: str = Field(description="Query sent to the subagent")
    success: bool = Field(default=True, description="Whether query succeeded")
    summary: str = Field(default="", description="Brief summary of response")


class UpgradeRecommendation(BaseModel):
    """A single upgrade recommendation for the deck.

    Attributes:
        priority: Priority ranking (1 = highest priority).
        action: Type of upgrade action (upgrade, swap, add, remove).
        remove_card: Card ID to remove (None for add actions).
        remove_card_name: Display name of card to remove.
        add_card: Card ID to add.
        add_card_name: Display name of card to add.
        xp_cost: XP cost for this upgrade.
        reason: Explanation of why this upgrade is recommended.
    """

    priority: int = Field(ge=1, description="Priority ranking (1 = highest)")
    action: str = Field(description="Type of action: 'upgrade', 'swap', 'add', or 'remove'")
    remove_card: str | None = Field(
        default=None, description="Card ID to remove (None for add actions)"
    )
    remove_card_name: str | None = Field(default=None, description="Display name of card to remove")
    add_card: str = Field(description="Card ID to add")
    add_card_name: str = Field(description="Display name of card to add")
    xp_cost: int = Field(ge=0, description="XP cost for this upgrade")
    reason: str = Field(description="Why this upgrade is recommended")


class UpgradeResponse(BaseModel):
    """Response for deck upgrade requests.

    This is the output schema for the deck upgrade flow,
    containing prioritized upgrade recommendations.

    Attributes:
        recommendations: List of upgrade recommendations in priority order.
        total_xp_cost: Total XP spent on all recommendations.
        remaining_xp: XP remaining after recommendations.
        available_xp: Original XP budget provided.
        deck_improvement_summary: Overall summary of improvements.
        investigator_id: The investigator this deck is for.
        investigator_name: Display name of the investigator.
        warnings: Any concerns or budget warnings.
        confidence: Overall confidence in the recommendations.
        subagent_results: Results from consulted subagents.
        metadata: Additional metadata about the upgrade process.
    """

    recommendations: list[UpgradeRecommendation] = Field(
        default_factory=list, description="Prioritized list of upgrade recommendations"
    )
    total_xp_cost: int = Field(default=0, ge=0, description="Total XP spent on all recommendations")
    remaining_xp: int = Field(default=0, ge=0, description="XP remaining after recommendations")
    available_xp: int = Field(default=0, ge=0, description="Original XP budget provided")
    deck_improvement_summary: str = Field(
        default="", description="Summary of how the deck will improve"
    )
    investigator_id: str = Field(default="", description="Investigator ID")
    investigator_name: str = Field(default="", description="Investigator display name")
    warnings: list[str] = Field(
        default_factory=list, description="Warnings about budget or recommendations"
    )
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence in recommendation quality"
    )
    subagent_results: list[DeckBuilderSubagentResult] = Field(
        default_factory=list, description="Results from consulted subagents"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional upgrade metadata"
    )

    @classmethod
    def error_response(
        cls,
        error_message: str,
        investigator_id: str = "",
        investigator_name: str = "",
        available_xp: int = 0,
    ) -> UpgradeResponse:
        """Create an error response for failed upgrade analysis.

        Args:
            error_message: Description of the error.
            investigator_id: The investigator ID if known.
            investigator_name: The investigator name if known.
            available_xp: The original XP budget.

        Returns:
            UpgradeResponse indicating an error occurred.
        """
        return cls(
            recommendations=[],
            total_xp_cost=0,
            remaining_xp=available_xp,
            available_xp=available_xp,
            deck_improvement_summary=error_message,
            investigator_id=investigator_id,
            investigator_name=investigator_name,
            warnings=[error_message],
            confidence=0.0,
            metadata={"error": True},
        )


class NewDeckResponse(BaseModel):
    """Response for new deck creation.

    This is the output schema for the deck building flow,
    containing the complete deck list with explanations.

    Attributes:
        deck_name: A generated name for the deck.
        investigator_id: The investigator this deck is for.
        investigator_name: Display name of the investigator.
        cards: List of selected cards with reasoning.
        total_cards: Total card count (should be deck_size).
        reasoning: Overall explanation of the build strategy.
        archetype: Identified playstyle (e.g., "Combat Guardian").
        warnings: Any concerns about the build.
        confidence: Overall confidence in the deck quality.
        subagent_results: Results from consulted subagents.
        metadata: Additional metadata about the build process.
    """

    deck_name: str = Field(description="Generated deck name")
    investigator_id: str = Field(description="Investigator ID")
    investigator_name: str = Field(description="Investigator display name")
    cards: list[CardSelection] = Field(
        default_factory=list, description="Selected cards with reasoning"
    )
    total_cards: int = Field(default=0, ge=0, description="Total card count")
    reasoning: str = Field(default="", description="Overall build strategy explanation")
    archetype: str = Field(default="", description="Identified playstyle")
    warnings: list[str] = Field(default_factory=list, description="Any concerns about the build")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence in deck quality")
    subagent_results: list[DeckBuilderSubagentResult] = Field(
        default_factory=list, description="Results from consulted subagents"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional build metadata")

    @classmethod
    def error_response(
        cls,
        error_message: str,
        investigator_id: str = "",
        investigator_name: str = "",
    ) -> NewDeckResponse:
        """Create an error response for failed deck building.

        Args:
            error_message: Description of the error.
            investigator_id: The investigator ID if known.
            investigator_name: The investigator name if known.

        Returns:
            NewDeckResponse indicating an error occurred.
        """
        return cls(
            deck_name="Error",
            investigator_id=investigator_id,
            investigator_name=investigator_name,
            cards=[],
            total_cards=0,
            reasoning=error_message,
            archetype="",
            warnings=[error_message],
            confidence=0.0,
            metadata={"error": True},
        )
