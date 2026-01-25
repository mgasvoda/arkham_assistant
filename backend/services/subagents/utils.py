"""Common utilities for subagent implementations.

This module provides reusable utilities for:
- Query classification via keyword matching
- Confidence score computation with adjustments
- Card data loading and normalization (CardDataLoader)

These utilities extract common patterns that were duplicated across
multiple subagent implementations.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from backend.services.chroma_client import ChromaClient


def classify_query_by_keywords(
    query: str,
    patterns: dict[str, list[str]],
    default: str = "general",
) -> str:
    """Classify a query based on keyword patterns.

    The patterns dict maps query_type -> list of keywords to match.
    Patterns are checked in insertion order (Python 3.7+ dict ordering),
    so put more specific patterns first for priority matching.

    Args:
        query: The query string to classify.
        patterns: Dict mapping query_type -> keywords list.
            Each keyword is checked for substring presence in the query.
        default: Default type if no patterns match.

    Returns:
        The matched query type string.

    Example:
        >>> patterns = {
        ...     "taboo": ["taboo"],
        ...     "signature": ["signature", "required"],
        ...     "xp_rules": ["xp", "experience", "upgrade"],
        ...     "legality": ["legal", "include", "can "],
        ... }
        >>> classify_query_by_keywords("Can I include this card?", patterns, "general")
        'legality'
        >>> classify_query_by_keywords("What is the taboo list?", patterns, "general")
        'taboo'
    """
    query_lower = query.lower()
    for query_type, keywords in patterns.items():
        if any(keyword in query_lower for keyword in keywords):
            return query_type
    return default


def compute_bounded_confidence(
    base: float,
    adjustments: list[tuple[bool, float]],
    min_bound: float = 0.1,
    max_bound: float = 0.95,
) -> float:
    """Compute confidence score with conditional adjustments and bounds.

    This provides a standardized way to calculate confidence scores
    across subagents, with consistent bounds enforcement.

    Args:
        base: Starting confidence value (typically 0.5).
        adjustments: List of (condition, delta) tuples.
            If condition is True, delta is added to confidence.
            Positive deltas increase confidence, negative decrease.
        min_bound: Minimum confidence value (default 0.1).
        max_bound: Maximum confidence value (default 0.95).

    Returns:
        Bounded confidence score between min_bound and max_bound.

    Example:
        >>> # Rules agent confidence calculation
        >>> confidence = compute_bounded_confidence(
        ...     base=0.5,
        ...     adjustments=[
        ...         (True, 0.15),   # Has retrieved context
        ...         (True, 0.2),    # Contains "rules state"
        ...         (False, -0.15), # No uncertainty language
        ...     ],
        ... )
        >>> confidence
        0.85
    """
    confidence = base
    for condition, delta in adjustments:
        if condition:
            confidence += delta
    return max(min_bound, min(max_bound, confidence))


def contains_any_phrase(text: str, phrases: list[str]) -> bool:
    """Check if text contains any of the given phrases.

    This is a helper for building confidence adjustments.

    Args:
        text: Text to search in (will be lowercased).
        phrases: List of phrases to look for.

    Returns:
        True if any phrase is found in text.

    Example:
        >>> contains_any_phrase("The rules state clearly", ["rules state", "according to"])
        True
    """
    text_lower = text.lower()
    return any(phrase in text_lower for phrase in phrases)


# =============================================================================
# Card Data Loading
# =============================================================================


class CardDataLoader:
    """Utility class for loading and normalizing card data from ChromaDB.

    This class consolidates card loading logic that was previously duplicated
    across StateAgent and agent_tools. It handles:
    - Multiple input formats (list of IDs, list of dicts, dict mapping)
    - JSON field parsing (traits, icons, upgrades)
    - Card count tracking

    Example:
        >>> loader = CardDataLoader()
        >>> cards = loader.load_card_list(["01001", "01002"])
        >>> cards = loader.load_card_list({"01001": 2, "01002": 1})
        >>> cards = loader.load_card_list([{"id": "01001", "count": 2}])
    """

    # Fields that may contain JSON strings that need parsing
    JSON_FIELDS = ["traits", "icons", "upgrades"]

    def __init__(self, chroma_client: Optional[ChromaClient] = None) -> None:
        """Initialize the card data loader.

        Args:
            chroma_client: Optional ChromaDB client instance.
                If None, a client will be created lazily on first use.
        """
        self._client = chroma_client

    @property
    def client(self) -> ChromaClient:
        """Lazy-load ChromaDB client."""
        if self._client is None:
            from backend.services.chroma_client import ChromaClient
            self._client = ChromaClient()
        return self._client

    def normalize_card_input(self, cards_data: list | dict) -> dict[str, int]:
        """Normalize various card input formats to a consistent id->count mapping.

        Supported formats:
        - List of card IDs: ["01001", "01002"]
        - List of dicts: [{"id": "01001", "count": 2}] or [{"code": "01001"}]
        - Dict mapping: {"01001": 2, "01002": 1}

        Args:
            cards_data: Card list in any supported format.

        Returns:
            Dict mapping card_id -> count.

        Example:
            >>> loader = CardDataLoader()
            >>> loader.normalize_card_input(["01001", "01001", "01002"])
            {'01001': 2, '01002': 1}
            >>> loader.normalize_card_input({"01001": 2, "01002": 1})
            {'01001': 2, '01002': 1}
        """
        card_counts: dict[str, int] = {}

        if isinstance(cards_data, dict):
            # Dict mapping card_id -> count
            for card_id, count in cards_data.items():
                card_counts[card_id] = count

        elif isinstance(cards_data, list):
            for item in cards_data:
                if isinstance(item, str):
                    # Simple card ID - increment count
                    card_counts[item] = card_counts.get(item, 0) + 1
                elif isinstance(item, dict):
                    # Dict with id/code and optional count
                    card_id = item.get("id") or item.get("code")
                    if card_id:
                        count = item.get("count", 1)
                        card_counts[card_id] = count

        return card_counts

    def parse_json_fields(
        self,
        card: dict,
        fields: list[str] | None = None,
    ) -> dict:
        """Parse JSON string fields in a card dict.

        Some card fields (traits, icons, upgrades) are stored as JSON strings
        in ChromaDB and need to be parsed to Python objects.

        Args:
            card: Card dictionary with potential JSON string fields.
            fields: Fields to parse. Defaults to ["traits", "icons", "upgrades"].

        Returns:
            Card dict with JSON fields parsed (modified in place).

        Example:
            >>> card = {"name": "Test", "traits": '["Item", "Weapon"]'}
            >>> loader.parse_json_fields(card)
            {'name': 'Test', 'traits': ['Item', 'Weapon']}
        """
        fields = fields or self.JSON_FIELDS

        for field in fields:
            if field in card and isinstance(card[field], str):
                try:
                    card[field] = json.loads(card[field])
                except (json.JSONDecodeError, TypeError):
                    pass  # Keep as string if not valid JSON

        return card

    def fetch_cards(
        self,
        card_ids: list[str],
        include_counts: dict[str, int] | None = None,
        parse_json: bool = True,
    ) -> list[dict]:
        """Fetch full card data from ChromaDB.

        Args:
            card_ids: List of card IDs to fetch.
            include_counts: Optional dict of card_id -> count to include
                in results as a "count" field.
            parse_json: Whether to parse JSON fields. Defaults to True.

        Returns:
            List of card dicts with parsed JSON fields and optional count field.
            Cards that are not found are silently skipped.

        Example:
            >>> loader = CardDataLoader()
            >>> cards = loader.fetch_cards(["01001", "01002"])
            >>> cards = loader.fetch_cards(["01001"], include_counts={"01001": 2})
        """
        cards = []

        for card_id in card_ids:
            card = self.client.get_card(card_id)
            if card:
                if parse_json:
                    card = self.parse_json_fields(card)

                if include_counts and card_id in include_counts:
                    card["count"] = include_counts[card_id]

                cards.append(card)

        return cards

    def load_card_list(self, cards_data: list | dict) -> list[dict]:
        """Full pipeline: normalize input, fetch cards, parse JSON.

        This combines normalize_card_input, fetch_cards, and parse_json_fields
        into a single convenient method.

        Args:
            cards_data: Card list in any supported format:
                - List of card IDs: ["01001", "01002"]
                - List of dicts: [{"id": "01001", "count": 2}]
                - Dict mapping: {"01001": 2, "01002": 1}

        Returns:
            List of full card dicts with counts and parsed JSON fields.

        Example:
            >>> loader = CardDataLoader()
            >>> cards = loader.load_card_list({"01001": 2, "01002": 1})
            >>> for card in cards:
            ...     print(f"{card['name']}: {card['count']}")
        """
        card_counts = self.normalize_card_input(cards_data)
        unique_ids = list(card_counts.keys())
        return self.fetch_cards(unique_ids, include_counts=card_counts)
