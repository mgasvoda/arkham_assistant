"""Tests for Monte Carlo deck simulation engine."""

import random
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.models.simulation_models import (
    KeyCardStats,
    MulliganStrategy,
)
from backend.services.simulator import (
    _calculate_setup_time,
    _detect_key_cards,
    _find_first_key_card_turn,
    _generate_warnings,
    _run_trial,
    _should_mulligan,
    _validate_deck_size,
    run_simulation,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_cards():
    """Sample card data for testing."""
    return [
        {
            "code": "01016",
            "name": "Machete",
            "type_name": "Asset",
            "class_name": "Guardian",
            "cost": 3,
            "text": "Guardian only. +1 damage if enemy is alone.",
            "traits": ["Item", "Weapon", "Melee"],
        },
        {
            "code": "01020",
            "name": "Beat Cop",
            "type_name": "Asset",
            "class_name": "Guardian",
            "cost": 4,
            "text": "Guardian only. +1 Combat. Discard to deal 1 damage.",
            "traits": ["Ally", "Police"],
        },
        {
            "code": "01086",
            "name": "Emergency Cache",
            "type_name": "Event",
            "class_name": "Neutral",
            "cost": 0,
            "text": "Gain 3 resources.",
            "traits": ["Supply"],
        },
        {
            "code": "01088",
            "name": "Flashlight",
            "type_name": "Asset",
            "class_name": "Neutral",
            "cost": 2,
            "text": "Uses (3 supplies). Spend 1 supply: -2 shroud.",
            "traits": ["Item", "Tool"],
        },
        {
            "code": "01092",
            "name": "Knife",
            "type_name": "Asset",
            "class_name": "Neutral",
            "cost": 1,
            "text": "+1 Combat. Discard to deal +1 damage.",
            "traits": ["Item", "Weapon", "Melee"],
        },
        {
            "code": "01024",
            "name": "Vicious Blow",
            "type_name": "Skill",
            "class_name": "Guardian",
            "cost": None,
            "text": "If this test succeeds, deal +1 damage.",
            "traits": ["Practiced"],
        },
        {
            "code": "01039",
            "name": "Preposterous Sketches",
            "type_name": "Event",
            "class_name": "Seeker",
            "cost": 2,
            "text": "Draw 3 cards.",
            "traits": ["Insight"],
        },
    ]


@pytest.fixture
def sample_card_data(sample_cards):
    """Card data as lookup dict."""
    return {c["code"]: c for c in sample_cards}


@pytest.fixture
def sample_deck_ids():
    """Sample deck as list of card IDs (30 cards)."""
    # 15 unique cards, 2 copies each
    cards = [
        "01016",
        "01016",  # Machete x2
        "01020",
        "01020",  # Beat Cop x2
        "01086",
        "01086",  # Emergency Cache x2
        "01088",
        "01088",  # Flashlight x2
        "01092",
        "01092",  # Knife x2
        "01024",
        "01024",  # Vicious Blow x2
        "01039",
        "01039",  # Preposterous Sketches x2
    ]
    # Pad to 30 cards
    while len(cards) < 30:
        cards.extend(["01024", "01024"])  # More skills
    return cards[:30]


# =============================================================================
# Test Deck Validation
# =============================================================================


class TestDeckValidation:
    """Tests for deck validation."""

    def test_validate_deck_size_correct_size(self):
        """No warnings for 30-card deck."""
        deck = ["card"] * 30
        warnings = _validate_deck_size(deck)
        assert warnings == []

    def test_validate_deck_size_too_small(self):
        """Warning for undersized deck."""
        deck = ["card"] * 25
        warnings = _validate_deck_size(deck)
        assert len(warnings) == 1
        assert "only 25 cards" in warnings[0]

    def test_validate_deck_size_too_large(self):
        """Warning for oversized deck."""
        deck = ["card"] * 35
        warnings = _validate_deck_size(deck)
        assert len(warnings) == 1
        assert "35 cards" in warnings[0]


# =============================================================================
# Test Key Card Detection
# =============================================================================


class TestKeyCardDetection:
    """Tests for key card auto-detection."""

    def test_detect_key_cards_user_specified(self, sample_cards):
        """User-specified cards are always included."""
        key_cards = _detect_key_cards(
            sample_cards,
            user_specified=["01016", "custom_card"],
            auto_detect=False,
        )
        assert "01016" in key_cards
        assert "custom_card" in key_cards

    def test_detect_key_cards_auto_cheap_assets(self, sample_cards):
        """Auto-detects cheap assets (cost <= 2)."""
        key_cards = _detect_key_cards(
            sample_cards,
            user_specified=None,
            auto_detect=True,
        )
        # Flashlight (cost 2) and Knife (cost 1) should be detected
        assert "01088" in key_cards  # Flashlight
        assert "01092" in key_cards  # Knife
        # Machete (cost 3) and Beat Cop (cost 4) should NOT be detected
        assert "01016" not in key_cards  # Machete
        assert "01020" not in key_cards  # Beat Cop

    def test_detect_key_cards_auto_resource_generators(self, sample_cards):
        """Auto-detects resource generators."""
        key_cards = _detect_key_cards(
            sample_cards,
            user_specified=None,
            auto_detect=True,
        )
        # Emergency Cache has "Gain 3 resources"
        assert "01086" in key_cards

    def test_detect_key_cards_auto_card_draw(self, sample_cards):
        """Auto-detects card draw effects."""
        key_cards = _detect_key_cards(
            sample_cards,
            user_specified=None,
            auto_detect=True,
        )
        # Preposterous Sketches has "Draw 3 cards"
        assert "01039" in key_cards

    def test_detect_key_cards_disabled_auto_detect(self, sample_cards):
        """No auto-detection when disabled."""
        key_cards = _detect_key_cards(
            sample_cards,
            user_specified=None,
            auto_detect=False,
        )
        assert len(key_cards) == 0


# =============================================================================
# Test Mulligan Strategies
# =============================================================================


class TestMulliganStrategies:
    """Tests for mulligan strategy evaluation."""

    def test_mulligan_none_never_mulligans(self, sample_card_data):
        """NONE strategy always keeps hand."""
        hand = ["01016", "01020", "01024", "01024", "01024"]
        key_cards = {"01088"}  # Flashlight not in hand

        result = _should_mulligan(hand, key_cards, sample_card_data, MulliganStrategy.NONE)
        assert result is False

    def test_mulligan_full_always_mulligans(self, sample_card_data):
        """FULL strategy always mulligans."""
        hand = ["01088", "01092", "01086", "01086", "01086"]  # Great hand
        key_cards = {"01088"}

        result = _should_mulligan(hand, key_cards, sample_card_data, MulliganStrategy.FULL)
        assert result is True

    def test_mulligan_aggressive_keeps_key_card(self, sample_card_data):
        """AGGRESSIVE keeps hand with key card."""
        hand = ["01088", "01024", "01024", "01024", "01024"]  # Has Flashlight
        key_cards = {"01088"}

        result = _should_mulligan(hand, key_cards, sample_card_data, MulliganStrategy.AGGRESSIVE)
        assert result is False

    def test_mulligan_aggressive_keeps_resource_generator(self, sample_card_data):
        """AGGRESSIVE keeps hand with resource generator."""
        hand = ["01086", "01024", "01024", "01024", "01024"]  # Has Emergency Cache
        key_cards = {"01088"}  # Looking for Flashlight

        result = _should_mulligan(hand, key_cards, sample_card_data, MulliganStrategy.AGGRESSIVE)
        assert result is False

    def test_mulligan_aggressive_mulligans_no_key(self, sample_card_data):
        """AGGRESSIVE mulligans without key card or resources."""
        hand = ["01016", "01020", "01024", "01024", "01024"]  # No key cards
        key_cards = {"01088"}  # Looking for Flashlight

        result = _should_mulligan(hand, key_cards, sample_card_data, MulliganStrategy.AGGRESSIVE)
        assert result is True

    def test_mulligan_conservative_keeps_playable_hand(self, sample_card_data):
        """CONSERVATIVE keeps hand with 2+ playable cards."""
        hand = ["01088", "01092", "01016", "01020", "01024"]  # Flashlight, Knife playable
        key_cards = set()

        result = _should_mulligan(hand, key_cards, sample_card_data, MulliganStrategy.CONSERVATIVE)
        assert result is False

    def test_mulligan_conservative_mulligans_unplayable(self, sample_card_data):
        """CONSERVATIVE mulligans hand with < 2 playable cards."""
        # All skills (no cost) and expensive assets
        hand = ["01020", "01020", "01024", "01024", "01024"]  # Only Beat Cops (cost 4)
        # Create card_data without the cost=4 cards counting as playable
        card_data = {
            "01020": {"code": "01020", "cost": 4, "type_name": "Asset"},
            "01024": {"code": "01024", "cost": None, "type_name": "Skill"},
        }

        result = _should_mulligan(hand, set(), card_data, MulliganStrategy.CONSERVATIVE)
        # Only skills have no cost (None), Beat Cop is cost 4 (> 3)
        # So we have 0 playable cards (cost <= 3)
        assert result is True


# =============================================================================
# Test Trial Execution
# =============================================================================


class TestTrialExecution:
    """Tests for single trial execution."""

    def test_run_trial_draws_five_cards(self, sample_deck_ids, sample_card_data):
        """Trial draws 5 cards for opening hand."""
        rng = random.Random(42)
        key_cards = {"01088"}

        result = _run_trial(
            sample_deck_ids,
            sample_card_data,
            key_cards,
            MulliganStrategy.NONE,
            rng,
        )

        assert len(result["opening_hand"]) == 5
        assert len(result["final_hand"]) == 5

    def test_run_trial_mulligan_changes_hand(self, sample_deck_ids, sample_card_data):
        """Mulligan should produce different hand."""
        rng = random.Random(42)
        key_cards = set()  # No key cards - will trigger aggressive mulligan

        result = _run_trial(
            sample_deck_ids,
            sample_card_data,
            key_cards,
            MulliganStrategy.FULL,
            rng,
        )

        assert result["mulliganed"] is True
        # With FULL mulligan, final hand may differ from opening
        # (though could be same by random chance)

    def test_run_trial_reproducible_with_seed(self, sample_deck_ids, sample_card_data):
        """Same seed produces same results."""
        key_cards = {"01088"}

        rng1 = random.Random(12345)
        result1 = _run_trial(
            sample_deck_ids,
            sample_card_data,
            key_cards,
            MulliganStrategy.NONE,
            rng1,
        )

        rng2 = random.Random(12345)
        result2 = _run_trial(
            sample_deck_ids,
            sample_card_data,
            key_cards,
            MulliganStrategy.NONE,
            rng2,
        )

        assert result1["opening_hand"] == result2["opening_hand"]
        assert result1["final_hand"] == result2["final_hand"]


# =============================================================================
# Test Key Card Turn Tracking
# =============================================================================


class TestKeyCardTurnTracking:
    """Tests for key card turn detection."""

    def test_find_key_card_in_opening(self):
        """Key card in opening hand returns turn 0."""
        hand = ["01088", "01024", "01024", "01024", "01024"]
        deck = ["01016", "01020", "01086", "01092", "01024"]
        key_cards = {"01088"}

        result = _find_first_key_card_turn(hand, deck, key_cards)
        assert result == 0

    def test_find_key_card_on_draw(self):
        """Key card drawn on turn 2."""
        hand = ["01024", "01024", "01024", "01024", "01024"]
        deck = ["01016", "01088", "01086", "01092", "01020"]  # Flashlight at index 1
        key_cards = {"01088"}

        result = _find_first_key_card_turn(hand, deck, key_cards)
        assert result == 2  # Draw on turn 2 (index 1 in deck)

    def test_find_key_card_not_found(self):
        """Key card not found returns None."""
        hand = ["01024", "01024", "01024", "01024", "01024"]
        deck = ["01016", "01020", "01086", "01092", "01024"]
        key_cards = {"01088"}  # Flashlight not in hand or first 5 draws

        result = _find_first_key_card_turn(hand, deck, key_cards, max_turns=5)
        assert result is None


# =============================================================================
# Test Setup Time Calculation
# =============================================================================


class TestSetupTimeCalculation:
    """Tests for setup time calculation."""

    def test_setup_time_immediate(self, sample_card_data):
        """Two cheap assets can be played turn 0."""
        hand = ["01088", "01092", "01024", "01024", "01024"]  # Flashlight (2) + Knife (1)
        deck = []

        result = _calculate_setup_time(hand, deck, sample_card_data)
        # Starting with 5 resources, can play Flashlight (2) + Knife (1) = 3 total
        assert result == 0

    def test_setup_time_delayed(self, sample_card_data):
        """Expensive assets delay setup."""
        hand = ["01020", "01020", "01024", "01024", "01024"]  # Beat Cops cost 4 each
        deck = ["01024"] * 10

        result = _calculate_setup_time(hand, deck, sample_card_data)
        # Turn 0: 5 resources, play Beat Cop (4), have 1 left
        # Turn 1: 2 resources (1 + 1), not enough for Beat Cop
        # Turn 2: 3 resources
        # Turn 3: 4 resources, play second Beat Cop
        assert result == 3


# =============================================================================
# Test Warning Generation
# =============================================================================


class TestWarningGeneration:
    """Tests for warning generation."""

    def test_warning_slow_setup(self):
        """Warning for slow setup time."""
        metrics = {
            "avg_setup_time": 4.5,
            "success_rate": 0.8,
            "mulligan_rate": 0.3,
        }
        warnings = _generate_warnings(metrics, {})
        assert any("Slow setup" in w for w in warnings)

    def test_warning_low_success_rate(self):
        """Warning for low consistency."""
        metrics = {
            "avg_setup_time": 2.0,
            "success_rate": 0.4,
            "mulligan_rate": 0.3,
        }
        warnings = _generate_warnings(metrics, {})
        assert any("Low consistency" in w for w in warnings)

    def test_warning_high_mulligan_rate(self):
        """Warning for high mulligan rate."""
        metrics = {
            "avg_setup_time": 2.0,
            "success_rate": 0.8,
            "mulligan_rate": 0.7,
        }
        warnings = _generate_warnings(metrics, {})
        assert any("High mulligan rate" in w for w in warnings)

    def test_warning_unreliable_key_card(self):
        """Warning for unreliable key card."""
        metrics = {
            "avg_setup_time": 2.0,
            "success_rate": 0.8,
            "mulligan_rate": 0.3,
        }
        key_card_stats = {
            "01088": KeyCardStats(
                card_id="01088",
                card_name="Flashlight",
                probability_in_opening=0.1,
                probability_by_turn_3=0.2,
                avg_turn_drawn=4.0,
            )
        }
        warnings = _generate_warnings(metrics, key_card_stats)
        assert any("Flashlight" in w and "unreliable" in w for w in warnings)


# =============================================================================
# Test Integration
# =============================================================================


class TestSimulationIntegration:
    """Integration tests for full simulation."""

    @patch("backend.services.simulator.ChromaClient")
    @patch("backend.services.simulator.CardDataLoader")
    def test_run_simulation_returns_expected_schema(
        self, mock_loader_cls, mock_client_cls, sample_cards
    ):
        """run_simulation returns all expected fields."""
        # Setup mocks
        mock_loader = MagicMock()
        mock_loader.normalize_card_input.return_value = {c["code"]: 2 for c in sample_cards}
        mock_loader.fetch_cards.return_value = [{**c, "count": 2} for c in sample_cards]
        mock_loader_cls.return_value = mock_loader

        result = run_simulation(
            card_list=["01016"] * 30,
            n_trials=10,
            config={"seed": 42},
        )

        # Check required fields exist
        assert "deck_id" in result
        assert "n_trials" in result
        assert "metrics" in result
        assert "key_card_reliability" in result
        assert "warnings" in result

        # Check metrics structure
        assert "avg_setup_time" in result["metrics"]
        assert "avg_draws_to_key_card" in result["metrics"]
        assert "success_rate" in result["metrics"]
        assert "mulligan_rate" in result["metrics"]

    @patch("backend.services.simulator.ChromaClient")
    @patch("backend.services.simulator.CardDataLoader")
    def test_simulation_performance(self, mock_loader_cls, mock_client_cls, sample_cards):
        """1000 trials should complete in < 1 second."""
        # Setup mocks
        mock_loader = MagicMock()
        mock_loader.normalize_card_input.return_value = {c["code"]: 2 for c in sample_cards}
        mock_loader.fetch_cards.return_value = [{**c, "count": 2} for c in sample_cards]
        mock_loader_cls.return_value = mock_loader

        start = time.time()
        run_simulation(
            card_list=["01016"] * 30,
            n_trials=1000,
            config={"seed": 42},
        )
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Simulation took {elapsed:.2f}s, expected < 1s"

    @patch("backend.services.simulator.ChromaClient")
    @patch("backend.services.simulator.CardDataLoader")
    def test_simulation_reproducible_with_seed(
        self, mock_loader_cls, mock_client_cls, sample_cards
    ):
        """Same seed produces same results."""
        # Setup mocks
        mock_loader = MagicMock()
        mock_loader.normalize_card_input.return_value = {c["code"]: 2 for c in sample_cards}
        mock_loader.fetch_cards.return_value = [{**c, "count": 2} for c in sample_cards]
        mock_loader_cls.return_value = mock_loader

        result1 = run_simulation(
            card_list=["01016"] * 30,
            n_trials=100,
            config={"seed": 12345},
        )

        result2 = run_simulation(
            card_list=["01016"] * 30,
            n_trials=100,
            config={"seed": 12345},
        )

        assert result1["metrics"] == result2["metrics"]


# =============================================================================
# Test Statistical Properties
# =============================================================================


class TestStatisticalProperties:
    """Tests for statistical correctness."""

    def test_draw_probability_approximates_hypergeometric(self):
        """Verify draw probability matches expected distribution.

        For 2 copies of a card in a 30-card deck, drawing 5 cards:
        P(at least 1) = 1 - C(28,5)/C(30,5)
        = 1 - (28! * 25!) / (23! * 30!)
        = 1 - (28*27*26*25*24)/(30*29*28*27*26)
        = 1 - (25*24)/(30*29)
        = 1 - 600/870
        ≈ 0.31
        """
        # Create a deck with 2 copies of target card
        deck = ["target", "target"] + ["other"] * 28
        key_cards = {"target"}
        card_data = {
            "target": {"code": "target", "name": "Target", "type_name": "Asset", "cost": 1},
            "other": {"code": "other", "name": "Other", "type_name": "Skill", "cost": None},
        }

        # Run many trials with no mulligan
        rng = random.Random(42)
        in_opening_count = 0
        n_trials = 10000

        for _ in range(n_trials):
            result = _run_trial(deck, card_data, key_cards, MulliganStrategy.NONE, rng)
            if "target" in result["final_hand"]:
                in_opening_count += 1

        observed_rate = in_opening_count / n_trials
        expected_rate = 1 - (600 / 870)  # ≈ 0.31

        # Allow 5% tolerance for random variation
        assert abs(observed_rate - expected_rate) < 0.05, (
            f"Observed {observed_rate:.3f}, expected ~{expected_rate:.3f}"
        )
