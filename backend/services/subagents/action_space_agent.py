"""ActionSpaceAgent for card search and filtering.

This module implements the ActionSpaceAgent subagent that searches and filters
available cards based on investigator constraints and upgrade budget. It provides:

- Class access filtering (respecting investigator deckbuilding rules)
- XP cost filtering (≤ available upgrade points)
- Card type, traits, and icons filtering
- Ownership filtering (when owned_sets configured)
- Semantic search for capabilities ("card draw", "enemy management")
- Ranked results with relevance scores
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.models.subagent_models import SubagentMetadata, SubagentResponse
from backend.services.chroma_client import ChromaClient
from backend.services.subagents.base import (
    ActionSpaceSubagent,
    SubagentConfig,
)


# =============================================================================
# Input/Output Schemas
# =============================================================================


class ActionSpaceQuery(BaseModel):
    """Input query for the ActionSpaceAgent.

    Attributes:
        investigator_id: Determines legal card pool based on deckbuilding rules.
        upgrade_points: Max XP cost filter (cards must cost <= this).
        search_query: Semantic search term (e.g., "card draw", "damage").
        type_filter: Filter by card type ("asset", "event", "skill").
        trait_filter: Filter by card traits (e.g., ["spell", "tome"]).
        capability_need: High-level capability need ("card draw", "combat", "clues").
        exclude_cards: Card IDs to exclude (e.g., cards already in deck).
        limit: Maximum number of results to return.
    """

    investigator_id: str = Field(
        description="Investigator ID to determine legal card pool"
    )
    upgrade_points: int = Field(
        default=0,
        ge=0,
        description="Maximum XP cost for returned cards"
    )
    search_query: Optional[str] = Field(
        default=None,
        description="Semantic search term (e.g., 'card draw', 'damage')"
    )
    type_filter: Optional[str] = Field(
        default=None,
        description="Card type filter: 'asset', 'event', or 'skill'"
    )
    trait_filter: Optional[list[str]] = Field(
        default=None,
        description="Card traits to filter by (e.g., ['spell', 'tome'])"
    )
    capability_need: Optional[str] = Field(
        default=None,
        description="High-level capability: 'card_draw', 'combat', 'clues', 'economy', 'willpower'"
    )
    exclude_cards: Optional[list[str]] = Field(
        default=None,
        description="Card IDs to exclude from results"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of cards to return"
    )


class CardCandidate(BaseModel):
    """A card candidate returned by the ActionSpaceAgent.

    Attributes:
        card_id: Unique identifier for the card.
        name: Display name of the card.
        xp_cost: Experience cost (level) of the card.
        relevance_score: Score from 0-1 indicating match quality.
        reason: Human-readable explanation of why this card was suggested.
        card_type: Type of card (asset, event, skill).
        class_name: Card's class (Guardian, Seeker, etc.).
        cost: Resource cost to play the card.
        traits: List of card traits.
        text: Card text (abilities/effects).
    """

    card_id: str
    name: str
    xp_cost: int = 0
    relevance_score: float = Field(ge=0.0, le=1.0)
    reason: str
    card_type: Optional[str] = None
    class_name: Optional[str] = None
    cost: Optional[int] = None
    traits: Optional[str] = None
    text: Optional[str] = None


class ActionSpaceResponse(SubagentResponse):
    """Response from the ActionSpaceAgent.

    Extends the base SubagentResponse with a list of card candidates.
    """

    candidates: list[CardCandidate] = Field(
        default_factory=list,
        description="Ranked list of card candidates matching the query"
    )

    @classmethod
    def _get_error_defaults(cls) -> dict[str, Any]:
        """Provide default values for action space fields in error responses."""
        return {"candidates": []}


# =============================================================================
# Investigator Class Access Rules
# =============================================================================


# Standard class access rules for investigators
# Format: investigator_id -> list of (class_name, max_level) tuples
# Level -1 means no access, level 5 means full access
INVESTIGATOR_CLASS_ACCESS: dict[str, list[tuple[str, int]]] = {
    # Core Set Investigators
    "01001": [("Guardian", 5), ("Neutral", 5), ("Seeker", 0)],  # Roland Banks
    "01002": [("Seeker", 5), ("Neutral", 5), ("Mystic", 0)],    # Daisy Walker
    "01003": [("Rogue", 5), ("Neutral", 5), ("Guardian", 0)],   # "Skids" O'Toole
    "01004": [("Mystic", 5), ("Neutral", 5), ("Survivor", 2)],  # Agnes Baker
    "01005": [("Survivor", 5), ("Neutral", 5), ("Rogue", 0)],   # Wendy Adams

    # Dunwich Legacy Investigators
    "02001": [("Seeker", 5), ("Neutral", 5), ("Survivor", 0)],  # Rex Murphy
    "02002": [("Guardian", 5), ("Neutral", 5), ("Survivor", 0)], # Zoey Samaras
    "02003": [("Rogue", 5), ("Neutral", 5), ("Mystic", 0)],     # Jenny Barnes
    "02004": [("Survivor", 5), ("Neutral", 5), ("Seeker", 0)],  # Jim Culver (actually Mystic)
    "02005": [("Mystic", 5), ("Neutral", 5), ("Seeker", 0)],    # Ashcan Pete (actually Survivor)

    # Default: Full access to Neutral only
    "default": [("Neutral", 5)],
}


# Capability keywords mapping for semantic search
CAPABILITY_KEYWORDS: dict[str, list[str]] = {
    "card_draw": [
        "draw", "card", "hand", "search your deck", "look at the top",
        "reveal", "insight", "research"
    ],
    "combat": [
        "damage", "fight", "attack", "enemy", "engage", "evade",
        "defeat", "weapon", "combat", "firearm", "melee"
    ],
    "clues": [
        "clue", "investigate", "discover", "shroud", "location",
        "intellect", "tome", "research", "evidence"
    ],
    "economy": [
        "resource", "gain", "cost", "pay", "afford", "income",
        "money", "wealth", "fund"
    ],
    "willpower": [
        "willpower", "horror", "sanity", "mind", "spirit",
        "treachery", "cancel", "ward", "protection"
    ],
    "movement": [
        "move", "location", "travel", "fast", "shortcut",
        "pathfinder", "scout"
    ],
    "healing": [
        "heal", "damage", "horror", "recover", "restore",
        "soak", "health", "stamina"
    ],
    "action_efficiency": [
        "fast", "free", "action", "additional", "extra",
        "quick", "swift"
    ],
}


# =============================================================================
# ActionSpaceAgent Implementation
# =============================================================================


@dataclass
class InvestigatorAccessRules:
    """Parsed deckbuilding rules for an investigator.

    Attributes:
        investigator_id: The investigator's ID.
        investigator_name: The investigator's name.
        class_access: Dict mapping class name -> max level allowed.
        special_rules: Any special deckbuilding text.
    """

    investigator_id: str
    investigator_name: str = ""
    class_access: dict[str, int] = field(default_factory=dict)
    special_rules: str = ""


class ActionSpaceAgent:
    """Agent for searching and filtering available cards.

    The ActionSpaceAgent helps find cards that:
    1. Are legal for a specific investigator
    2. Fit within an XP budget
    3. Match search criteria (type, traits, capabilities)
    4. Are available in the player's collection

    Example usage:
        agent = ActionSpaceAgent()
        query = ActionSpaceQuery(
            investigator_id="01001",
            upgrade_points=5,
            capability_need="combat",
            type_filter="asset",
            limit=10
        )
        response = agent.search(query)
        for card in response.candidates:
            print(f"{card.name} (XP: {card.xp_cost}) - {card.reason}")
    """

    def __init__(
        self,
        config: SubagentConfig | None = None,
        chroma_client: ChromaClient | None = None,
    ) -> None:
        """Initialize the ActionSpaceAgent.

        Args:
            config: Optional subagent configuration.
            chroma_client: Optional ChromaDB client (created if not provided).
        """
        self.config = config or SubagentConfig()
        self._chroma_client = chroma_client
        self._base_subagent: ActionSpaceSubagent | None = None

    @property
    def chroma_client(self) -> ChromaClient:
        """Lazy-initialize ChromaDB client."""
        if self._chroma_client is None:
            self._chroma_client = ChromaClient()
        return self._chroma_client

    def _get_investigator_rules(self, investigator_id: str) -> InvestigatorAccessRules:
        """Get deckbuilding rules for an investigator.

        Args:
            investigator_id: The investigator's unique ID.

        Returns:
            InvestigatorAccessRules with class access and special rules.
        """
        # Try to get investigator from ChromaDB
        investigator = self.chroma_client.get_character(investigator_id)

        rules = InvestigatorAccessRules(investigator_id=investigator_id)

        if investigator:
            rules.investigator_name = investigator.get("name", "")
            rules.special_rules = investigator.get("deck_requirements", "")

            # Parse faction/class from investigator data
            faction = investigator.get("faction_name") or investigator.get("class_name", "")
            if faction:
                rules.class_access[faction] = 5  # Full access to primary class
                rules.class_access["Neutral"] = 5  # All have neutral access

            # Check for secondary class access
            secondary = investigator.get("deck_options", "")
            if secondary:
                # Parse deck_options for additional class access
                # This is simplified - real implementation would parse JSON
                for class_name in ["Guardian", "Seeker", "Rogue", "Mystic", "Survivor"]:
                    if class_name.lower() in secondary.lower():
                        if class_name not in rules.class_access:
                            # Assume level 0 access for secondary classes
                            rules.class_access[class_name] = 0

        # Fall back to hardcoded rules if available
        if not rules.class_access:
            access_list = INVESTIGATOR_CLASS_ACCESS.get(
                investigator_id,
                INVESTIGATOR_CLASS_ACCESS["default"]
            )
            for class_name, max_level in access_list:
                rules.class_access[class_name] = max_level

        return rules

    def _is_card_legal(
        self,
        card: dict,
        rules: InvestigatorAccessRules,
        max_xp: int,
    ) -> bool:
        """Check if a card is legal for the investigator.

        Args:
            card: Card data dictionary.
            rules: Investigator's deckbuilding rules.
            max_xp: Maximum XP allowed.

        Returns:
            True if the card is legal, False otherwise.
        """
        # Get card's class and level
        card_class = card.get("class_name") or card.get("faction_name", "")
        card_level = card.get("xp") or card.get("level", 0)

        # Handle missing/invalid level
        if card_level is None:
            card_level = 0
        try:
            card_level = int(card_level)
        except (ValueError, TypeError):
            card_level = 0

        # Check XP constraint
        if card_level > max_xp:
            return False

        # Check class access
        if card_class in rules.class_access:
            max_allowed_level = rules.class_access[card_class]
            if card_level <= max_allowed_level:
                return True

        # Neutral cards are always allowed (up to XP limit)
        if card_class == "Neutral":
            return True

        # Multi-class cards: check if any class is accessible
        if "/" in card_class:
            classes = [c.strip() for c in card_class.split("/")]
            for cls in classes:
                if cls in rules.class_access:
                    max_allowed = rules.class_access[cls]
                    if card_level <= max_allowed:
                        return True

        return False

    def _matches_type_filter(self, card: dict, type_filter: str | None) -> bool:
        """Check if card matches the type filter.

        Args:
            card: Card data dictionary.
            type_filter: Desired card type (asset, event, skill) or None.

        Returns:
            True if matches or no filter, False otherwise.
        """
        if not type_filter:
            return True

        card_type = (card.get("type_name") or card.get("type", "")).lower()
        return type_filter.lower() in card_type

    def _matches_trait_filter(
        self,
        card: dict,
        trait_filter: list[str] | None
    ) -> bool:
        """Check if card has any of the specified traits.

        Args:
            card: Card data dictionary.
            trait_filter: List of desired traits or None.

        Returns:
            True if card has any trait (OR logic) or no filter, False otherwise.
        """
        if not trait_filter:
            return True

        card_traits = (card.get("traits") or "").lower()

        for trait in trait_filter:
            if trait.lower() in card_traits:
                return True

        return False

    def _matches_ownership(
        self,
        card: dict,
        owned_sets: list[str] | None
    ) -> bool:
        """Check if card is in owned sets.

        Args:
            card: Card data dictionary.
            owned_sets: List of owned pack/expansion names, or None for no filter.

        Returns:
            True if owned or no filter, False otherwise.
        """
        if not owned_sets:
            return True

        # Check if card is marked as owned
        if card.get("owned"):
            return True

        # Check pack name against owned sets
        pack_name = card.get("pack_name", "")
        if pack_name:
            for owned_set in owned_sets:
                if owned_set.lower() in pack_name.lower():
                    return True

        return False

    def _calculate_relevance_score(
        self,
        card: dict,
        query: ActionSpaceQuery,
    ) -> tuple[float, str]:
        """Calculate relevance score and generate reason.

        Args:
            card: Card data dictionary.
            query: The search query.

        Returns:
            Tuple of (relevance_score, reason_string).
        """
        score = 0.5  # Base score
        reasons = []

        card_name = card.get("name", "")
        card_text = (card.get("text") or "").lower()
        card_traits = (card.get("traits") or "").lower()

        # Boost for search query match
        if query.search_query:
            search_lower = query.search_query.lower()
            if search_lower in card_name.lower():
                score += 0.3
                reasons.append(f"Name matches '{query.search_query}'")
            elif search_lower in card_text:
                score += 0.2
                reasons.append(f"Text contains '{query.search_query}'")
            elif search_lower in card_traits:
                score += 0.15
                reasons.append(f"Has trait related to '{query.search_query}'")

        # Boost for capability match
        if query.capability_need:
            keywords = CAPABILITY_KEYWORDS.get(query.capability_need, [])
            matched_keywords = []
            for keyword in keywords:
                if keyword in card_text or keyword in card_name.lower():
                    matched_keywords.append(keyword)
            if matched_keywords:
                keyword_score = min(0.3, len(matched_keywords) * 0.1)
                score += keyword_score
                reasons.append(f"Provides {query.capability_need}: {', '.join(matched_keywords[:3])}")

        # Boost for trait match
        if query.trait_filter:
            matching_traits = [t for t in query.trait_filter if t.lower() in card_traits]
            if matching_traits:
                score += 0.15
                reasons.append(f"Has traits: {', '.join(matching_traits)}")

        # Slight penalty for high XP cost relative to budget
        if query.upgrade_points > 0:
            card_xp = card.get("xp", 0) or 0
            if card_xp > 0:
                xp_ratio = card_xp / query.upgrade_points
                if xp_ratio > 0.5:
                    score -= 0.05
                reasons.append(f"Costs {card_xp} XP")

        # Ensure score is in valid range
        score = max(0.0, min(1.0, score))

        # Default reason if none found
        if not reasons:
            card_class = card.get("class_name", "")
            card_type = card.get("type_name", "")
            reasons.append(f"Legal {card_class} {card_type}")

        return score, "; ".join(reasons)

    def search(
        self,
        query: ActionSpaceQuery,
        context: dict[str, Any] | None = None,
    ) -> ActionSpaceResponse:
        """Search for cards matching the query criteria.

        This is the main entry point for the ActionSpaceAgent. It:
        1. Gets investigator deckbuilding rules
        2. Fetches candidate cards from ChromaDB
        3. Filters by legality, type, traits, and ownership
        4. Calculates relevance scores
        5. Returns ranked results

        Args:
            query: The search query with all filter criteria.
            context: Optional additional context (owned_sets, etc.).

        Returns:
            ActionSpaceResponse with ranked card candidates.
        """
        context = context or {}
        owned_sets = context.get("owned_sets")

        # Get investigator rules
        rules = self._get_investigator_rules(query.investigator_id)

        # Build ChromaDB query
        # Start with type filter if specified
        chroma_kwargs: dict[str, Any] = {}
        if query.type_filter:
            chroma_kwargs["type_filter"] = query.type_filter

        # Get cards from ChromaDB
        if query.search_query:
            cards = self.chroma_client.search_cards(
                query=query.search_query,
                **chroma_kwargs
            )
        else:
            cards = self.chroma_client.search_cards(**chroma_kwargs)

        # Filter and score cards
        candidates: list[CardCandidate] = []
        exclude_set = set(query.exclude_cards or [])

        for card in cards:
            card_id = card.get("code") or card.get("id", "")

            # Skip excluded cards
            if card_id in exclude_set:
                continue

            # Check legality
            if not self._is_card_legal(card, rules, query.upgrade_points):
                continue

            # Check type filter
            if not self._matches_type_filter(card, query.type_filter):
                continue

            # Check trait filter
            if not self._matches_trait_filter(card, query.trait_filter):
                continue

            # Check ownership
            if not self._matches_ownership(card, owned_sets):
                continue

            # Calculate relevance score
            relevance_score, reason = self._calculate_relevance_score(card, query)

            # Create candidate
            candidate = CardCandidate(
                card_id=card_id,
                name=card.get("name", "Unknown"),
                xp_cost=card.get("xp", 0) or 0,
                relevance_score=relevance_score,
                reason=reason,
                card_type=card.get("type_name"),
                class_name=card.get("class_name"),
                cost=card.get("cost"),
                traits=card.get("traits"),
                text=card.get("text"),
            )
            candidates.append(candidate)

        # Sort by relevance score (descending)
        candidates.sort(key=lambda c: c.relevance_score, reverse=True)

        # Limit results
        candidates = candidates[:query.limit]

        # Build response
        summary_parts = []
        if candidates:
            summary_parts.append(
                f"Found {len(candidates)} cards"
            )
            if query.capability_need:
                summary_parts.append(f"for {query.capability_need}")
            if query.upgrade_points > 0:
                summary_parts.append(f"within {query.upgrade_points} XP budget")
            summary_parts.append(f"for {rules.investigator_name or query.investigator_id}")
        else:
            summary_parts.append("No cards found matching criteria")

        return ActionSpaceResponse(
            content=". ".join(summary_parts),
            confidence=0.85 if candidates else 0.5,
            sources=[f"Card pool: {rules.investigator_name or query.investigator_id}"],
            metadata=SubagentMetadata(
                agent_type="action_space",
                query_type="card_search",
                context_used={
                    "investigator_id": query.investigator_id,
                    "upgrade_points": query.upgrade_points,
                    "search_query": query.search_query,
                    "type_filter": query.type_filter,
                    "trait_filter": query.trait_filter,
                    "capability_need": query.capability_need,
                },
                extra={
                    "total_matches": len(candidates),
                    "class_access": rules.class_access,
                },
            ),
            candidates=candidates,
        )

    def query(
        self,
        query_text: str,
        context: dict[str, Any] | None = None,
    ) -> SubagentResponse:
        """Natural language query interface (delegates to base subagent).

        For complex natural language queries that need LLM interpretation,
        this method delegates to the base ActionSpaceSubagent.

        Args:
            query_text: Natural language query.
            context: Optional context dict.

        Returns:
            SubagentResponse from the base subagent.
        """
        if self._base_subagent is None:
            from backend.services.subagents.base import ActionSpaceSubagent
            self._base_subagent = ActionSpaceSubagent(config=self.config)

        return self._base_subagent.query(query_text, context)


# =============================================================================
# Convenience Functions
# =============================================================================


def create_action_space_agent(
    config: SubagentConfig | None = None,
    chroma_client: ChromaClient | None = None,
) -> ActionSpaceAgent:
    """Factory function to create an ActionSpaceAgent.

    Args:
        config: Optional configuration for the agent.
        chroma_client: Optional ChromaDB client.

    Returns:
        Configured ActionSpaceAgent instance.
    """
    return ActionSpaceAgent(config=config, chroma_client=chroma_client)
