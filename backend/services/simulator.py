"""Monte Carlo deck simulation engine for opening hand analysis.

This module implements Monte Carlo simulation for Arkham Horror LCG decks,
analyzing opening hand consistency, mulligan effectiveness, and key card
reliability through repeated random trials.
"""

from __future__ import annotations

import random
from statistics import mean

from backend.models.simulation_models import (
    CostDistribution,
    HandQualityBreakdown,
    KeyCardStats,
    MulliganStrategy,
    SimulationConfig,
)
from backend.services.chroma_client import ChromaClient
from backend.services.subagents.utils import CardDataLoader

# =============================================================================
# Deck Loading
# =============================================================================


def _load_deck(
    deck_id: str | None,
    card_list: list | None,
    loader: CardDataLoader,
    client: ChromaClient,
) -> tuple[list[dict], list[str]]:
    """Load deck and expand to shuffleable card list.

    Args:
        deck_id: ID of deck to load from ChromaDB.
        card_list: Alternative direct card list.
        loader: CardDataLoader instance.
        client: ChromaDB client instance.

    Returns:
        Tuple of (card_data_list, expanded_ids):
        - card_data_list: List of unique card dicts with full data
        - expanded_ids: Flat list of card IDs for shuffling
    """
    if deck_id:
        deck = client.get_deck(deck_id)
        if deck is None:
            raise ValueError(f"Deck not found: {deck_id}")
        cards_data = deck.get("cards", [])
    else:
        cards_data = card_list or []

    if not cards_data:
        raise ValueError("No cards provided for simulation")

    # Normalize to ID -> count mapping
    card_counts = loader.normalize_card_input(cards_data)

    # Fetch full card data
    card_data_list = loader.fetch_cards(
        list(card_counts.keys()),
        include_counts=card_counts,
        parse_json=True,
    )

    # Expand to shuffleable list
    expanded_ids = []
    for card in card_data_list:
        card_id = card.get("code") or card.get("id")
        count = card.get("count", 1)
        expanded_ids.extend([card_id] * count)

    return card_data_list, expanded_ids


def _validate_deck_size(expanded_ids: list[str]) -> list[str]:
    """Validate deck size and return warnings if issues found."""
    warnings = []
    deck_size = len(expanded_ids)
    if deck_size < 30:
        warnings.append(
            f"Deck has only {deck_size} cards (expected 30). "
            "Results may not reflect typical gameplay."
        )
    elif deck_size > 30:
        warnings.append(
            f"Deck has {deck_size} cards (expected 30). "
            "This may indicate data issues or special rules."
        )
    return warnings


# =============================================================================
# Key Card Detection
# =============================================================================


def _detect_key_cards(
    cards: list[dict],
    user_specified: list[str] | None,
    auto_detect: bool,
) -> set[str]:
    """Detect key cards for tracking in simulation.

    Key cards are cards that are important for the deck's strategy.
    They can be user-specified or auto-detected based on card properties.

    Auto-detection includes:
    - Assets with cost <= 2 (cheap setup pieces)
    - Cards with resource generation
    - Cards with card draw effects

    Args:
        cards: Full card data from deck.
        user_specified: Card IDs explicitly marked as key.
        auto_detect: Whether to auto-detect additional key cards.

    Returns:
        Set of card IDs considered key cards.
    """
    key_cards = set(user_specified or [])

    if not auto_detect:
        return key_cards

    for card in cards:
        card_id = card.get("code") or card.get("id")
        if not card_id:
            continue

        # Cheap assets (cost <= 2) are often key setup pieces
        if card.get("type_name") == "Asset":
            cost = card.get("cost")
            if cost is not None and cost <= 2:
                key_cards.add(card_id)

        # Check card text for key effects
        text = (card.get("text") or "").lower()

        # Resource generators
        if "gain" in text and "resource" in text:
            key_cards.add(card_id)

        # Card draw effects
        if "draw" in text and "card" in text:
            key_cards.add(card_id)

    return key_cards


# =============================================================================
# Mulligan Evaluation
# =============================================================================


def _should_mulligan(
    hand: list[str],
    key_cards: set[str],
    card_data: dict[str, dict],
    strategy: MulliganStrategy,
) -> bool:
    """Evaluate whether to mulligan the opening hand.

    Args:
        hand: List of card IDs in opening hand.
        key_cards: Set of key card IDs to look for.
        card_data: Dict mapping card_id -> card info.
        strategy: Mulligan strategy to apply.

    Returns:
        True if hand should be mulliganed, False otherwise.
    """
    if strategy == MulliganStrategy.NONE:
        return False

    if strategy == MulliganStrategy.FULL:
        return True

    if strategy == MulliganStrategy.AGGRESSIVE:
        # Keep if any key card is present
        if any(card_id in key_cards for card_id in hand):
            return False

        # Also keep if we have a resource generator
        for card_id in hand:
            card = card_data.get(card_id, {})
            text = (card.get("text") or "").lower()
            if "gain" in text and "resource" in text:
                return False

        return True

    if strategy == MulliganStrategy.CONSERVATIVE:
        # Count cards playable by turn 2 (cost <= 3 with starting resources)
        playable_count = 0
        for card_id in hand:
            card = card_data.get(card_id, {})
            cost = card.get("cost")
            if cost is not None and cost <= 3:
                playable_count += 1

        # Only mulligan truly terrible hands
        return playable_count < 2

    return False


# =============================================================================
# Trial Execution
# =============================================================================


def _run_trial(
    deck_ids: list[str],
    card_data: dict[str, dict],
    key_cards: set[str],
    strategy: MulliganStrategy,
    rng: random.Random,
) -> dict:
    """Execute a single Monte Carlo trial.

    Args:
        deck_ids: List of card IDs representing the full deck.
        card_data: Dict mapping card_id -> card info.
        key_cards: Set of key card IDs to track.
        strategy: Mulligan strategy to apply.
        rng: Random number generator instance.

    Returns:
        Dict with trial results including hand composition and metrics.
    """
    # Shuffle deck
    deck = deck_ids.copy()
    rng.shuffle(deck)

    # Draw opening hand (5 cards)
    opening_hand = deck[:5]
    remaining_deck = deck[5:]

    # Evaluate mulligan
    mulliganed = _should_mulligan(opening_hand, key_cards, card_data, strategy)

    if mulliganed:
        # Return hand to deck, shuffle, draw new 5
        full_deck = opening_hand + remaining_deck
        rng.shuffle(full_deck)
        final_hand = full_deck[:5]
        remaining_deck = full_deck[5:]
    else:
        final_hand = opening_hand

    # Track key cards in final hand
    key_cards_in_hand = [cid for cid in final_hand if cid in key_cards]

    # Find turn when first key card is drawn (0 = in opening hand)
    turns_to_key_card = _find_first_key_card_turn(final_hand, remaining_deck, key_cards)

    # Calculate setup time (turns until 2+ assets playable)
    setup_time = _calculate_setup_time(final_hand, remaining_deck, card_data)

    # Calculate hand cost
    hand_cost = _calculate_hand_cost(final_hand, card_data)

    # Check if playable turn 1
    playable_turn_1 = _has_playable_turn_1(final_hand, card_data)

    # Calculate hand quality
    quality_score, quality_breakdown = _calculate_hand_quality(final_hand, key_cards, card_data)

    # Track cost distribution for this hand
    cost_counts = {
        "cost_0": 0,
        "cost_1": 0,
        "cost_2": 0,
        "cost_3": 0,
        "cost_4_plus": 0,
        "no_cost": 0,
    }
    for card_id in final_hand:
        card = card_data.get(card_id, {})
        bucket = _get_cost_bucket(card.get("cost"))
        cost_counts[bucket] += 1

    return {
        "opening_hand": opening_hand,
        "final_hand": final_hand,
        "mulliganed": mulliganed,
        "key_cards_in_hand": key_cards_in_hand,
        "turns_to_key_card": turns_to_key_card,
        "setup_time": setup_time,
        "hand_cost": hand_cost,
        "playable_turn_1": playable_turn_1,
        "quality_score": quality_score,
        "quality_breakdown": quality_breakdown,
        "cost_counts": cost_counts,
    }


def _find_first_key_card_turn(
    hand: list[str],
    deck: list[str],
    key_cards: set[str],
    max_turns: int = 5,
) -> int | None:
    """Find the turn when first key card is drawn.

    Args:
        hand: Opening hand card IDs.
        deck: Remaining deck card IDs.
        key_cards: Set of key card IDs.
        max_turns: Maximum turns to simulate.

    Returns:
        Turn number (0 = opening hand) or None if not found.
    """
    # Check opening hand (turn 0)
    if any(cid in key_cards for cid in hand):
        return 0

    # Check subsequent draws (1 card per turn)
    for turn in range(1, max_turns + 1):
        if turn - 1 < len(deck) and deck[turn - 1] in key_cards:
            return turn

    return None


def _calculate_setup_time(
    hand: list[str],
    deck: list[str],
    card_data: dict[str, dict],
    max_turns: int = 5,
) -> int:
    """Calculate turns until 2+ assets are playable.

    Simulates a simplified game flow where:
    - Player starts with 5 resources
    - Gains 1 resource per turn
    - Draws 1 card per turn (after turn 0)
    - Plays cheapest assets first

    Args:
        hand: Opening hand card IDs.
        deck: Remaining deck card IDs.
        card_data: Dict mapping card_id -> card info.
        max_turns: Maximum turns to simulate.

    Returns:
        Turn number when 2+ assets have been played.
    """
    current_hand = list(hand)
    resources = 5  # Starting resources
    assets_played = 0

    for turn in range(max_turns + 1):
        # Gain resource at start of turn (turn 0 has starting resources)
        if turn > 0:
            resources += 1
            # Draw card
            if turn - 1 < len(deck):
                current_hand.append(deck[turn - 1])

        # Find playable assets sorted by cost (play cheapest first)
        playable = []
        for card_id in current_hand:
            card = card_data.get(card_id, {})
            if card.get("type_name") == "Asset":
                cost = card.get("cost") or 0
                if cost <= resources:
                    playable.append((cost, card_id))

        playable.sort()  # Sort by cost

        # Play assets while we can afford them
        for cost, card_id in playable:
            if cost <= resources:
                resources -= cost
                assets_played += 1
                current_hand.remove(card_id)

                if assets_played >= 2:
                    return turn

    return max_turns


# =============================================================================
# Hand Analysis Metrics
# =============================================================================


def _calculate_hand_cost(hand: list[str], card_data: dict[str, dict]) -> float:
    """Calculate total cost of cards in hand.

    Args:
        hand: List of card IDs in hand.
        card_data: Dict mapping card_id -> card info.

    Returns:
        Total resource cost of playable cards (skills have cost 0).
    """
    total = 0.0
    for card_id in hand:
        card = card_data.get(card_id, {})
        cost = card.get("cost")
        if cost is not None:
            total += cost
    return total


def _has_playable_turn_1(hand: list[str], card_data: dict[str, dict]) -> bool:
    """Check if hand has at least one card playable turn 1.

    A card is playable turn 1 if it costs 0 or 1 resources.
    Skills (no cost) are also considered playable.

    Args:
        hand: List of card IDs in hand.
        card_data: Dict mapping card_id -> card info.

    Returns:
        True if at least one playable card exists.
    """
    for card_id in hand:
        card = card_data.get(card_id, {})
        cost = card.get("cost")
        # Skills have no cost and are always playable
        if cost is None:
            continue
        # 0 or 1 cost cards are playable turn 1
        if cost <= 1:
            return True
    return False


def _calculate_hand_quality(
    hand: list[str],
    key_cards: set[str],
    card_data: dict[str, dict],
) -> tuple[float, HandQualityBreakdown]:
    """Calculate composite hand quality score (0-100).

    Score components:
    - Key card presence: 30 points max
    - Cost balance: 35 points max (based on playable cards)
    - Type mix: 35 points max (diversity of card types)

    Args:
        hand: List of card IDs in hand.
        key_cards: Set of key card IDs.
        card_data: Dict mapping card_id -> card info.

    Returns:
        Tuple of (total_score, breakdown).
    """
    # Key card component (0-30 points)
    has_key = any(cid in key_cards for cid in hand)
    key_card_points = 30.0 if has_key else 0.0

    # Cost balance component (0-35 points)
    # Award points for having low-cost playable cards
    playable_costs = []
    for card_id in hand:
        card = card_data.get(card_id, {})
        cost = card.get("cost")
        if cost is not None:
            playable_costs.append(cost)

    if playable_costs:
        # Score based on having cheap cards (0-2 cost is good)
        cheap_count = sum(1 for c in playable_costs if c <= 2)
        medium_count = sum(1 for c in playable_costs if c == 3)
        # Up to 35 points: 7 per cheap card, 3 per medium
        cost_points = min(35.0, cheap_count * 7.0 + medium_count * 3.0)
    else:
        # All skills, give partial credit
        cost_points = 15.0

    # Type mix component (0-35 points)
    # Penalize all-skill or all-expensive-asset hands
    type_counts = {"Asset": 0, "Event": 0, "Skill": 0}
    for card_id in hand:
        card = card_data.get(card_id, {})
        card_type = card.get("type_name", "")
        if card_type in type_counts:
            type_counts[card_type] += 1

    hand_size = len(hand)
    if hand_size > 0:
        # Check for excessive concentration
        skill_ratio = type_counts["Skill"] / hand_size
        asset_ratio = type_counts["Asset"] / hand_size

        # Base points for type diversity
        unique_types = sum(1 for c in type_counts.values() if c > 0)
        type_points = unique_types * 10.0  # Up to 30 for 3 types

        # Penalty for extreme concentration
        if skill_ratio > 0.7:
            type_points = max(0, type_points - 15.0)
        if asset_ratio > 0.8:
            type_points = max(0, type_points - 10.0)

        # Bonus for balanced mix
        if 0.2 <= skill_ratio <= 0.6 and 0.2 <= asset_ratio <= 0.6:
            type_points = min(35.0, type_points + 5.0)

        type_points = min(35.0, type_points)
    else:
        type_points = 0.0

    total = key_card_points + cost_points + type_points
    breakdown = HandQualityBreakdown(
        key_card_component=round(key_card_points, 1),
        cost_component=round(cost_points, 1),
        type_mix_component=round(type_points, 1),
    )

    return round(total, 1), breakdown


def _get_cost_bucket(cost: int | None) -> str:
    """Categorize card cost into distribution bucket."""
    if cost is None:
        return "no_cost"
    if cost == 0:
        return "cost_0"
    if cost == 1:
        return "cost_1"
    if cost == 2:
        return "cost_2"
    if cost == 3:
        return "cost_3"
    return "cost_4_plus"


# =============================================================================
# Metrics Aggregation
# =============================================================================


def _aggregate_metrics(
    trials: list[dict],
    key_cards: set[str],
    card_data: dict[str, dict],
) -> dict:
    """Aggregate statistics across all trials.

    Args:
        trials: List of trial result dicts.
        key_cards: Set of key card IDs.
        card_data: Dict mapping card_id -> card info.

    Returns:
        Dict with aggregated metrics.
    """
    n_trials = len(trials)

    # Mulligan rate
    mulligan_count = sum(1 for t in trials if t["mulliganed"])
    mulligan_rate = mulligan_count / n_trials

    # Average setup time
    setup_times = [t["setup_time"] for t in trials]
    avg_setup_time = mean(setup_times)

    # Average draws to key card (only counting trials where key card was found)
    key_card_turns = [t["turns_to_key_card"] for t in trials if t["turns_to_key_card"] is not None]
    avg_draws_to_key_card = mean(key_card_turns) if key_card_turns else None

    # Success rate (key card by turn 3)
    success_count = sum(
        1 for t in trials if t["turns_to_key_card"] is not None and t["turns_to_key_card"] <= 3
    )
    success_rate = success_count / n_trials

    # Any key card rate (at least one key card in opening hand)
    any_key_card_count = sum(1 for t in trials if len(t["key_cards_in_hand"]) > 0)
    any_key_card_rate = any_key_card_count / n_trials

    # Average hand cost
    hand_costs = [t["hand_cost"] for t in trials]
    avg_hand_cost = mean(hand_costs)

    # Playable turn 1 rate
    playable_count = sum(1 for t in trials if t["playable_turn_1"])
    playable_turn_1_rate = playable_count / n_trials

    # Average hand quality score
    quality_scores = [t["quality_score"] for t in trials]
    avg_quality_score = mean(quality_scores)

    # Average quality breakdown
    avg_key_component = mean(t["quality_breakdown"].key_card_component for t in trials)
    avg_cost_component = mean(t["quality_breakdown"].cost_component for t in trials)
    avg_type_component = mean(t["quality_breakdown"].type_mix_component for t in trials)
    avg_quality_breakdown = HandQualityBreakdown(
        key_card_component=round(avg_key_component, 1),
        cost_component=round(avg_cost_component, 1),
        type_mix_component=round(avg_type_component, 1),
    )

    # Aggregate cost distribution
    total_cards = n_trials * 5  # 5 cards per hand
    cost_totals = {
        "cost_0": 0,
        "cost_1": 0,
        "cost_2": 0,
        "cost_3": 0,
        "cost_4_plus": 0,
        "no_cost": 0,
    }
    for trial in trials:
        for bucket, count in trial["cost_counts"].items():
            cost_totals[bucket] += count

    cost_distribution = CostDistribution(
        cost_0=round(cost_totals["cost_0"] / total_cards, 3),
        cost_1=round(cost_totals["cost_1"] / total_cards, 3),
        cost_2=round(cost_totals["cost_2"] / total_cards, 3),
        cost_3=round(cost_totals["cost_3"] / total_cards, 3),
        cost_4_plus=round(cost_totals["cost_4_plus"] / total_cards, 3),
        no_cost=round(cost_totals["no_cost"] / total_cards, 3),
    )

    # Key card reliability per card
    key_card_stats = _calculate_key_card_stats(trials, key_cards, card_data)

    return {
        "avg_setup_time": round(avg_setup_time, 2),
        "avg_draws_to_key_card": (
            round(avg_draws_to_key_card, 2) if avg_draws_to_key_card else None
        ),
        "success_rate": round(success_rate, 3),
        "mulligan_rate": round(mulligan_rate, 3),
        "any_key_card_rate": round(any_key_card_rate, 3),
        "avg_hand_cost": round(avg_hand_cost, 2),
        "playable_turn_1_rate": round(playable_turn_1_rate, 3),
        "hand_quality_score": round(avg_quality_score, 1),
        "hand_quality_breakdown": avg_quality_breakdown,
        "cost_distribution": cost_distribution,
        "key_card_reliability": key_card_stats,
    }


def _calculate_key_card_stats(
    trials: list[dict],
    key_cards: set[str],
    card_data: dict[str, dict],
) -> dict[str, KeyCardStats]:
    """Calculate per-card statistics for key cards.

    Args:
        trials: List of trial result dicts.
        key_cards: Set of key card IDs.
        card_data: Dict mapping card_id -> card info.

    Returns:
        Dict mapping card_id -> KeyCardStats.
    """
    n_trials = len(trials)
    stats = {}

    for card_id in key_cards:
        card = card_data.get(card_id, {})
        card_name = card.get("name", card_id)

        # Count appearances in opening hand
        in_opening_count = sum(1 for t in trials if card_id in t["final_hand"])

        # Track turn drawn for this specific card
        turns_drawn = []
        by_turn_3_count = 0

        for trial in trials:
            # Check if in opening hand
            if card_id in trial["final_hand"]:
                turns_drawn.append(0)
                by_turn_3_count += 1
            else:
                # Would need to track per-card draws for more accurate stats
                # For now, use overall key card turn as approximation
                turn = trial["turns_to_key_card"]
                if turn is not None and card_id in trial.get("key_cards_in_hand", []):
                    turns_drawn.append(turn)
                    if turn <= 3:
                        by_turn_3_count += 1

        stats[card_id] = KeyCardStats(
            card_id=card_id,
            card_name=card_name,
            probability_in_opening=round(in_opening_count / n_trials, 3),
            probability_by_turn_3=round(by_turn_3_count / n_trials, 3),
            avg_turn_drawn=round(mean(turns_drawn), 2) if turns_drawn else None,
        )

    return stats


# =============================================================================
# Warning Generation
# =============================================================================


def _generate_warnings(
    metrics: dict,
    key_card_stats: dict[str, KeyCardStats],
) -> list[str]:
    """Generate human-readable warnings based on simulation results.

    Args:
        metrics: Aggregate metrics dict.
        key_card_stats: Per-card statistics.

    Returns:
        List of warning messages.
    """
    warnings = []

    # Slow setup warning
    if metrics["avg_setup_time"] > 4:
        warnings.append(
            f"Slow setup: average {metrics['avg_setup_time']} turns to play 2 assets. "
            "Consider adding more low-cost assets."
        )

    # Low success rate warning
    if metrics["success_rate"] < 0.5:
        warnings.append(
            f"Low consistency: only {metrics['success_rate'] * 100:.0f}% of games "
            "have a key card by turn 3. Consider adding redundancy."
        )

    # High mulligan rate warning
    if metrics["mulligan_rate"] > 0.6:
        warnings.append(
            f"High mulligan rate ({metrics['mulligan_rate'] * 100:.0f}%). "
            "Opening hands may lack consistency."
        )

    # Key card specific warnings
    for card_id, stats in key_card_stats.items():
        if stats.probability_by_turn_3 < 0.3:
            warnings.append(
                f"Key card '{stats.card_name}' is unreliable: only "
                f"{stats.probability_by_turn_3 * 100:.0f}% chance by turn 3."
            )

    return warnings


def _generate_recommendations(
    metrics: dict,
    key_card_stats: dict[str, KeyCardStats],
) -> list[str]:
    """Generate actionable recommendations based on simulation results.

    Args:
        metrics: Aggregate metrics dict.
        key_card_stats: Per-card statistics.

    Returns:
        List of recommendation messages.
    """
    recommendations = []

    # Low hand quality score
    if metrics["hand_quality_score"] < 50:
        breakdown = metrics["hand_quality_breakdown"]
        if breakdown.key_card_component < 15:
            recommendations.append(
                "Consider adding more key cards or redundant effects to improve "
                "opening hand reliability."
            )
        if breakdown.cost_component < 15:
            recommendations.append(
                "Too many expensive cards. Add more 0-2 cost cards for better early game options."
            )
        if breakdown.type_mix_component < 15:
            recommendations.append(
                "Card type balance is poor. Consider diversifying between assets, "
                "events, and skills."
            )

    # High average hand cost
    if metrics["avg_hand_cost"] > 12.5:  # Average 2.5 per card * 5 cards
        recommendations.append(
            f"Average hand cost is high ({metrics['avg_hand_cost']:.1f} resources). "
            "This may slow down early game tempo."
        )

    # Low playable turn 1 rate
    if metrics["playable_turn_1_rate"] < 0.6:
        recommendations.append(
            f"Only {metrics['playable_turn_1_rate'] * 100:.0f}% of opening hands "
            "have a playable turn 1 card. Add more 0-1 cost cards."
        )

    # Low any key card rate
    if metrics["any_key_card_rate"] < 0.4:
        recommendations.append(
            f"Key card presence is low ({metrics['any_key_card_rate'] * 100:.0f}%). "
            "Consider adding more copies of key cards or similar effects."
        )

    # Cost distribution issues
    cost_dist = metrics["cost_distribution"]
    cheap_ratio = cost_dist.cost_0 + cost_dist.cost_1 + cost_dist.cost_2
    expensive_ratio = cost_dist.cost_4_plus

    if cheap_ratio < 0.3:
        recommendations.append(
            "Deck is top-heavy with few cheap cards. Add more 0-2 cost options for flexibility."
        )

    if expensive_ratio > 0.3:
        recommendations.append(
            f"{expensive_ratio * 100:.0f}% of cards cost 4+. Consider reducing "
            "expensive cards for better curve."
        )

    return recommendations


# =============================================================================
# Main Entry Point
# =============================================================================


def run_simulation(
    deck_id: str | None = None,
    card_list: list[str] | None = None,
    n_trials: int = 1000,
    config: dict | None = None,
) -> dict:
    """Run Monte Carlo simulation for deck performance.

    This is the main entry point for deck simulation. It executes multiple
    random trials to analyze opening hand consistency, mulligan effectiveness,
    and key card reliability.

    Args:
        deck_id: ID of deck to simulate (fetches from ChromaDB).
        card_list: Direct card list (alternative to deck_id).
        n_trials: Number of simulation trials to run.
        config: Simulation configuration dict with optional keys:
            - mulligan_strategy: "none", "full", "aggressive", "conservative"
            - key_cards: List of card IDs to track
            - auto_detect_key_cards: Whether to auto-detect key cards (default True)
            - seed: Random seed for reproducibility

    Returns:
        Dictionary with simulation metrics including:
        - deck_id: ID of simulated deck (if provided)
        - n_trials: Number of trials run
        - metrics: Aggregate performance metrics
        - key_card_reliability: Per-card statistics
        - warnings: List of generated warnings
    """
    # Parse config
    sim_config = SimulationConfig(**(config or {}))

    # Initialize RNG (for reproducibility)
    rng = random.Random(sim_config.seed)

    # Initialize loader and client
    client = ChromaClient()
    loader = CardDataLoader(client)

    # Load deck
    card_data_list, expanded_ids = _load_deck(deck_id, card_list, loader, client)

    # Validate deck size
    warnings = _validate_deck_size(expanded_ids)

    # Build card lookup dict
    card_data = {(c.get("code") or c.get("id")): c for c in card_data_list}

    # Detect key cards
    key_cards = _detect_key_cards(
        card_data_list,
        user_specified=sim_config.key_cards,
        auto_detect=sim_config.auto_detect_key_cards,
    )

    # Run trials
    trials = []
    for _ in range(n_trials):
        result = _run_trial(
            deck_ids=expanded_ids,
            card_data=card_data,
            key_cards=key_cards,
            strategy=sim_config.mulligan_strategy,
            rng=rng,
        )
        trials.append(result)

    # Aggregate metrics
    metrics = _aggregate_metrics(trials, key_cards, card_data)
    key_card_reliability = metrics.pop("key_card_reliability", {})

    # Generate warnings and recommendations
    warnings.extend(_generate_warnings(metrics, key_card_reliability))
    recommendations = _generate_recommendations(metrics, key_card_reliability)

    # Convert Pydantic models to dicts for JSON serialization
    metrics_dict = {
        **metrics,
        "hand_quality_breakdown": metrics["hand_quality_breakdown"].model_dump(),
        "cost_distribution": metrics["cost_distribution"].model_dump(),
    }

    return {
        "deck_id": deck_id,
        "n_trials": n_trials,
        "mulligan_strategy": sim_config.mulligan_strategy.value,
        "metrics": metrics_dict,
        "key_card_reliability": {
            cid: stats.model_dump() for cid, stats in key_card_reliability.items()
        },
        "warnings": warnings,
        "recommendations": recommendations,
    }
