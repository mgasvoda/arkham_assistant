"""AI agent tool functions.

These functions are called as tools by the LLM agent during chat interactions.
They provide access to card data, deck information, and static reference content.

This module provides both:
1. Core functions (get_card_details, get_deck, etc.) for direct Python usage
2. LangGraph tool wrappers (card_lookup_tool, deck_lookup_tool, etc.) for agent integration
"""

import json
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.models.deck_builder_models import DeckSummary, Recommendation
from backend.services.chroma_client import ChromaClient
from backend.services.subagents.utils import CardDataLoader

# Module-level instances (lazy initialization)
_chroma_client: ChromaClient | None = None
_card_loader: CardDataLoader | None = None


def _get_client() -> ChromaClient:
    """Get or create the ChromaDB client instance."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = ChromaClient()
    return _chroma_client


def _get_card_loader() -> CardDataLoader:
    """Get or create the CardDataLoader instance."""
    global _card_loader
    if _card_loader is None:
        _card_loader = CardDataLoader(_get_client())
    return _card_loader


class CardNotFoundError(Exception):
    """Raised when a requested card is not found in the database."""

    pass


class DeckNotFoundError(Exception):
    """Raised when a requested deck is not found in the database."""

    pass


class StaticFileNotFoundError(Exception):
    """Raised when a requested static file is not found."""

    pass


def get_card_details(card_ids: list[str]) -> list[dict]:
    """Query ChromaDB for specific cards by ID.

    Args:
        card_ids: List of card IDs to retrieve

    Returns:
        List of card dictionaries with full card data (cost, type, text, icons, etc.)

    Raises:
        CardNotFoundError: If any of the requested cards are not found
    """
    if not card_ids:
        return []

    loader = _get_card_loader()
    cards = loader.fetch_cards(card_ids, parse_json=True)

    # Check if any cards were not found
    found_ids = {card.get("code") or card.get("id") for card in cards}
    not_found = [cid for cid in card_ids if cid not in found_ids]

    if not_found:
        raise CardNotFoundError(f"Cards not found: {', '.join(not_found)}")

    return cards


def get_deck(deck_id: str) -> dict:
    """Retrieve deck definition from ChromaDB.

    Args:
        deck_id: ID of deck to retrieve

    Returns:
        Deck dictionary with investigator, card list, and metadata

    Raises:
        DeckNotFoundError: If the deck is not found
    """
    if not deck_id:
        raise DeckNotFoundError("Deck ID cannot be empty")

    client = _get_client()
    deck = client.get_deck(deck_id)

    if deck is None:
        raise DeckNotFoundError(f"Deck not found: {deck_id}")

    # Parse JSON fields if they exist
    if "cards" in deck and isinstance(deck["cards"], str):
        try:
            deck["cards"] = json.loads(deck["cards"])
        except (json.JSONDecodeError, TypeError):
            pass

    return deck


def run_simulation_tool(
    deck_id: str | None = None,
    card_list: list[str] | dict[str, int] | None = None,
    n_trials: int = 1000,
) -> dict:
    """Execute deck simulation via simulator service.

    This tool runs Monte Carlo simulations to analyze deck performance,
    including draw consistency, resource curves, and key card timing.

    Args:
        deck_id: ID of deck to simulate (for stored decks)
        card_list: Card list as IDs or {id: count} dict (for local decks)
        n_trials: Number of simulation trials (default 1000)

    Returns:
        Simulation report with metrics including:
        - avg_setup_time: Average turns to establish board state
        - avg_draws_to_key_card: Turns to draw critical cards
        - success_rate: Percentage of successful runs
        - mulligan_rate: Recommended mulligan frequency
        - resource_efficiency: Resource utilization score
        - key_card_reliability: Consistency of key card draws
    """
    from backend.services.simulator import run_simulation

    # Convert dict card_list to flat list if needed
    expanded_card_list = None
    if card_list:
        if isinstance(card_list, dict):
            expanded_card_list = []
            for card_id, count in card_list.items():
                for _ in range(count):
                    expanded_card_list.append(card_id)
        else:
            expanded_card_list = list(card_list)

    try:
        return run_simulation(
            deck_id=deck_id,
            card_list=expanded_card_list,
            n_trials=n_trials,
            config={"mulligan_strategy": "aggressive"},
        )
    except Exception as e:
        return {"error": str(e), "deck_id": deck_id}


def get_static_info(topic: str) -> str:
    """Read markdown files from /backend/static/.

    Provides access to reference documentation for the AI agent including
    game rules, meta analysis, and user's owned card sets.

    Args:
        topic: Topic to read. Supported values:
            - "rules": Game rules overview (rules_overview.md)
            - "meta": Current meta trends and strategies (meta_trends.md)
            - "owned_sets" or "owned": User's owned card sets (owned_sets.md)
            - "investigator:<name>": Investigator-specific info (future)

    Returns:
        Contents of the requested markdown file

    Raises:
        StaticFileNotFoundError: If the topic doesn't map to a valid file
    """
    # Map topics to file names
    topic_map = {
        "rules": "rules_overview.md",
        "meta": "meta_trends.md",
        "owned_sets": "owned_sets.md",
        "owned": "owned_sets.md",
    }

    # Handle investigator subtopics (future expansion)
    if topic.startswith("investigator:"):
        # For now, return meta trends which contains archetype info
        # Future: create individual investigator files
        filename = "meta_trends.md"
    else:
        filename = topic_map.get(topic.lower())

    if filename is None:
        available = list(topic_map.keys()) + ["investigator:<name>"]
        raise StaticFileNotFoundError(
            f"Unknown topic: '{topic}'. Available topics: {available}"
        )

    # Build path to static file
    static_dir = Path(__file__).parent.parent / "static"
    file_path = static_dir / filename

    if not file_path.exists():
        raise StaticFileNotFoundError(f"Static file not found: {filename}")

    return file_path.read_text(encoding="utf-8")


def recommend_cards(deck_id: str, goal: str = "balance") -> list[Recommendation]:
    """Analyze deck composition and suggest card recommendations.

    This function analyzes a deck's composition and suggests cards to add or
    remove based on the specified optimization goal. It examines the current
    deck structure and identifies gaps or improvements.

    Args:
        deck_id: ID of deck to analyze
        goal: Optimization goal. Supported values:
            - "balance": Overall deck balance
            - "card_draw": Improve card draw consistency
            - "economy": Better resource generation
            - "combat": Enhanced enemy handling
            - "clues": Improved investigation efficiency

    Returns:
        List of Recommendation objects with suggested changes.

    Raises:
        DeckNotFoundError: If the deck is not found
    """
    # Get deck and analyze its composition
    # Validate deck exists (raises DeckNotFoundError if not)
    get_deck(deck_id)
    summary = summarize_deck(deck_id)

    recommendations: list[Recommendation] = []
    type_dist = summary.get("type_breakdown", {})
    total = summary.get("total_cards", 0)

    if total == 0:
        return recommendations

    # Calculate ratios
    asset_count = type_dist.get("Asset", 0)
    event_count = type_dist.get("Event", 0)
    skill_count = type_dist.get("Skill", 0)

    # Goal-specific analysis
    if goal == "card_draw":
        # Check if deck has enough draw
        if asset_count < total * 0.4:
            recommendations.append(Recommendation(
                action="add",
                card_id="01035",  # Lucky Cigarette Case (placeholder)
                card_name="Card Draw Asset",
                xp_cost=0,
                priority=1,
                reason="Deck lacks consistent card draw - add draw engine"
            ))

    elif goal == "economy":
        # Check resource curve
        curve = summary.get("curve", {})
        high_cost = sum(
            count for cost, count in curve.items()
            if cost.isdigit() and int(cost) >= 3
        )
        if high_cost > total * 0.4:
            recommendations.append(Recommendation(
                action="add",
                card_id="01073",  # Emergency Cache (placeholder)
                card_name="Resource Generator",
                xp_cost=0,
                priority=1,
                reason="High cost curve - add resource generation"
            ))

    elif goal == "combat":
        # Check for combat assets
        if asset_count < total * 0.3:
            recommendations.append(Recommendation(
                action="add",
                card_id="01016",  # Machete
                card_name="Combat Weapon",
                xp_cost=0,
                priority=1,
                reason="Deck needs more combat options"
            ))

    elif goal == "clues":
        # Check for investigation tools
        if asset_count < total * 0.3:
            recommendations.append(Recommendation(
                action="add",
                card_id="01036",  # Magnifying Glass
                card_name="Investigation Tool",
                xp_cost=0,
                priority=1,
                reason="Deck needs more investigation tools"
            ))

    else:  # balance
        # General balance recommendations
        if skill_count < total * 0.15:
            recommendations.append(Recommendation(
                action="add",
                card_id="01000",
                card_name="Skill Card",
                xp_cost=0,
                priority=2,
                reason="Low skill card count - add defensive skills"
            ))
        if event_count > total * 0.5:
            recommendations.append(Recommendation(
                action="swap",
                card_id="01000",
                card_name="Asset",
                remove_card_id="01000",
                remove_card_name="Event",
                xp_cost=0,
                priority=3,
                reason="Too many events - consider more permanent assets"
            ))

    return recommendations


def summarize_deck(deck_id: str) -> dict:
    """Generate high-level deck summary with composition analysis.

    Analyzes deck composition and returns metrics about resource curve,
    class distribution, and card type breakdown.

    Args:
        deck_id: ID of deck to summarize

    Returns:
        Summary dictionary containing:
        - deck_name: Name of the deck
        - investigator: Investigator name (if set)
        - total_cards: Total card count
        - curve: Dict mapping cost -> count (resource curve)
        - class_distribution: Dict mapping class -> count
        - type_breakdown: Dict mapping card type -> count
        - archetype: Deck archetype (if set)
        - key_cards: List of important cards (XP cards, core assets)

    Raises:
        DeckNotFoundError: If the deck is not found
    """
    # Get deck data
    deck = get_deck(deck_id)

    # Initialize summary
    summary = {
        "deck_name": deck.get("name", "Unknown"),
        "investigator": deck.get("investigator_name"),
        "total_cards": 0,
        "curve": {},  # cost -> count
        "class_distribution": {},  # class -> count
        "type_breakdown": {},  # type -> count
        "archetype": deck.get("archetype"),
        "key_cards": [],  # Important cards
    }

    # Get card list from deck
    cards_data = deck.get("cards", [])
    if not cards_data:
        return summary

    # Parse cards if it's a string
    if isinstance(cards_data, str):
        try:
            cards_data = json.loads(cards_data)
        except (json.JSONDecodeError, TypeError):
            return summary

    # Use CardDataLoader to normalize input and fetch card data
    loader = _get_card_loader()
    card_counts = loader.normalize_card_input(cards_data)

    # Track cards for key_cards selection
    card_details: list[tuple[str, dict, int]] = []

    # Fetch card details (don't fail on missing cards)
    for card_id, count in card_counts.items():
        card = _get_client().get_card(card_id)
        if card is None:
            continue

        card_details.append((card_id, card, count))
        summary["total_cards"] += count

        # Resource curve (by cost)
        cost = card.get("cost", 0)
        if cost is not None:
            cost_key = str(cost)
            summary["curve"][cost_key] = summary["curve"].get(cost_key, 0) + count

        # Class distribution
        card_class = card.get("class_name") or card.get("class", "Unknown")
        summary["class_distribution"][card_class] = (
            summary["class_distribution"].get(card_class, 0) + count
        )

        # Type breakdown
        card_type = card.get("type_name") or card.get("type", "Unknown")
        summary["type_breakdown"][card_type] = (
            summary["type_breakdown"].get(card_type, 0) + count
        )

    # Identify key cards (XP cards, unique assets, signature cards)
    key_cards: list[str] = []
    for card_id, card, count in card_details:
        xp = card.get("xp", 0) or 0
        card_name = card.get("name", card_id)
        is_unique = card.get("is_unique", False)
        is_permanent = "Permanent" in str(card.get("traits", ""))

        # Key card criteria: XP > 0, unique, or permanent
        if xp > 0 or is_unique or is_permanent:
            key_cards.append(card_name)

    # Limit to top 5 key cards
    summary["key_cards"] = key_cards[:5]

    return summary


def get_deck_summary_model(deck_id: str) -> DeckSummary:
    """Generate a DeckSummary Pydantic model for a deck.

    This is a convenience wrapper around summarize_deck that returns
    a properly typed DeckSummary model instead of a dict.

    Args:
        deck_id: ID of deck to summarize

    Returns:
        DeckSummary model with deck composition analysis.

    Raises:
        DeckNotFoundError: If the deck is not found
    """
    summary = summarize_deck(deck_id)
    return DeckSummary(
        card_count=summary.get("total_cards", 0),
        curve=summary.get("curve", {}),
        type_distribution=summary.get("type_breakdown", {}),
        class_distribution=summary.get("class_distribution", {}),
        key_cards=summary.get("key_cards", []),
    )


# =============================================================================
# Pydantic Input Schemas for LangGraph Tools
# =============================================================================


class CardLookupInput(BaseModel):
    """Input schema for looking up cards by their IDs."""

    card_ids: list[str] = Field(
        description="List of card IDs to retrieve (e.g., ['01016', '01017'])"
    )


class DeckLookupInput(BaseModel):
    """Input schema for retrieving a deck by ID."""

    deck_id: str = Field(description="The unique identifier of the deck to retrieve")


class StaticInfoInput(BaseModel):
    """Input schema for retrieving static reference information."""

    topic: Literal["rules", "meta", "owned_sets", "owned"] = Field(
        description=(
            "The topic to retrieve. Options: "
            "'rules' (game rules), "
            "'meta' (current meta trends), "
            "'owned_sets' or 'owned' (user's card collection)"
        )
    )


class DeckSummaryInput(BaseModel):
    """Input schema for generating a deck summary."""

    deck_id: str = Field(description="The unique identifier of the deck to summarize")


class SimulationInput(BaseModel):
    """Input schema for running deck simulations."""

    deck_id: str | None = Field(
        default=None,
        description="The unique identifier of the deck to simulate (use if deck is stored)"
    )
    card_list: list[str] | dict[str, int] | None = Field(
        default=None,
        description="Card list as IDs or {id: count} dict (use for local decks not in database)"
    )
    n_trials: int = Field(
        default=1000,
        description="Number of simulation trials to run (default: 1000)",
        ge=1,
        le=10000,
    )


class RecommendationInput(BaseModel):
    """Input schema for getting card recommendations."""

    deck_id: str = Field(description="The unique identifier of the deck to analyze")
    goal: Literal["balance", "card_draw", "economy", "combat", "clues"] = Field(
        default="balance",
        description=(
            "Optimization goal: 'balance' (overall), 'card_draw' (consistency), "
            "'economy' (resources), 'combat' (enemies), 'clues' (investigation)"
        ),
    )


# =============================================================================
# LangGraph Tool Wrappers
# =============================================================================


@tool("card_lookup", args_schema=CardLookupInput)
def card_lookup_tool(card_ids: list[str]) -> str:
    """Look up detailed information about specific Arkham Horror LCG cards.

    Use this tool when you need to retrieve card details like cost, type,
    text, traits, or icons for one or more cards. Returns full card data
    from the database.
    """
    try:
        cards = get_card_details(card_ids)
        return json.dumps(cards, indent=2)
    except CardNotFoundError as e:
        return json.dumps({"error": str(e)})


@tool("deck_lookup", args_schema=DeckLookupInput)
def deck_lookup_tool(deck_id: str) -> str:
    """Retrieve a deck's full definition including investigator and card list.

    Use this tool when you need to see what cards are in a deck, who the
    investigator is, or access deck metadata like archetype and notes.
    """
    try:
        deck = get_deck(deck_id)
        return json.dumps(deck, indent=2)
    except DeckNotFoundError as e:
        return json.dumps({"error": str(e)})


@tool("static_info", args_schema=StaticInfoInput)
def static_info_tool(topic: str) -> str:
    """Retrieve reference information about game rules, meta, or card collection.

    Use this tool to access:
    - 'rules': Game rules overview (actions, resources, deck construction)
    - 'meta': Current meta trends and popular archetypes
    - 'owned_sets' or 'owned': User's card collection checklist
    """
    try:
        content = get_static_info(topic)
        return content
    except StaticFileNotFoundError as e:
        return f"Error: {e}"


@tool("deck_summary", args_schema=DeckSummaryInput)
def deck_summary_tool(deck_id: str) -> str:
    """Generate a summary analysis of a deck's composition.

    Use this tool to get an overview of a deck including:
    - Resource curve (cost distribution)
    - Class distribution (Guardian, Seeker, etc.)
    - Card type breakdown (Assets, Events, Skills)
    - Total card count and archetype
    """
    try:
        summary = summarize_deck(deck_id)
        return json.dumps(summary, indent=2)
    except DeckNotFoundError as e:
        return json.dumps({"error": str(e)})


@tool("run_simulation", args_schema=SimulationInput)
def simulation_tool(
    deck_id: str | None = None,
    card_list: list[str] | dict[str, int] | None = None,
    n_trials: int = 1000,
) -> str:
    """Run Monte Carlo simulations to analyze deck performance.

    Executes multiple random trials to analyze opening hand consistency,
    mulligan effectiveness, and key card reliability. Returns metrics like
    average setup time, success rate, and per-card statistics.

    Use deck_id for decks stored in the database, or card_list for local
    decks that aren't stored (e.g., AI-generated proposals).
    """
    if not deck_id and not card_list:
        return json.dumps({"error": "Either deck_id or card_list must be provided"})
    result = run_simulation_tool(deck_id=deck_id, card_list=card_list, n_trials=n_trials)
    return json.dumps(result, indent=2)


@tool("recommend_cards", args_schema=RecommendationInput)
def recommendation_tool(deck_id: str, goal: str = "balance") -> str:
    """Get card recommendations for improving a deck.

    Analyzes deck composition and suggests cards to add, remove, swap,
    or upgrade based on the specified optimization goal.
    """
    try:
        recommendations = recommend_cards(deck_id, goal)
        # Serialize Recommendation models to dicts for JSON output
        result = [rec.model_dump() for rec in recommendations]
        return json.dumps(result, indent=2)
    except DeckNotFoundError as e:
        return json.dumps({"error": str(e)})


# =============================================================================
# Tool Registry for Orchestrator
# =============================================================================

# List of all available LangGraph tools for binding to the LLM
AGENT_TOOLS = [
    card_lookup_tool,
    deck_lookup_tool,
    static_info_tool,
    deck_summary_tool,
    simulation_tool,
    recommendation_tool,
]

# Tools that are fully implemented (not stubs)
IMPLEMENTED_TOOLS = [
    card_lookup_tool,
    deck_lookup_tool,
    static_info_tool,
    deck_summary_tool,
    simulation_tool,
    recommendation_tool,
]

# Stub tools (placeholders for future implementation)
STUB_TOOLS: list = [
]

