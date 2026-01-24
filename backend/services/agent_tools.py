"""AI agent tool functions.

These functions are called as tools by the LLM agent during chat interactions.
They provide access to card data, deck information, and static reference content.
"""

import json
from pathlib import Path
from typing import Optional

from backend.services.chroma_client import ChromaClient


# Module-level client instance (lazy initialization)
_chroma_client: Optional[ChromaClient] = None


def _get_client() -> ChromaClient:
    """Get or create the ChromaDB client instance."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = ChromaClient()
    return _chroma_client


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

    client = _get_client()
    cards = []
    not_found = []

    for card_id in card_ids:
        card = client.get_card(card_id)
        if card is None:
            not_found.append(card_id)
        else:
            # Parse JSON fields if they exist
            for field in ["traits", "icons", "upgrades"]:
                if field in card and isinstance(card[field], str):
                    try:
                        card[field] = json.loads(card[field])
                    except (json.JSONDecodeError, TypeError):
                        pass  # Keep as string if not valid JSON
            cards.append(card)

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

    # Handle different card list formats
    # Format 1: List of card IDs ["01001", "01002"]
    # Format 2: List of dicts [{"id": "01001", "count": 2}]
    # Format 3: Dict mapping card_id -> count {"01001": 2}
    card_ids = []
    card_counts = {}

    if isinstance(cards_data, list):
        for item in cards_data:
            if isinstance(item, str):
                card_ids.append(item)
                card_counts[item] = card_counts.get(item, 0) + 1
            elif isinstance(item, dict):
                card_id = item.get("id") or item.get("code")
                if card_id:
                    count = item.get("count", 1)
                    card_ids.append(card_id)
                    card_counts[card_id] = count
    elif isinstance(cards_data, dict):
        for card_id, count in cards_data.items():
            card_ids.append(card_id)
            card_counts[card_id] = count

    # Remove duplicates while preserving order
    unique_card_ids = list(dict.fromkeys(card_ids))

    # Fetch card details (don't fail on missing cards)
    client = _get_client()
    for card_id in unique_card_ids:
        card = client.get_card(card_id)
        if card is None:
            continue

        count = card_counts.get(card_id, 1)
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

