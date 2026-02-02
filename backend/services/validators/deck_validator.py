"""Pure Python deck validator for hard deckbuilding constraints.

This module validates decks against investigator deckbuilding rules WITHOUT
using an LLM. Rules are enforced programmatically as a post-processing filter.

Design philosophy (from AlphaGo pattern):
- LLM generates creative recommendations (policy network)
- Validator filters illegal options (legal move mask)
- The filter is deterministic and fast

This is the "Rules as Mask" architecture from the decision_architecture.md proposal.
"""

from collections import Counter
from typing import Any

from backend.models.deck_constraints import (
    ClassAccess,
    DeckValidationResult,
    DeckBuildingRules,
    ValidationError,
)


class DeckValidator:
    """Validates decks against hard deckbuilding constraints.

    This class enforces rules that cannot be violated regardless of LLM
    suggestions. It acts as a filter on the recommendation pipeline.

    Typical usage:
        validator = DeckValidator()
        constraints = validator.load_constraints(investigator_code)
        result = validator.validate(deck, card_details, constraints)
        if not result.valid:
            # Filter or fix recommendations
    """

    # Card keywords that modify copy limits
    MYRIAD_ALLOWS_3 = True  # Myriad keyword allows 3 copies
    EXCEPTIONAL_ALLOWS_1 = True  # Exceptional keyword allows only 1 copy

    def __init__(self) -> None:
        """Initialize the validator."""
        # Constraint cache keyed by investigator_code
        self._constraint_cache: dict[str, DeckBuildingRules] = {}

    def validate(
        self,
        deck: dict[str, Any],
        card_details: list[dict[str, Any]],
        constraints: DeckBuildingRules,
        is_initial_deck: bool = True,
    ) -> DeckValidationResult:
        """Validate a deck against investigator constraints.

        Args:
            deck: Deck dictionary with 'cards' field (list or {id: count} dict)
            card_details: Full card data for each card in deck
            constraints: Investigator deckbuilding constraints
            is_initial_deck: If True, enforces level 0 only (no XP cards)

        Returns:
            DeckValidationResult with valid flag, errors, and warnings
        """
        errors: list[ValidationError] = []
        warnings: list[ValidationError] = []

        # Normalize cards to {code: count} format
        card_counts = self._normalize_cards(deck.get("cards", {}))
        card_lookup = {c.get("code") or c.get("id"): c for c in card_details}

        # Calculate total card count (excluding signatures and weaknesses)
        total_count = self._count_deck_cards(
            card_counts, card_lookup, constraints
        )

        # 1. Deck size validation
        if total_count != constraints.deck_size:
            errors.append(
                ValidationError(
                    code="DECK_SIZE",
                    message=(
                        f"Deck has {total_count} cards, "
                        f"must be exactly {constraints.deck_size}"
                    ),
                    severity="error",
                )
            )

        # 2. Copy limit validation
        copy_errors = self._validate_copy_limits(card_counts, card_lookup)
        errors.extend(copy_errors)

        # 3. Class restriction validation
        class_errors = self._validate_class_restrictions(
            card_counts, card_lookup, constraints
        )
        errors.extend(class_errors)

        # 4. XP level validation (for initial decks)
        if is_initial_deck:
            xp_errors = self._validate_xp_levels(card_counts, card_lookup)
            errors.extend(xp_errors)

        # 5. Required cards validation
        required_errors = self._validate_required_cards(card_counts, constraints)
        errors.extend(required_errors)

        # 6. Special rules warning
        if constraints.special_rules:
            warnings.append(
                ValidationError(
                    code="SPECIAL_RULES",
                    message=f"Manual check needed: {constraints.special_rules}",
                    severity="warning",
                )
            )

        return DeckValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            card_count=total_count,
            expected_count=constraints.deck_size,
        )

    def validate_single_card(
        self,
        card: dict[str, Any],
        constraints: DeckBuildingRules,
        is_initial_deck: bool = True,
    ) -> list[ValidationError]:
        """Check if a single card is legal for an investigator.

        Useful for filtering card recommendations before adding to deck.

        Args:
            card: Card data dictionary
            constraints: Investigator constraints
            is_initial_deck: If True, level 0 only

        Returns:
            List of validation errors (empty if card is legal)
        """
        errors: list[ValidationError] = []
        card_code = card.get("code") or card.get("id", "unknown")
        card_name = card.get("name", card_code)

        # Check class restriction
        card_faction = card.get("faction_code") or card.get("class_name", "")
        card_level = card.get("xp", 0) or 0

        if not constraints.allows_card(card_faction, card_level):
            errors.append(
                ValidationError(
                    code="CLASS_RESTRICTION",
                    message=(
                        f"'{card_name}' ({card_faction} level {card_level}) "
                        f"not allowed for {constraints.name}"
                    ),
                    card_code=card_code,
                    severity="error",
                )
            )

        # Check XP for initial deck
        if is_initial_deck and card_level > 0:
            errors.append(
                ValidationError(
                    code="XP_RESTRICTION",
                    message=(
                        f"'{card_name}' has XP cost ({card_level}) - "
                        f"not allowed in starting deck"
                    ),
                    card_code=card_code,
                    severity="error",
                )
            )

        return errors

    def _normalize_cards(
        self, cards: list | dict[str, int]
    ) -> dict[str, int]:
        """Convert card list/dict to {code: count} format.

        Args:
            cards: Either a list of card codes or a {code: count} dict

        Returns:
            Dictionary mapping card code to count
        """
        if isinstance(cards, dict):
            return cards.copy()

        # Count occurrences in list
        return dict(Counter(cards))

    def _count_deck_cards(
        self,
        card_counts: dict[str, int],
        card_lookup: dict[str, dict],
        constraints: DeckBuildingRules,
    ) -> int:
        """Count deck cards excluding signatures and weaknesses.

        Args:
            card_counts: {code: count} mapping
            card_lookup: Card details by code
            constraints: Investigator constraints

        Returns:
            Total card count for deck size validation
        """
        total = 0
        signature_set = set(constraints.signature_cards)
        weakness_set = set(constraints.weakness_cards)

        for card_code, count in card_counts.items():
            # Skip signature and weakness cards in count
            if card_code in signature_set or card_code in weakness_set:
                continue
            total += count

        return total

    def _validate_copy_limits(
        self,
        card_counts: dict[str, int],
        card_lookup: dict[str, dict],
    ) -> list[ValidationError]:
        """Validate copy limits (max 2, or modified by keywords).

        Args:
            card_counts: {code: count} mapping
            card_lookup: Card details by code

        Returns:
            List of copy limit violation errors
        """
        errors: list[ValidationError] = []

        for card_code, count in card_counts.items():
            card = card_lookup.get(card_code, {})
            card_name = card.get("name", card_code)
            traits = (card.get("traits") or "").lower()
            text = (card.get("text") or "").lower()

            # Determine max copies
            max_copies = 2
            if "myriad" in traits or "myriad" in text:
                max_copies = 3
            if "exceptional" in text:
                max_copies = 1

            if count > max_copies:
                errors.append(
                    ValidationError(
                        code="COPY_LIMIT",
                        message=(
                            f"'{card_name}' has {count} copies "
                            f"(max {max_copies})"
                        ),
                        card_code=card_code,
                        severity="error",
                    )
                )

        return errors

    def _validate_class_restrictions(
        self,
        card_counts: dict[str, int],
        card_lookup: dict[str, dict],
        constraints: DeckBuildingRules,
    ) -> list[ValidationError]:
        """Validate class/faction restrictions.

        Args:
            card_counts: {code: count} mapping
            card_lookup: Card details by code
            constraints: Investigator constraints

        Returns:
            List of class restriction violation errors
        """
        errors: list[ValidationError] = []

        # Track counts per faction for max_count enforcement
        faction_counts: dict[str, int] = Counter()

        for card_code, count in card_counts.items():
            card = card_lookup.get(card_code, {})
            card_name = card.get("name", card_code)
            card_faction = card.get("faction_code") or card.get("class_name", "")
            card_level = card.get("xp", 0) or 0

            # Skip if we don't have card data
            if not card:
                continue

            faction_counts[card_faction.lower()] += count

            # Check if faction/level combo is allowed
            if not constraints.allows_card(card_faction, card_level):
                errors.append(
                    ValidationError(
                        code="CLASS_RESTRICTION",
                        message=(
                            f"'{card_name}' ({card_faction} level {card_level}) "
                            f"not allowed for {constraints.name}"
                        ),
                        card_code=card_code,
                        severity="error",
                    )
                )

        # Check faction count limits
        for option in constraints.deck_options:
            if option.max_count is not None:
                faction_key = option.faction.lower()
                actual = faction_counts.get(faction_key, 0)
                if actual > option.max_count:
                    errors.append(
                        ValidationError(
                            code="FACTION_COUNT",
                            message=(
                                f"Too many {option.faction} cards: "
                                f"{actual} (max {option.max_count})"
                            ),
                            severity="error",
                        )
                    )

        return errors

    def _validate_xp_levels(
        self,
        card_counts: dict[str, int],
        card_lookup: dict[str, dict],
    ) -> list[ValidationError]:
        """Validate XP levels for initial deck (level 0 only).

        Args:
            card_counts: {code: count} mapping
            card_lookup: Card details by code

        Returns:
            List of XP violation errors
        """
        errors: list[ValidationError] = []

        for card_code in card_counts:
            card = card_lookup.get(card_code, {})
            card_name = card.get("name", card_code)
            card_level = card.get("xp", 0) or 0

            if card_level > 0:
                errors.append(
                    ValidationError(
                        code="XP_RESTRICTION",
                        message=(
                            f"'{card_name}' has XP cost ({card_level}) - "
                            f"not allowed in starting deck"
                        ),
                        card_code=card_code,
                        severity="error",
                    )
                )

        return errors

    def _validate_required_cards(
        self,
        card_counts: dict[str, int],
        constraints: DeckBuildingRules,
    ) -> list[ValidationError]:
        """Validate required signature and weakness cards.

        Args:
            card_counts: {code: count} mapping
            constraints: Investigator constraints

        Returns:
            List of missing required card errors
        """
        errors: list[ValidationError] = []
        present_cards = set(card_counts.keys())

        for sig in constraints.signature_cards:
            if sig not in present_cards:
                errors.append(
                    ValidationError(
                        code="MISSING_SIGNATURE",
                        message=f"Missing required signature card: {sig}",
                        card_code=sig,
                        severity="error",
                    )
                )

        for weakness in constraints.weakness_cards:
            if weakness not in present_cards:
                errors.append(
                    ValidationError(
                        code="MISSING_WEAKNESS",
                        message=f"Missing required weakness: {weakness}",
                        card_code=weakness,
                        severity="error",
                    )
                )

        return errors


# =============================================================================
# Investigator Constraint Presets
# =============================================================================

# Common investigators with their deckbuilding rules
# These can be loaded from ChromaDB in production, but having presets
# ensures validation works even without database access

INVESTIGATOR_PRESETS: dict[str, DeckBuildingRules] = {
    # Core Set Investigators
    "01001": DeckBuildingRules(
        investigator_code="01001",
        name="Roland Banks",
        deck_size=30,
        deck_options=[
            ClassAccess(faction="Guardian", max_level=5),
            ClassAccess(faction="Seeker", max_level=2),
            ClassAccess(faction="Neutral", max_level=5),
        ],
        signature_cards=["01006"],  # Roland's .38 Special
        weakness_cards=["01007"],  # Cover Up
    ),
    "01002": DeckBuildingRules(
        investigator_code="01002",
        name="Daisy Walker",
        deck_size=30,
        deck_options=[
            ClassAccess(faction="Seeker", max_level=5),
            ClassAccess(faction="Mystic", max_level=2),
            ClassAccess(faction="Neutral", max_level=5),
        ],
        signature_cards=["01008"],  # Daisy's Tote Bag
        weakness_cards=["01009"],  # The Necronomicon
    ),
    "01003": DeckBuildingRules(
        investigator_code="01003",
        name="Skids O'Toole",
        deck_size=30,
        deck_options=[
            ClassAccess(faction="Rogue", max_level=5),
            ClassAccess(faction="Guardian", max_level=2),
            ClassAccess(faction="Neutral", max_level=5),
        ],
        signature_cards=["01010"],  # On the Lam
        weakness_cards=["01011"],  # Hospital Debts
    ),
    "01004": DeckBuildingRules(
        investigator_code="01004",
        name="Agnes Baker",
        deck_size=30,
        deck_options=[
            ClassAccess(faction="Mystic", max_level=5),
            ClassAccess(faction="Survivor", max_level=2),
            ClassAccess(faction="Neutral", max_level=5),
        ],
        signature_cards=["01012"],  # Heirloom of Hyperborea
        weakness_cards=["01013"],  # Dark Memory
    ),
    "01005": DeckBuildingRules(
        investigator_code="01005",
        name="Wendy Adams",
        deck_size=30,
        deck_options=[
            ClassAccess(faction="Survivor", max_level=5),
            ClassAccess(faction="Rogue", max_level=2),
            ClassAccess(faction="Neutral", max_level=5),
        ],
        signature_cards=["01014"],  # Wendy's Amulet
        weakness_cards=["01015"],  # Abandoned and Alone
    ),
}


def get_investigator_constraints(investigator_code: str) -> DeckBuildingRules | None:
    """Get constraints for an investigator by code.

    First checks presets, then could be extended to query ChromaDB.

    Args:
        investigator_code: ArkhamDB investigator code

    Returns:
        DeckBuildingRules or None if not found
    """
    return INVESTIGATOR_PRESETS.get(investigator_code)
