"""Tests for DeckValidator.

Tests pure Python validation of deckbuilding constraints.
"""

import pytest

from backend.models.deck_constraints import (
    ClassAccess,
    DeckValidationResult,
    DeckBuildingRules,
    ValidationError,
)
from backend.services.validators.deck_validator import (
    DeckValidator,
    INVESTIGATOR_PRESETS,
    get_investigator_constraints,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator() -> DeckValidator:
    """Create a validator instance."""
    return DeckValidator()


@pytest.fixture
def roland_constraints() -> DeckBuildingRules:
    """Roland Banks deckbuilding constraints."""
    return DeckBuildingRules(
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
    )


@pytest.fixture
def sample_card_details() -> list[dict]:
    """Sample card data for validation."""
    return [
        {
            "code": "01016",
            "name": ".45 Automatic",
            "faction_code": "Guardian",
            "xp": 0,
            "traits": "Item. Weapon. Firearm.",
        },
        {
            "code": "01017",
            "name": "Physical Training",
            "faction_code": "Guardian",
            "xp": 0,
            "traits": "Talent.",
        },
        {
            "code": "01018",
            "name": "Beat Cop",
            "faction_code": "Guardian",
            "xp": 0,
            "traits": "Ally. Police.",
        },
        {
            "code": "01025",
            "name": "Magnifying Glass",
            "faction_code": "Seeker",
            "xp": 0,
            "traits": "Item. Tool.",
        },
        {
            "code": "01030",
            "name": "Dr. Milan Christopher",
            "faction_code": "Seeker",
            "xp": 0,
            "traits": "Ally. Miskatonic.",
        },
        {
            "code": "01050",
            "name": "Shrivelling",
            "faction_code": "Mystic",
            "xp": 0,
            "traits": "Spell.",
        },
        {
            "code": "01060",
            "name": "Vicious Blow",
            "faction_code": "Guardian",
            "xp": 2,
            "traits": "Practiced. Expert.",
        },
        {
            "code": "01088",
            "name": "Emergency Cache",
            "faction_code": "Neutral",
            "xp": 0,
            "traits": "Supply.",
        },
        {
            "code": "01006",  # Roland's signature
            "name": "Roland's .38 Special",
            "faction_code": "Guardian",
            "xp": 0,
            "traits": "Item. Weapon. Firearm.",
        },
        {
            "code": "01007",  # Roland's weakness
            "name": "Cover Up",
            "faction_code": "Neutral",
            "xp": 0,
            "traits": "Task.",
        },
        {
            "code": "myriad_card",
            "name": "Myriad Test Card",
            "faction_code": "Neutral",
            "xp": 0,
            "text": "Myriad.",
        },
        {
            "code": "exceptional_card",
            "name": "Exceptional Test Card",
            "faction_code": "Guardian",
            "xp": 3,
            "text": "Exceptional.",
        },
    ]


# =============================================================================
# Deck Size Tests
# =============================================================================


class TestDeckSizeValidation:
    """Tests for deck size validation."""

    def test_valid_deck_size(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """A deck with exactly 30 cards passes."""
        # 30 regular cards + signature + weakness
        cards = {f"card_{i}": 1 for i in range(30)}
        cards["01006"] = 1  # Signature
        cards["01007"] = 1  # Weakness

        card_details = [
            {"code": f"card_{i}", "faction_code": "Guardian", "xp": 0}
            for i in range(30)
        ]
        card_details.append({"code": "01006", "faction_code": "Guardian", "xp": 0})
        card_details.append({"code": "01007", "faction_code": "Neutral", "xp": 0})

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints
        )

        assert result.valid
        assert result.card_count == 30
        assert len(result.errors) == 0

    def test_too_few_cards(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """A deck with fewer than 30 cards fails."""
        cards = {f"card_{i}": 1 for i in range(25)}
        card_details = [
            {"code": f"card_{i}", "faction_code": "Guardian", "xp": 0}
            for i in range(25)
        ]

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints
        )

        assert not result.valid
        assert result.card_count == 25
        assert any(e.code == "DECK_SIZE" for e in result.errors)

    def test_too_many_cards(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """A deck with more than 30 cards fails."""
        cards = {f"card_{i}": 1 for i in range(35)}
        card_details = [
            {"code": f"card_{i}", "faction_code": "Guardian", "xp": 0}
            for i in range(35)
        ]

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints
        )

        assert not result.valid
        assert result.card_count == 35
        assert any(e.code == "DECK_SIZE" for e in result.errors)


# =============================================================================
# Copy Limit Tests
# =============================================================================


class TestCopyLimitValidation:
    """Tests for card copy limit validation."""

    def test_valid_two_copies(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """Two copies of a normal card is valid."""
        cards = {"01016": 2}  # 2x .45 Automatic
        for i in range(28):
            cards[f"filler_{i}"] = 1

        card_details = [{"code": "01016", "faction_code": "Guardian", "xp": 0}]
        card_details.extend([
            {"code": f"filler_{i}", "faction_code": "Guardian", "xp": 0}
            for i in range(28)
        ])

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints
        )

        # Should not have copy limit errors
        copy_errors = [e for e in result.errors if e.code == "COPY_LIMIT"]
        assert len(copy_errors) == 0

    def test_three_copies_fails(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """Three copies of a normal card fails."""
        cards = {"01016": 3}  # 3x .45 Automatic - illegal!
        card_details = [{"code": "01016", "faction_code": "Guardian", "xp": 0}]

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints
        )

        copy_errors = [e for e in result.errors if e.code == "COPY_LIMIT"]
        assert len(copy_errors) == 1
        assert ".45 Automatic" not in copy_errors[0].message or "01016" in copy_errors[0].message

    def test_myriad_allows_three(
        self,
        validator: DeckValidator,
        roland_constraints: DeckBuildingRules,
        sample_card_details: list[dict],
    ):
        """Myriad cards can have 3 copies."""
        cards = {"myriad_card": 3}
        card_details = [c for c in sample_card_details if c["code"] == "myriad_card"]

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints
        )

        copy_errors = [e for e in result.errors if e.code == "COPY_LIMIT"]
        assert len(copy_errors) == 0

    def test_exceptional_allows_one(
        self,
        validator: DeckValidator,
        roland_constraints: DeckBuildingRules,
        sample_card_details: list[dict],
    ):
        """Exceptional cards can only have 1 copy."""
        cards = {"exceptional_card": 2}
        card_details = [c for c in sample_card_details if c["code"] == "exceptional_card"]

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints, is_initial_deck=False
        )

        copy_errors = [e for e in result.errors if e.code == "COPY_LIMIT"]
        assert len(copy_errors) == 1
        assert "max 1" in copy_errors[0].message


# =============================================================================
# Class Restriction Tests
# =============================================================================


class TestClassRestrictionValidation:
    """Tests for class/faction restriction validation."""

    def test_valid_classes(
        self,
        validator: DeckValidator,
        roland_constraints: DeckBuildingRules,
        sample_card_details: list[dict],
    ):
        """Guardian and Seeker (level 0-2) cards are valid for Roland."""
        cards = {
            "01016": 2,  # Guardian
            "01025": 2,  # Seeker
            "01088": 2,  # Neutral
        }
        for i in range(24):
            cards[f"guardian_{i}"] = 1

        card_details = [c for c in sample_card_details if c["code"] in cards]
        card_details.extend([
            {"code": f"guardian_{i}", "faction_code": "Guardian", "xp": 0}
            for i in range(24)
        ])

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints
        )

        class_errors = [e for e in result.errors if e.code == "CLASS_RESTRICTION"]
        assert len(class_errors) == 0

    def test_forbidden_class_fails(
        self,
        validator: DeckValidator,
        roland_constraints: DeckBuildingRules,
        sample_card_details: list[dict],
    ):
        """Mystic cards fail for Roland (not in his deckbuilding options)."""
        cards = {"01050": 1}  # Shrivelling - Mystic card
        card_details = [c for c in sample_card_details if c["code"] == "01050"]

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints
        )

        class_errors = [e for e in result.errors if e.code == "CLASS_RESTRICTION"]
        assert len(class_errors) == 1
        assert "Mystic" in class_errors[0].message

    def test_seeker_level_3_fails_for_roland(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """Roland can only take Seeker 0-2, not level 3+."""
        cards = {"seeker_3": 1}
        card_details = [{"code": "seeker_3", "faction_code": "Seeker", "xp": 3}]

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints, is_initial_deck=False
        )

        class_errors = [e for e in result.errors if e.code == "CLASS_RESTRICTION"]
        assert len(class_errors) == 1
        assert "level 3" in class_errors[0].message


# =============================================================================
# XP Level Tests
# =============================================================================


class TestXPValidation:
    """Tests for XP/level validation in initial decks."""

    def test_level_0_valid_in_initial(
        self,
        validator: DeckValidator,
        roland_constraints: DeckBuildingRules,
        sample_card_details: list[dict],
    ):
        """Level 0 cards are valid in initial decks."""
        cards = {"01016": 2}  # .45 Automatic (level 0)
        card_details = [c for c in sample_card_details if c["code"] == "01016"]

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints, is_initial_deck=True
        )

        xp_errors = [e for e in result.errors if e.code == "XP_RESTRICTION"]
        assert len(xp_errors) == 0

    def test_level_2_fails_in_initial(
        self,
        validator: DeckValidator,
        roland_constraints: DeckBuildingRules,
        sample_card_details: list[dict],
    ):
        """Level 2+ cards fail in initial decks."""
        cards = {"01060": 1}  # Vicious Blow (2) - level 2
        card_details = [c for c in sample_card_details if c["code"] == "01060"]

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints, is_initial_deck=True
        )

        xp_errors = [e for e in result.errors if e.code == "XP_RESTRICTION"]
        assert len(xp_errors) == 1
        assert "XP cost" in xp_errors[0].message

    def test_level_2_valid_in_upgraded(
        self,
        validator: DeckValidator,
        roland_constraints: DeckBuildingRules,
        sample_card_details: list[dict],
    ):
        """Level 2+ cards are valid in upgraded decks."""
        cards = {"01060": 1}  # Vicious Blow (2)
        card_details = [c for c in sample_card_details if c["code"] == "01060"]

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints, is_initial_deck=False
        )

        xp_errors = [e for e in result.errors if e.code == "XP_RESTRICTION"]
        assert len(xp_errors) == 0


# =============================================================================
# Required Cards Tests
# =============================================================================


class TestRequiredCardsValidation:
    """Tests for signature and weakness card validation."""

    def test_missing_signature_fails(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """Missing signature card produces error."""
        cards = {f"card_{i}": 1 for i in range(30)}
        cards["01007"] = 1  # Has weakness
        # Missing 01006 (signature)

        card_details = [
            {"code": f"card_{i}", "faction_code": "Guardian", "xp": 0}
            for i in range(30)
        ]
        card_details.append({"code": "01007", "faction_code": "Neutral", "xp": 0})

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints
        )

        sig_errors = [e for e in result.errors if e.code == "MISSING_SIGNATURE"]
        assert len(sig_errors) == 1
        assert "01006" in sig_errors[0].message

    def test_missing_weakness_fails(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """Missing weakness card produces error."""
        cards = {f"card_{i}": 1 for i in range(30)}
        cards["01006"] = 1  # Has signature
        # Missing 01007 (weakness)

        card_details = [
            {"code": f"card_{i}", "faction_code": "Guardian", "xp": 0}
            for i in range(30)
        ]
        card_details.append({"code": "01006", "faction_code": "Guardian", "xp": 0})

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints
        )

        weakness_errors = [e for e in result.errors if e.code == "MISSING_WEAKNESS"]
        assert len(weakness_errors) == 1
        assert "01007" in weakness_errors[0].message


# =============================================================================
# Single Card Validation Tests
# =============================================================================


class TestSingleCardValidation:
    """Tests for single card validation (for recommendation filtering)."""

    def test_valid_card_for_investigator(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """Guardian level 0 card is valid for Roland."""
        card = {"code": "01016", "faction_code": "Guardian", "xp": 0, "name": ".45 Auto"}

        errors = validator.validate_single_card(
            card, roland_constraints, is_initial_deck=True
        )

        assert len(errors) == 0

    def test_invalid_class_for_investigator(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """Mystic card is invalid for Roland."""
        card = {"code": "01050", "faction_code": "Mystic", "xp": 0, "name": "Shrivelling"}

        errors = validator.validate_single_card(
            card, roland_constraints, is_initial_deck=True
        )

        assert len(errors) == 1
        assert errors[0].code == "CLASS_RESTRICTION"

    def test_xp_card_in_initial_deck(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """Level 2 card fails for initial deck."""
        card = {"code": "01060", "faction_code": "Guardian", "xp": 2, "name": "Vicious Blow (2)"}

        errors = validator.validate_single_card(
            card, roland_constraints, is_initial_deck=True
        )

        assert len(errors) == 1
        assert errors[0].code == "XP_RESTRICTION"


# =============================================================================
# Preset Tests
# =============================================================================


class TestInvestigatorPresets:
    """Tests for investigator constraint presets."""

    def test_core_investigators_present(self):
        """All core set investigators have presets."""
        core_codes = ["01001", "01002", "01003", "01004", "01005"]
        for code in core_codes:
            assert code in INVESTIGATOR_PRESETS

    def test_get_investigator_constraints(self):
        """get_investigator_constraints returns correct data."""
        roland = get_investigator_constraints("01001")
        assert roland is not None
        assert roland.name == "Roland Banks"
        assert roland.deck_size == 30

    def test_unknown_investigator_returns_none(self):
        """Unknown investigator code returns None."""
        result = get_investigator_constraints("99999")
        assert result is None

    def test_roland_allows_guardian(self):
        """Roland can include Guardian cards."""
        roland = get_investigator_constraints("01001")
        assert roland.allows_card("Guardian", 5)
        assert roland.allows_card("guardian", 0)  # Case insensitive

    def test_roland_allows_seeker_limited(self):
        """Roland can include Seeker 0-2 only."""
        roland = get_investigator_constraints("01001")
        assert roland.allows_card("Seeker", 0)
        assert roland.allows_card("Seeker", 2)
        assert not roland.allows_card("Seeker", 3)

    def test_roland_disallows_mystic(self):
        """Roland cannot include Mystic cards."""
        roland = get_investigator_constraints("01001")
        assert not roland.allows_card("Mystic", 0)


# =============================================================================
# Integration Tests
# =============================================================================


class TestValidatorIntegration:
    """Integration tests with realistic scenarios."""

    def test_complete_valid_roland_deck(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """A complete, valid Roland deck passes all checks."""
        # Build a realistic 30-card deck
        cards = {
            # Guardian cards
            "01016": 2,  # .45 Automatic
            "01017": 2,  # Physical Training
            "01018": 2,  # Beat Cop
            "01019": 2,  # First Aid
            "01020": 2,  # Machete
            "01021": 2,  # Guard Dog
            "01022": 2,  # Evidence!
            "01023": 2,  # Dodge
            # Seeker cards
            "01025": 2,  # Magnifying Glass
            "01030": 1,  # Dr. Milan Christopher
            "01037": 2,  # Working a Hunch
            # Neutral cards
            "01088": 2,  # Emergency Cache
            "01089": 2,  # Guts
            "01090": 2,  # Overpower
            "01092": 1,  # Manual Dexterity
            # Required
            "01006": 1,  # Roland's .38 Special (signature)
            "01007": 1,  # Cover Up (weakness)
        }

        # All level 0 Guardian, Seeker, or Neutral
        card_details = []
        for code, count in cards.items():
            faction = "Guardian"
            if code.startswith("010") and int(code[2:4]) in range(25, 50):
                faction = "Seeker"
            if code in ["01088", "01089", "01090", "01092"]:
                faction = "Neutral"
            card_details.append({
                "code": code,
                "faction_code": faction,
                "xp": 0,
                "name": f"Card {code}",
            })

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints
        )

        assert result.valid, f"Errors: {[e.message for e in result.errors]}"
        assert result.card_count == 30

    def test_validation_result_summary(
        self, validator: DeckValidator, roland_constraints: DeckBuildingRules
    ):
        """Validation result summary is readable."""
        # Invalid deck
        cards = {"01050": 1}  # Mystic card
        card_details = [{"code": "01050", "faction_code": "Mystic", "xp": 0}]

        result = validator.validate(
            {"cards": cards}, card_details, roland_constraints
        )

        summary = result.summary()
        assert "invalid" in summary.lower()
        assert "1/30" in summary
