"""Shared pytest fixtures."""

import pytest


@pytest.fixture
def sample_deck():
    """Fixture providing a test deck."""
    return {
        "id": "test_deck_001",
        "name": "Test Deck",
        "character_id": "01001",
        "card_list": ["01001", "01002", "01003"],
        "archetype": "clue",
        "notes": "Test deck for unit tests",
    }


@pytest.fixture
def sample_card():
    """Fixture providing a test card."""
    return {
        "id": "01001",
        "name": "Roland Banks",
        "class": "guardian",
        "cost": 0,
        "type": "investigator",
        "text": "Roland Banks investigator card",
        "owned": True,
    }

