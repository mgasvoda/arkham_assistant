"""Pydantic models for Monte Carlo deck simulation.

This module defines the configuration and result schemas for the
opening hand simulator. These models ensure type safety and
enable validation of simulation inputs and outputs.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class MulliganStrategy(str, Enum):
    """Mulligan strategy options for opening hand simulation."""

    NONE = "none"  # Keep initial hand always
    FULL = "full"  # Always mulligan entire hand
    AGGRESSIVE = "aggressive"  # Mulligan unless key card present
    CONSERVATIVE = "conservative"  # Only mulligan terrible hands


class SimulationConfig(BaseModel):
    """Configuration for a simulation run."""

    mulligan_strategy: MulliganStrategy = Field(
        default=MulliganStrategy.AGGRESSIVE,
        description="Strategy for evaluating mulligan decisions",
    )
    key_cards: list[str] | None = Field(
        default=None,
        description="User-specified key cards to track (card IDs)",
    )
    auto_detect_key_cards: bool = Field(
        default=True,
        description="Whether to auto-detect key cards based on card properties",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed for reproducibility",
    )


class KeyCardStats(BaseModel):
    """Statistics for a single key card across all trials."""

    card_id: str = Field(description="The card's unique identifier")
    card_name: str = Field(description="The card's display name")
    probability_in_opening: float = Field(
        ge=0.0,
        le=1.0,
        description="Probability of card appearing in opening hand",
    )
    probability_by_turn_3: float = Field(
        ge=0.0,
        le=1.0,
        description="Probability of drawing card by turn 3",
    )
    avg_turn_drawn: float | None = Field(
        default=None,
        description="Average turn when card is first drawn (None if never drawn)",
    )


class SimulationResult(BaseModel):
    """Complete results from a simulation run."""

    deck_id: str | None = Field(
        default=None,
        description="ID of the simulated deck (if loaded from storage)",
    )
    n_trials: int = Field(description="Number of simulation trials run")
    metrics: dict = Field(
        description="Aggregate performance metrics",
    )
    key_card_reliability: dict[str, KeyCardStats] = Field(
        default_factory=dict,
        description="Per-card statistics for key cards",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Generated warnings about deck performance",
    )
