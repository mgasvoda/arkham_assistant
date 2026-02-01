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


class CostDistribution(BaseModel):
    """Distribution of card costs in opening hands."""

    cost_0: float = Field(ge=0.0, le=1.0, description="Proportion of 0-cost cards")
    cost_1: float = Field(ge=0.0, le=1.0, description="Proportion of 1-cost cards")
    cost_2: float = Field(ge=0.0, le=1.0, description="Proportion of 2-cost cards")
    cost_3: float = Field(ge=0.0, le=1.0, description="Proportion of 3-cost cards")
    cost_4_plus: float = Field(ge=0.0, le=1.0, description="Proportion of 4+ cost cards")
    no_cost: float = Field(ge=0.0, le=1.0, description="Proportion of cards with no cost (skills)")


class HandQualityBreakdown(BaseModel):
    """Breakdown of hand quality score components."""

    key_card_component: float = Field(
        ge=0.0, le=30.0, description="Points from key card presence (0-30)"
    )
    cost_component: float = Field(ge=0.0, le=35.0, description="Points from cost balance (0-35)")
    type_mix_component: float = Field(
        ge=0.0, le=35.0, description="Points from card type diversity (0-35)"
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


class SimulationMetrics(BaseModel):
    """Aggregate performance metrics from simulation."""

    # Setup and key card metrics
    avg_setup_time: float = Field(description="Average turns to play 2+ assets")
    avg_draws_to_key_card: float | None = Field(
        default=None,
        description="Average turn when first key card is drawn",
    )
    success_rate: float = Field(ge=0.0, le=1.0, description="Rate of key card by turn 3")
    mulligan_rate: float = Field(ge=0.0, le=1.0, description="Rate of hands mulliganed")
    any_key_card_rate: float = Field(
        ge=0.0, le=1.0, description="Rate of at least one key card in opening"
    )

    # Resource analysis
    avg_hand_cost: float = Field(ge=0.0, description="Average total cost of opening hand")
    cost_distribution: CostDistribution = Field(
        description="Distribution of card costs in opening hands"
    )
    playable_turn_1_rate: float = Field(
        ge=0.0, le=1.0, description="Rate of hands with at least one 0-1 cost card"
    )

    # Hand quality
    hand_quality_score: float = Field(
        ge=0.0, le=100.0, description="Composite hand quality score (0-100)"
    )
    hand_quality_breakdown: HandQualityBreakdown = Field(
        description="Breakdown of quality score components"
    )


class SimulationResult(BaseModel):
    """Complete results from a simulation run."""

    deck_id: str | None = Field(
        default=None,
        description="ID of the simulated deck (if loaded from storage)",
    )
    n_trials: int = Field(description="Number of simulation trials run")
    mulligan_strategy: str = Field(description="Mulligan strategy used for simulation")
    metrics: SimulationMetrics = Field(
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
    recommendations: list[str] = Field(
        default_factory=list,
        description="Suggestions for improving deck consistency",
    )
