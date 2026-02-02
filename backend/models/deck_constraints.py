"""Pydantic models for deckbuilding constraints and validation.

This module defines the structured schemas for hard deckbuilding rules
that must be enforced regardless of LLM recommendations. These constraints
come directly from investigator cards and game rules.

Design philosophy: Rules retrieved from documents can be misinterpreted
by LLMs. These models encode rules as data structures that can be
programmatically validated without interpretation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ClassAccess(BaseModel):
    """Access rules for a single card class/faction.

    Defines what level cards an investigator can include from a specific
    class, and optionally limits the count of cards from that class.

    Attributes:
        faction: The card faction (Guardian, Seeker, etc.)
        max_level: Maximum card level allowed (0-5)
        max_count: Optional limit on total cards from this faction
    """

    faction: str = Field(description="Card faction (Guardian, Seeker, Mystic, Rogue, Survivor, Neutral)")
    max_level: int = Field(default=5, ge=0, le=5, description="Maximum card level allowed (0-5)")
    max_count: int | None = Field(default=None, ge=1, description="Optional max cards from this faction")


class DeckBuildingRules(BaseModel):
    """Hard deckbuilding constraints derived from an investigator card.

    This model captures the full flexibility of investigator deckbuilding
    rules, including multi-class investigators and complex restrictions.

    Note: This differs from backend.models.InvestigatorConstraints which
    uses a simpler primary/secondary class pattern. This model handles
    edge cases like Tony Morgan (5 class options) or Lola Hayes.

    Attributes:
        investigator_code: ArkhamDB investigator code (e.g., "01001")
        name: Investigator display name
        deck_size: Required deck size (usually 30, some exceptions)
        deck_options: List of class access rules from investigator card
        signature_cards: Required signature asset card codes
        weakness_cards: Required weakness card codes
        special_rules: Free-text for complex edge cases the validator flags
    """

    investigator_code: str = Field(description="ArkhamDB investigator code")
    name: str = Field(description="Investigator display name")
    deck_size: int = Field(default=30, ge=20, le=50, description="Required deck size")
    deck_options: list[ClassAccess] = Field(
        default_factory=list,
        description="List of class access rules from investigator card"
    )
    signature_cards: list[str] = Field(
        default_factory=list,
        description="Required signature asset card codes"
    )
    weakness_cards: list[str] = Field(
        default_factory=list,
        description="Required weakness card codes"
    )
    special_rules: str | None = Field(
        default=None,
        description="Free-text for complex rules that need manual review"
    )

    def allows_card(self, faction: str, level: int) -> bool:
        """Check if a card is allowed by class/level restrictions.

        Args:
            faction: The card's faction
            level: The card's XP level (0-5)

        Returns:
            True if the card is allowed by at least one deck option
        """
        for option in self.deck_options:
            if option.faction.lower() == faction.lower() and level <= option.max_level:
                return True
        return False


class ValidationError(BaseModel):
    """A single validation error with context.

    Attributes:
        code: Machine-readable error code
        message: Human-readable error description
        card_code: Related card code if applicable
        severity: Error severity (error blocks deck, warning is advisory)
    """

    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error description")
    card_code: str | None = Field(default=None, description="Related card code")
    severity: Literal["error", "warning"] = Field(
        default="error",
        description="error = blocks deck, warning = advisory"
    )


class DeckValidationResult(BaseModel):
    """Complete validation result for a deck.

    Attributes:
        valid: True if deck passes all hard constraints
        errors: List of blocking validation errors
        warnings: List of advisory warnings (deck still valid)
        card_count: Actual card count in deck
        expected_count: Expected card count from investigator
    """

    valid: bool = Field(description="True if deck passes all hard constraints")
    errors: list[ValidationError] = Field(
        default_factory=list,
        description="Blocking validation errors"
    )
    warnings: list[ValidationError] = Field(
        default_factory=list,
        description="Advisory warnings"
    )
    card_count: int = Field(default=0, description="Actual card count")
    expected_count: int = Field(default=30, description="Expected card count")

    def summary(self) -> str:
        """Generate a human-readable validation summary.

        Returns:
            Multi-line string summarizing validation result
        """
        if self.valid:
            return f"✓ Deck valid ({self.card_count}/{self.expected_count} cards)"

        lines = [f"✗ Deck invalid ({self.card_count}/{self.expected_count} cards)"]
        for err in self.errors:
            lines.append(f"  ERROR: {err.message}")
        for warn in self.warnings:
            lines.append(f"  WARN: {warn.message}")
        return "\n".join(lines)
