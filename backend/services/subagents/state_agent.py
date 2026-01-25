"""StateAgent for deck composition analysis.

This module provides the StateAgent subagent which analyzes current deck
composition and identifies strengths, weaknesses, and gaps. It provides
detailed quantitative analysis of deck state.
"""

import json
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.models.subagent_models import SubagentMetadata, SubagentResponse
from backend.services.agent_tools import get_deck
from backend.services.chroma_client import ChromaClient
from backend.services.subagents.utils import CardDataLoader


# =============================================================================
# Input/Output Schemas
# =============================================================================


class StateQuery(BaseModel):
    """Input schema for StateAgent queries.

    Attributes:
        deck_id: Existing deck ID to analyze (if using stored deck)
        card_list: Raw list of card IDs or card dicts (alternative to deck_id)
        investigator_id: Investigator code for context on class access
        upgrade_points: Available XP for upgrades
    """

    deck_id: Optional[str] = Field(
        default=None,
        description="Existing deck ID to analyze"
    )
    card_list: Optional[list[str | dict]] = Field(
        default=None,
        description="Raw card list as IDs or dicts with id/count"
    )
    investigator_id: str = Field(
        description="Investigator code for class access context"
    )
    upgrade_points: int = Field(
        default=0,
        ge=0,
        description="Available XP for upgrades"
    )


class SynergyInfo(BaseModel):
    """Information about a detected synergy."""

    cards: list[str] = Field(description="Card names involved in the synergy")
    effect: str = Field(description="Description of the synergy effect")
    strength: str = Field(
        default="moderate",
        description="Synergy strength: weak, moderate, strong"
    )


class StateResponse(SubagentResponse):
    """Structured response from StateAgent analysis.

    Extends SubagentResponse with detailed deck analysis fields.

    Attributes:
        curve_analysis: Resource curve distribution (cost -> count)
        type_distribution: Card type counts (asset, event, skill, etc.)
        class_distribution: Class counts (guardian, seeker, etc.)
        identified_gaps: List of missing capabilities
        strengths: List of deck strengths
        synergies: Detected card synergies
        upgrade_priority: Cards that should be upgraded first
        total_cards: Total card count in deck
        investigator_name: Name of the investigator
    """

    curve_analysis: dict[str, int] = Field(
        default_factory=dict,
        description="Resource curve: cost -> count"
    )
    type_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Card types: type -> count"
    )
    class_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Classes: class -> count"
    )
    identified_gaps: list[str] = Field(
        default_factory=list,
        description="Missing capabilities"
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="Deck strengths"
    )
    synergies: list[SynergyInfo] = Field(
        default_factory=list,
        description="Detected synergies"
    )
    upgrade_priority: list[str] = Field(
        default_factory=list,
        description="Cards to upgrade first"
    )
    total_cards: int = Field(
        default=0,
        description="Total card count"
    )
    investigator_name: Optional[str] = Field(
        default=None,
        description="Investigator name"
    )

    @classmethod
    def _get_error_defaults(cls) -> dict[str, Any]:
        """Provide default values for state-specific fields in error responses."""
        return {
            "curve_analysis": {},
            "type_distribution": {},
            "class_distribution": {},
            "identified_gaps": [],
            "strengths": [],
            "synergies": [],
            "upgrade_priority": [],
            "total_cards": 0,
            "investigator_name": None,
        }


# =============================================================================
# Ideal Deck Templates for Gap Analysis
# =============================================================================

# Minimum capabilities an "ideal" deck should have
IDEAL_CAPABILITIES = {
    "card_draw": {
        "keywords": ["draw", "search your deck"],
        "min_count": 4,
        "description": "card draw/deck searching"
    },
    "resources": {
        "keywords": ["gain.*resource", "resource"],
        "min_count": 4,
        "description": "resource generation"
    },
    "combat": {
        "keywords": ["fight", "damage", "attack"],
        "min_count": 6,
        "description": "combat capability"
    },
    "clues": {
        "keywords": ["investigate", "clue", "discover"],
        "min_count": 6,
        "description": "clue gathering"
    },
    "willpower_icons": {
        "icon_type": "willpower",
        "min_count": 6,
        "description": "willpower commit icons"
    },
    "treachery_protection": {
        "keywords": ["cancel", "avoid", "ignore.*treachery"],
        "min_count": 2,
        "description": "treachery protection"
    },
    "healing": {
        "keywords": ["heal", "horror", "damage from"],
        "min_count": 2,
        "description": "healing/horror management"
    },
}

# Common synergy patterns to detect
SYNERGY_PATTERNS = [
    {
        "name": "Skill Commit Engine",
        "traits": ["practiced"],
        "keywords": ["commit.*skill", "when.*commit"],
        "effect": "Cards that synergize with skill commits",
    },
    {
        "name": "Resource Engine",
        "keywords": ["gain.*resource", "reduce.*cost"],
        "effect": "Resource generation and cost reduction synergy",
    },
    {
        "name": "Card Draw Engine",
        "keywords": ["draw.*card", "search.*deck"],
        "effect": "Card draw and deck cycling synergy",
    },
    {
        "name": "Fight Action Synergy",
        "keywords": ["fight action", "attack", r"\+.*combat", "damage"],
        "effect": "Combat boosting and fight action synergy",
    },
    {
        "name": "Investigate Synergy",
        "keywords": ["investigate action", r"\+.*intellect", "discover.*clue"],
        "effect": "Investigation boosting and clue synergy",
    },
    {
        "name": "Event Recursion",
        "type": "event",
        "keywords": ["play.*event", "return.*event", "again"],
        "effect": "Event replay and recursion synergy",
    },
    {
        "name": "Asset Synergy",
        "type": "asset",
        "keywords": ["asset.*play", "each.*asset", "control.*asset"],
        "effect": "Asset deployment and board presence synergy",
    },
]

# Upgrade priority keywords (cards with these should be upgraded)
UPGRADE_PRIORITY_KEYWORDS = [
    "exceptional",  # Exceptional cards are high impact
    "permanent",    # Permanents are always good upgrades
    "seal",         # Seal cards are powerful
    "fast",         # Fast cards are efficient
]


# =============================================================================
# StateAgent Implementation
# =============================================================================


class StateAgent:
    """Agent for analyzing deck composition and state.

    The StateAgent provides detailed analysis of deck composition including:
    - Resource curve analysis
    - Card type and class distribution
    - Gap identification compared to ideal capabilities
    - Synergy detection within the deck
    - Upgrade priority recommendations

    This agent can work with either a stored deck (by ID) or a raw card list.
    """

    def __init__(self, chroma_client: Optional[ChromaClient] = None):
        """Initialize the StateAgent.

        Args:
            chroma_client: Optional ChromaDB client. If None, creates one lazily.
        """
        self._client: Optional[ChromaClient] = chroma_client
        self._card_loader: Optional[CardDataLoader] = None

    @property
    def client(self) -> ChromaClient:
        """Lazy-load ChromaDB client."""
        if self._client is None:
            self._client = ChromaClient()
        return self._client

    @property
    def card_loader(self) -> CardDataLoader:
        """Lazy-load CardDataLoader."""
        if self._card_loader is None:
            self._card_loader = CardDataLoader(self.client)
        return self._card_loader

    def analyze(self, query: StateQuery) -> StateResponse:
        """Perform comprehensive deck analysis.

        Args:
            query: StateQuery with deck_id or card_list and investigator context

        Returns:
            StateResponse with full analysis results

        Raises:
            ValueError: If neither deck_id nor card_list is provided
        """
        # Get card data from deck or card list
        cards, deck_name, investigator_name = self._load_cards(query)

        if not cards:
            return StateResponse(
                content="Empty deck - no cards to analyze",
                confidence=0.0,
                sources=[],
                metadata=SubagentMetadata(
                    agent_type="state",
                    query_type="empty_deck",
                ),
                investigator_name=investigator_name,
                identified_gaps=["Empty deck - no cards to analyze"],
            )

        # Perform analyses
        curve = self._analyze_curve(cards)
        types = self._analyze_types(cards)
        classes = self._analyze_classes(cards)
        gaps = self._identify_gaps(cards)
        strengths = self._identify_strengths(cards)
        synergies = self._detect_synergies(cards)
        upgrades = self._prioritize_upgrades(cards, query.upgrade_points)
        total = self._count_cards(cards)

        # Build summary content
        content_parts = [f"Deck analysis for {investigator_name or 'Unknown'}:"]
        content_parts.append(f"- {total} total cards")
        if gaps:
            content_parts.append(f"- {len(gaps)} identified gaps")
        if strengths:
            content_parts.append(f"- {len(strengths)} strengths")
        if synergies:
            content_parts.append(f"- {len(synergies)} synergies detected")

        # Build sources
        sources = []
        if deck_name:
            sources.append(f"Deck: {deck_name}")
        if investigator_name:
            sources.append(f"Investigator: {investigator_name}")

        # Build response with all analyses
        response = StateResponse(
            content="\n".join(content_parts),
            confidence=0.9 if cards else 0.0,
            sources=sources,
            metadata=SubagentMetadata(
                agent_type="state",
                query_type="deck_analysis",
                context_used={
                    "deck_id": query.deck_id,
                    "investigator_id": query.investigator_id,
                    "upgrade_points": query.upgrade_points,
                },
            ),
            curve_analysis=curve,
            type_distribution=types,
            class_distribution=classes,
            identified_gaps=gaps,
            strengths=strengths,
            synergies=synergies,
            upgrade_priority=upgrades,
            total_cards=total,
            investigator_name=investigator_name,
        )

        return response

    def _load_cards(
        self, query: StateQuery
    ) -> tuple[list[dict], Optional[str], Optional[str]]:
        """Load card data from deck ID or card list.

        Args:
            query: StateQuery with deck_id or card_list

        Returns:
            Tuple of (cards list, deck_name, investigator_name)

        Raises:
            ValueError: If neither deck_id nor card_list is provided
        """
        deck_name = None
        investigator_name = None

        if query.deck_id:
            # Load from stored deck
            try:
                deck = get_deck(query.deck_id)
                deck_name = deck.get("name")
                investigator_name = deck.get("investigator_name")

                # Parse cards from deck
                cards_data = deck.get("cards", [])
                if isinstance(cards_data, str):
                    cards_data = json.loads(cards_data)

                cards = self._expand_card_list(cards_data)
            except Exception:
                cards = []

        elif query.card_list:
            # Use raw card list
            cards = self._expand_card_list(query.card_list)

            # Try to get investigator name
            if query.investigator_id:
                investigator = self.client.get_character(query.investigator_id)
                if investigator:
                    investigator_name = investigator.get("name")
        else:
            raise ValueError("Either deck_id or card_list must be provided")

        return cards, deck_name, investigator_name

    def _expand_card_list(self, cards_data: list | dict) -> list[dict]:
        """Expand card list to full card data with counts.

        Handles multiple input formats:
        - List of card IDs: ["01001", "01002"]
        - List of dicts: [{"id": "01001", "count": 2}]
        - Dict mapping: {"01001": 2, "01002": 1}

        Args:
            cards_data: Card list in any supported format

        Returns:
            List of card dicts with full data and "count" field
        """
        return self.card_loader.load_card_list(cards_data)

    def _count_cards(self, cards: list[dict]) -> int:
        """Count total cards considering quantities."""
        return sum(card.get("count", 1) for card in cards)

    def _analyze_curve(self, cards: list[dict]) -> dict[str, int]:
        """Analyze resource curve (cost distribution).

        Args:
            cards: List of card dicts with cost and count fields

        Returns:
            Dict mapping cost (as string) to count
        """
        curve: dict[str, int] = {}

        for card in cards:
            cost = card.get("cost")
            if cost is None:
                continue

            cost_key = str(cost)
            count = card.get("count", 1)
            curve[cost_key] = curve.get(cost_key, 0) + count

        return curve

    def _analyze_types(self, cards: list[dict]) -> dict[str, int]:
        """Analyze card type distribution.

        Args:
            cards: List of card dicts

        Returns:
            Dict mapping type name to count
        """
        types: dict[str, int] = {}

        for card in cards:
            card_type = card.get("type_name") or card.get("type", "Unknown")
            count = card.get("count", 1)
            types[card_type] = types.get(card_type, 0) + count

        return types

    def _analyze_classes(self, cards: list[dict]) -> dict[str, int]:
        """Analyze class distribution.

        Args:
            cards: List of card dicts

        Returns:
            Dict mapping class name to count
        """
        classes: dict[str, int] = {}

        for card in cards:
            card_class = card.get("class_name") or card.get("class", "Unknown")
            count = card.get("count", 1)
            classes[card_class] = classes.get(card_class, 0) + count

        return classes

    def _identify_gaps(self, cards: list[dict]) -> list[str]:
        """Identify missing capabilities compared to ideal deck.

        Args:
            cards: List of card dicts

        Returns:
            List of identified gaps
        """
        gaps = []

        for capability, config in IDEAL_CAPABILITIES.items():
            count = 0

            if "keywords" in config:
                # Count cards matching keywords
                for card in cards:
                    card_text = (card.get("text") or "").lower()
                    card_traits = str(card.get("traits") or "").lower()

                    for keyword in config["keywords"]:
                        import re
                        if re.search(keyword, card_text) or re.search(keyword, card_traits):
                            count += card.get("count", 1)
                            break

            elif "icon_type" in config:
                # Count cards with specific icon
                icon_type = config["icon_type"]
                for card in cards:
                    icons = card.get("icons", {})
                    if isinstance(icons, str):
                        try:
                            icons = json.loads(icons)
                        except (json.JSONDecodeError, TypeError):
                            icons = {}

                    if icons.get(icon_type, 0) > 0:
                        count += card.get("count", 1)

            # Check if below minimum
            min_count = config["min_count"]
            if count < min_count:
                gaps.append(
                    f"Insufficient {config['description']} "
                    f"({count}/{min_count} cards)"
                )

        return gaps

    def _identify_strengths(self, cards: list[dict]) -> list[str]:
        """Identify deck strengths based on composition.

        Args:
            cards: List of card dicts

        Returns:
            List of identified strengths
        """
        strengths = []
        total = self._count_cards(cards)

        if total == 0:
            return strengths

        # Analyze type distribution for strengths
        types = self._analyze_types(cards)

        asset_count = types.get("Asset", 0)
        event_count = types.get("Event", 0)
        skill_count = types.get("Skill", 0)

        if asset_count > total * 0.5:
            strengths.append("Strong board presence (high asset count)")

        if event_count > total * 0.4:
            strengths.append("High flexibility (many events)")

        if skill_count > total * 0.25:
            strengths.append("Good test reliability (many skills)")

        # Check for capabilities above threshold
        for capability, config in IDEAL_CAPABILITIES.items():
            count = 0

            if "keywords" in config:
                for card in cards:
                    card_text = (card.get("text") or "").lower()
                    for keyword in config["keywords"]:
                        import re
                        if re.search(keyword, card_text):
                            count += card.get("count", 1)
                            break

            # If significantly above minimum, it's a strength
            min_count = config["min_count"]
            if count >= min_count * 1.5:
                strengths.append(f"Strong {config['description']}")

        # Check curve health
        curve = self._analyze_curve(cards)
        low_cost = sum(curve.get(str(c), 0) for c in range(3))

        if low_cost > total * 0.6:
            strengths.append("Efficient resource curve (many low-cost cards)")

        return strengths

    def _detect_synergies(self, cards: list[dict]) -> list[SynergyInfo]:
        """Detect card synergies within the deck.

        Args:
            cards: List of card dicts

        Returns:
            List of SynergyInfo objects
        """
        synergies = []

        for pattern in SYNERGY_PATTERNS:
            matching_cards = []

            for card in cards:
                card_text = (card.get("text") or "").lower()
                card_type = (card.get("type_name") or card.get("type", "")).lower()
                card_traits = str(card.get("traits") or "").lower()

                # Check type filter
                if "type" in pattern and pattern["type"] != card_type:
                    continue

                # Check trait filter
                trait_match = False
                if "traits" in pattern:
                    for trait in pattern["traits"]:
                        if trait.lower() in card_traits:
                            trait_match = True
                            break

                # Check keyword filter
                keyword_match = False
                if "keywords" in pattern:
                    import re
                    for keyword in pattern["keywords"]:
                        if re.search(keyword, card_text):
                            keyword_match = True
                            break

                # Add if matches any criteria
                if trait_match or keyword_match:
                    card_name = card.get("name", card.get("code", "Unknown"))
                    if card_name not in matching_cards:
                        matching_cards.append(card_name)

            # Only report synergy if multiple cards match
            if len(matching_cards) >= 2:
                strength = "weak"
                if len(matching_cards) >= 4:
                    strength = "strong"
                elif len(matching_cards) >= 3:
                    strength = "moderate"

                synergies.append(SynergyInfo(
                    cards=matching_cards[:5],  # Limit to 5 cards
                    effect=pattern["effect"],
                    strength=strength,
                ))

        return synergies

    def _prioritize_upgrades(
        self, cards: list[dict], available_xp: int
    ) -> list[str]:
        """Identify cards that should be upgraded first.

        Args:
            cards: List of card dicts
            available_xp: Available XP for upgrades

        Returns:
            List of card names to prioritize for upgrades
        """
        upgrade_candidates = []

        for card in cards:
            card_name = card.get("name", card.get("code", "Unknown"))
            card_text = (card.get("text") or "").lower()
            xp_cost = card.get("xp_cost", 0) or 0

            # Skip cards that already have XP (already upgraded)
            # or have XP cost higher than available
            if xp_cost > 0 or xp_cost > available_xp:
                continue

            # Check for upgrade priority indicators
            priority_score = 0

            for keyword in UPGRADE_PRIORITY_KEYWORDS:
                if keyword in card_text:
                    priority_score += 2

            # Cards in key capabilities are higher priority
            for capability, config in IDEAL_CAPABILITIES.items():
                if "keywords" in config:
                    import re
                    for keyword in config["keywords"]:
                        if re.search(keyword, card_text):
                            priority_score += 1
                            break

            if priority_score > 0:
                upgrade_candidates.append((card_name, priority_score))

        # Sort by priority score and return top candidates
        upgrade_candidates.sort(key=lambda x: x[1], reverse=True)
        return [name for name, _ in upgrade_candidates[:10]]


# =============================================================================
# Factory Function
# =============================================================================


def create_state_agent() -> StateAgent:
    """Factory function to create a StateAgent.

    Returns:
        Configured StateAgent instance
    """
    return StateAgent()
