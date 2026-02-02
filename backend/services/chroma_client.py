"""ChromaDB client for data persistence."""

from pathlib import Path

import chromadb

from backend.core.logging_config import get_logger

logger = get_logger(__name__)


class ChromaClient:
    """ChromaDB client wrapper for Arkham Assistant."""

    def __init__(self, persist_path: str = None):
        """Initialize ChromaDB client.

        Args:
            persist_path: Path to persist ChromaDB data. If None, uses project root chroma_data.
        """
        if persist_path is None:
            # Use project root directory
            project_root = Path(__file__).parent.parent.parent
            persist_path = str(project_root / "chroma_data")

        self.client = chromadb.PersistentClient(path=persist_path)
        self.cards = self.client.get_or_create_collection("cards")
        self.characters = self.client.get_or_create_collection("characters")
        self.decks = self.client.get_or_create_collection("decks")

    # Card operations
    def get_card(self, card_id: str) -> dict | None:
        """Fetch single card by ID."""
        try:
            result = self.cards.get(ids=[card_id])
            if result["ids"]:
                card_data = result["metadatas"][0]
                card_data["code"] = result["ids"][0]
                card_data["name"] = result["documents"][0]
                return card_data
            return None
        except Exception:
            logger.error(
                "Failed to fetch card",
                extra={"extra_data": {"card_id": card_id}},
                exc_info=True,
            )
            return None

    def search_cards(
        self,
        query: str | None = None,
        class_filter: str | None = None,
        type_filter: str | None = None,
        owned: bool | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Search cards with metadata filters.

        For text queries, performs case-insensitive fuzzy matching on card names.
        """
        try:
            # Build where filter
            where_filters = {}
            if class_filter:
                where_filters["class_name"] = class_filter
            if type_filter:
                where_filters["type_name"] = type_filter
            if owned is not None:
                where_filters["owned"] = owned

            # Get all cards matching filters (ChromaDB doesn't support text contains)
            result = self.cards.get(
                where=where_filters if where_filters else None,
            )

            # Format results
            cards = []
            for i, card_id in enumerate(result["ids"]):
                card_data = result["metadatas"][i]
                card_data["code"] = card_id
                card_data["name"] = result["documents"][i]
                cards.append(card_data)

            # Apply text search filter in Python if query provided
            if query:
                query_lower = query.lower()
                filtered_cards = []
                for card in cards:
                    card_name = card.get("name", "").lower()
                    card_text = card.get("text", "").lower()
                    card_traits = card.get("traits", "").lower()

                    # Match on name, text, or traits
                    if (
                        query_lower in card_name
                        or query_lower in card_text
                        or query_lower in card_traits
                    ):
                        filtered_cards.append(card)

                # Sort by relevance (name match first, then text match)
                def sort_key(card):
                    name = card.get("name", "").lower()
                    if name.startswith(query_lower):
                        return 0  # Starts with query - highest priority
                    elif query_lower in name:
                        return 1  # Contains in name - second priority
                    else:
                        return 2  # Contains in text/traits - lowest priority

                filtered_cards.sort(key=sort_key)
                cards = filtered_cards[:limit]
            else:
                cards = cards[:limit]

            return cards
        except Exception:
            logger.error("Card search failed", exc_info=True)
            return []

    def add_card(self, card: dict) -> None:
        """Insert or update a card.

        Args:
            card: Card dictionary with required fields (id, name, etc.)
        """
        card_id = card.pop("id")
        name = card.pop("name")

        # Use card name as document for semantic search
        self.cards.upsert(ids=[card_id], documents=[name], metadatas=[card])

    # Deck operations
    def _enrich_deck_cards(self, cards: list[dict]) -> list[dict]:
        """Enrich deck cards with full card data from the cards collection.

        Maps backend field names to frontend expected names:
        - type -> type_name
        - class -> class_name
        - traits (JSON array) -> traits (dot-separated string)
        """
        import json

        enriched = []
        for deck_card in cards:
            code = deck_card.get("code")
            quantity = deck_card.get("quantity", 1)

            # Look up full card data
            full_card = self.get_card(code) if code else None

            if full_card:
                # Build enriched card with frontend-expected field names
                enriched_card = {
                    "code": code,
                    "name": full_card.get("name", deck_card.get("name", "")),
                    "real_name": full_card.get("name", deck_card.get("name", "")),
                    "quantity": quantity,
                    "cost": full_card.get("cost"),
                    "type_name": full_card.get("type", ""),
                    "class_name": full_card.get("class", "Neutral"),
                    "text": full_card.get("text", ""),
                }

                # Parse traits from JSON string to dot-separated string
                traits_raw = full_card.get("traits", "")
                if traits_raw:
                    try:
                        traits_list = json.loads(traits_raw)
                        if isinstance(traits_list, list):
                            enriched_card["traits"] = ". ".join(traits_list) + "."
                        else:
                            enriched_card["traits"] = traits_raw
                    except (json.JSONDecodeError, TypeError):
                        enriched_card["traits"] = traits_raw
                else:
                    enriched_card["traits"] = ""

                enriched.append(enriched_card)
            else:
                # Card not found in collection, use whatever data we have
                enriched.append({
                    "code": code,
                    "name": deck_card.get("name", "Unknown Card"),
                    "real_name": deck_card.get("name", "Unknown Card"),
                    "quantity": quantity,
                    "cost": deck_card.get("cost"),
                    "type_name": deck_card.get("type_name", deck_card.get("type", "")),
                    "class_name": deck_card.get("class_name", deck_card.get("class", "Neutral")),
                    "traits": deck_card.get("traits", ""),
                    "text": deck_card.get("text", ""),
                })

        return enriched

    def get_deck(self, deck_id: str) -> dict | None:
        """Fetch single deck with full metadata and enriched card data."""
        import json

        try:
            result = self.decks.get(ids=[deck_id])
            if result["ids"]:
                deck_data = result["metadatas"][0].copy()
                deck_data["id"] = result["ids"][0]
                deck_data["name"] = result["documents"][0]
                # Parse cards JSON if stored as string
                if "cards" in deck_data and isinstance(deck_data["cards"], str):
                    try:
                        deck_data["cards"] = json.loads(deck_data["cards"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                # Enrich cards with full data from cards collection
                if "cards" in deck_data and isinstance(deck_data["cards"], list):
                    deck_data["cards"] = self._enrich_deck_cards(deck_data["cards"])
                return deck_data
            return None
        except Exception:
            logger.error(
                "Failed to fetch deck",
                extra={"extra_data": {"deck_id": deck_id}},
                exc_info=True,
            )
            return None

    def list_decks(self) -> list[dict]:
        """Return all decks with enriched card data."""
        import json

        try:
            result = self.decks.get()
            decks = []
            for i, deck_id in enumerate(result["ids"]):
                deck_data = result["metadatas"][i].copy()
                deck_data["id"] = deck_id
                deck_data["name"] = result["documents"][i]
                # Parse cards JSON if stored as string
                if "cards" in deck_data and isinstance(deck_data["cards"], str):
                    try:
                        deck_data["cards"] = json.loads(deck_data["cards"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                # Enrich cards with full data from cards collection
                if "cards" in deck_data and isinstance(deck_data["cards"], list):
                    deck_data["cards"] = self._enrich_deck_cards(deck_data["cards"])
                decks.append(deck_data)
            return decks
        except Exception:
            logger.error("Failed to list decks", exc_info=True)
            return []

    def create_deck(self, deck: dict) -> str:
        """Create deck, return new ID."""
        import json
        import uuid

        deck_id = f"deck_{uuid.uuid4().hex[:8]}"

        deck_copy = deck.copy()
        name = deck_copy.pop("name", "Untitled Deck")

        # JSON-serialize cards field for ChromaDB (metadata only supports scalars)
        if "cards" in deck_copy and isinstance(deck_copy["cards"], list):
            deck_copy["cards"] = json.dumps(deck_copy["cards"])

        # Filter out None values - ChromaDB doesn't accept them
        deck_copy = {k: v for k, v in deck_copy.items() if v is not None}

        try:
            self.decks.add(ids=[deck_id], documents=[name], metadatas=[deck_copy])
            return deck_id
        except Exception:
            logger.error("Failed to create deck", exc_info=True)
            raise

    def update_deck(self, deck_id: str, updates: dict) -> None:
        """Update deck fields."""
        import json

        try:
            # Get current deck
            current = self.get_deck(deck_id)
            if not current:
                raise ValueError(f"Deck {deck_id} not found")

            # Merge updates
            name = updates.pop("name", current.get("name", "Untitled Deck"))
            current.update(updates)
            # Remove id field from metadata
            current.pop("id", None)
            current.pop("name", None)

            # JSON-serialize cards field for ChromaDB
            if "cards" in current and isinstance(current["cards"], list):
                current["cards"] = json.dumps(current["cards"])

            # Filter out None values - ChromaDB doesn't accept them
            current = {k: v for k, v in current.items() if v is not None}

            self.decks.update(ids=[deck_id], documents=[name], metadatas=[current])
        except Exception:
            logger.error(
                "Failed to update deck",
                extra={"extra_data": {"deck_id": deck_id}},
                exc_info=True,
            )
            raise

    def delete_deck(self, deck_id: str) -> None:
        """Remove deck."""
        try:
            self.decks.delete(ids=[deck_id])
        except Exception:
            logger.error(
                "Failed to delete deck",
                extra={"extra_data": {"deck_id": deck_id}},
                exc_info=True,
            )
            raise

    # Character operations
    def add_character(self, character: dict) -> None:
        """Insert or update a character.

        Args:
            character: Character dictionary with required fields
        """
        char_id = character.pop("id")
        name = character.pop("name")

        # Use character name as document for semantic search
        self.characters.upsert(ids=[char_id], documents=[name], metadatas=[character])

    def get_character(self, char_id: str) -> dict | None:
        """Fetch investigator definition."""
        try:
            result = self.characters.get(ids=[char_id])
            if result["ids"]:
                char_data = result["metadatas"][0]
                char_data["code"] = result["ids"][0]
                char_data["name"] = result["documents"][0]
                return char_data
            return None
        except Exception:
            logger.error(
                "Failed to fetch character",
                extra={"extra_data": {"char_id": char_id}},
                exc_info=True,
            )
            return None

    def list_characters(self) -> list[dict]:
        """Return all investigators."""
        try:
            result = self.characters.get()
            characters = []
            for i, char_id in enumerate(result["ids"]):
                char_data = result["metadatas"][i]
                char_data["code"] = char_id
                char_data["name"] = result["documents"][i]
                characters.append(char_data)
            return characters
        except Exception:
            logger.error("Failed to list characters", exc_info=True)
            return []
