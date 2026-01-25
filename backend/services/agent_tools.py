"""AI agent tool functions.

These functions are called as tools by the LLM agent during chat interactions.
They provide access to card data, deck information, and static reference content.

This module provides both:
1. Core functions (get_card_details, get_deck, etc.) for direct Python usage
2. LangGraph tool wrappers (card_lookup_tool, deck_lookup_tool, etc.) for agent integration
"""

import json
from pathlib import Path
from typing import Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.services.chroma_client import ChromaClient
from backend.services.subagents.utils import CardDataLoader


# Module-level instances (lazy initialization)
_chroma_client: Optional[ChromaClient] = None
_card_loader: Optional[CardDataLoader] = None


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


def run_simulation_tool(deck_id: str, n_trials: int = 1000) -> dict:
    """Execute deck simulation via simulator service.

    This tool runs Monte Carlo simulations to analyze deck performance,
    including draw consistency, resource curves, and key card timing.

    Note: This function is a stub and will be implemented in a later ticket.
    The simulator service (backend/services/simulator.py) needs to be
    completed first.

    Args:
        deck_id: ID of deck to simulate
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
    # TODO: Implement in ticket [1.4] - Deck Simulator
    # Will delegate to: from backend.services.simulator import run_simulation
    return {
        "error": "Simulation not yet implemented",
        "deck_id": deck_id,
        "n_trials": n_trials,
    }


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


def recommend_cards(deck_id: str, goal: str = "balance") -> list[dict]:
    """LLM-driven analysis of deck composition with card recommendations.

    This tool analyzes a deck's composition and suggests cards to add or
    remove based on the specified optimization goal.

    Note: This function is a stub and will be implemented in a later ticket.
    Requires LLM integration for intelligent card recommendations.

    Args:
        deck_id: ID of deck to analyze
        goal: Optimization goal. Supported values:
            - "balance": Overall deck balance
            - "card_draw": Improve card draw consistency
            - "economy": Better resource generation
            - "combat": Enhanced enemy handling
            - "clues": Improved investigation efficiency

    Returns:
        List of recommendation dictionaries, each containing:
        - card_id: Recommended card ID
        - card_name: Card name
        - action: "add" or "remove"
        - reason: Explanation for the recommendation
        - priority: 1-5 importance rating
    """
    # TODO: Implement in ticket [1.5] - Agent Orchestrator
    # Will use LLM analysis with deck context
    return []


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

    # Fetch card details (don't fail on missing cards)
    for card_id, count in card_counts.items():
        card = _get_client().get_card(card_id)
        if card is None:
            continue

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

    return summary


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

    deck_id: str = Field(description="The unique identifier of the deck to simulate")
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
def simulation_tool(deck_id: str, n_trials: int = 1000) -> str:
    """Run Monte Carlo simulations to analyze deck performance.

    Note: This tool is not yet implemented and will return a placeholder response.
    When implemented, it will provide metrics like draw consistency, resource
    curves, and key card timing.
    """
    result = run_simulation_tool(deck_id, n_trials)
    return json.dumps(result, indent=2)


@tool("recommend_cards", args_schema=RecommendationInput)
def recommendation_tool(deck_id: str, goal: str = "balance") -> str:
    """Get AI-powered card recommendations for improving a deck.

    Note: This tool is not yet implemented and will return an empty list.
    When implemented, it will suggest cards to add or remove based on the
    specified optimization goal.
    """
    result = recommend_cards(deck_id, goal)
    return json.dumps(result, indent=2)


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
]

# Stub tools (placeholders for future implementation)
STUB_TOOLS = [
    simulation_tool,
    recommendation_tool,
]

