# Database & CRUD Services Design — Arkham Assistant

## Overview

ChromaDB-based storage for cards, characters, and decks. Provides CRUD API endpoints for frontend and backend services.

**Key features:**
- Local vector database (no cloud dependencies)
- Metadata-rich storage for filtering and search
- Optional text embeddings for semantic search

---

## ChromaDB Schema

### Collection 1: `cards`

**Purpose:** Store all Arkham Horror LCG cards.

| Field           | Type              | Notes                                        |
| --------------- | ----------------- | -------------------------------------------- |
| `id`            | String (CardID)   | Primary key (e.g., "01001")                  |
| `name`          | String            | Card name                                    |
| `class`         | String            | Guardian, Seeker, Rogue, Mystic, Survivor, Neutral |
| `cost`          | Int               | Resource cost (0-5, or X)                    |
| `type`          | String            | Asset, Event, Skill, Treachery, etc.         |
| `subtype`       | String            | Item, Spell, Talent, etc. (optional)         |
| `text`          | String            | Full rules text                              |
| `traits`        | Array[String]     | e.g., ["Weapon", "Firearm"]                  |
| `icons`         | JSON              | Skill icons: {willpower: 1, intellect: 2, ...} |
| `set`           | String            | Pack/expansion code (e.g., "core", "tfa")    |
| `function`      | String            | damage, clue, defense, econ, draw, etc.      |
| `upgrades`      | Array[CardID]     | XP upgrade chain                             |
| `xp_cost`       | Int               | XP cost (0 for level 0 cards)                |
| `owned`         | Boolean           | User owns this card (set by data import)     |

**Embeddings:** Optional `text_embedding` for semantic search (generated from `text` field).

---

### Collection 2: `characters`

**Purpose:** Store investigator definitions.

| Field               | Type              | Notes                                      |
| ------------------- | ----------------- | ------------------------------------------ |
| `id`                | String            | Character ID (e.g., "01001")               |
| `name`              | String            | Investigator name                          |
| `class`             | String            | Primary class                              |
| `deckbuilding`      | JSON              | Rules for deck construction                |
| `archetypes`        | Array[String]     | Suggested archetypes (manual/AI-tagged)    |
| `locked_cards`      | Array[CardID]     | Signature/required cards                   |
| `default_deck_id`   | String            | Reference to active or starter deck        |

**Deckbuilding JSON example:**
```json
{
  "primary_class": "Seeker",
  "secondary_class": "Neutral",
  "restrictions": "No Guardian cards except level 0",
  "size": 30
}
```

---

### Collection 3: `decks`

**Purpose:** Store user-created decks.

| Field               | Type              | Notes                                   |
| ------------------- | ----------------- | --------------------------------------- |
| `id`                | String            | Deck ID (UUID or custom)                |
| `name`              | String            | User-defined deck name                  |
| `character_id`      | String (FK)       | Links to `characters` collection        |
| `card_list`         | Array[CardID]     | Full list of cards (duplicates allowed) |
| `archetype`         | String            | Clue, fight, hybrid, etc.               |
| `notes`             | Text              | Freeform user notes                     |
| `sim_reports`       | Array[JSON]       | Cached simulation results               |
| `created_at`        | Timestamp         | Deck creation time                      |
| `updated_at`        | Timestamp         | Last modification time                  |

---

## CRUD API Endpoints

**Base URL:** `http://localhost:8000`

### Cards

| Method | Route              | Purpose                          | Query Params                          |
| ------ | ------------------ | -------------------------------- | ------------------------------------- |
| GET    | `/cards`           | Search/filter cards              | `class`, `type`, `cost`, `owned`, `q` (text search) |
| GET    | `/cards/:id`       | Get single card by ID            | —                                     |

**Example:**
```
GET /cards?class=Seeker&type=Asset&cost=2&owned=true
→ Returns all owned Seeker assets costing 2 resources
```

---

### Characters

| Method | Route              | Purpose                    |
| ------ | ------------------ | -------------------------- |
| GET    | `/characters`      | List all investigators     |
| GET    | `/characters/:id`  | Get single character       |

---

### Decks

| Method | Route              | Purpose                          | Body/Params                          |
| ------ | ------------------ | -------------------------------- | ------------------------------------ |
| GET    | `/decks`           | List all decks                   | —                                    |
| GET    | `/decks/:id`       | Get single deck with full data   | —                                    |
| POST   | `/decks`           | Create new deck                  | `{name, character_id, card_list}`    |
| PUT    | `/decks/:id`       | Update deck                      | `{card_list, notes, archetype}`      |
| DELETE | `/decks/:id`       | Delete deck                      | —                                    |

**Example POST:**
```json
{
  "name": "Roland's Investigation Deck",
  "character_id": "01001",
  "card_list": ["01001", "01002", "01003", ...],
  "archetype": "clue",
  "notes": "Focused on investigation with backup combat"
}
```

---

## ChromaDB Client (Service Layer)

### `chroma_client.py`

**Purpose:** Abstraction layer for ChromaDB operations.

```python
class ChromaClient:
    def __init__(self, persist_path: str = "./chroma_data"):
        self.client = chromadb.PersistentClient(path=persist_path)
        self.cards = self.client.get_or_create_collection("cards")
        self.characters = self.client.get_or_create_collection("characters")
        self.decks = self.client.get_or_create_collection("decks")

    # Card operations
    def get_card(self, card_id: str) -> dict:
        """Fetch single card by ID."""
        
    def search_cards(self, filters: dict) -> List[dict]:
        """Search cards with metadata filters."""
    
    def add_card(self, card: dict):
        """Insert new card."""

    # Deck operations
    def get_deck(self, deck_id: str) -> dict:
        """Fetch single deck with full metadata."""
    
    def create_deck(self, deck: dict) -> str:
        """Create deck, return new ID."""
    
    def update_deck(self, deck_id: str, updates: dict):
        """Update deck fields."""
    
    def delete_deck(self, deck_id: str):
        """Remove deck."""

    # Character operations
    def get_character(self, char_id: str) -> dict:
        """Fetch investigator definition."""
    
    def list_characters(self) -> List[dict]:
        """Return all investigators."""
```

---

## Data Validation

**Use Pydantic models for request/response validation:**

```python
from pydantic import BaseModel
from typing import List, Optional

class CardBase(BaseModel):
    name: str
    class_: str
    cost: int
    type: str
    text: str
    owned: bool = False

class DeckCreate(BaseModel):
    name: str
    character_id: str
    card_list: List[str]
    archetype: Optional[str] = "balanced"
    notes: Optional[str] = ""

class DeckResponse(BaseModel):
    id: str
    name: str
    character_id: str
    card_list: List[str]
    archetype: str
    notes: str
    sim_reports: List[dict]
    created_at: str
    updated_at: str
```

---

## Indexing and Performance

**Filters:** ChromaDB supports metadata filtering natively.

**Text search:** Use `query_texts` with embeddings for semantic search:
```python
results = cards.query(
    query_texts=["investigate location"],
    n_results=10,
    where={"class": "Seeker", "owned": True}
)
```

**Caching:**
- Cache frequently accessed decks in memory (LRU cache)
- Invalidate cache on deck updates

---

## File Structure

```
backend/
├── services/
│   ├── chroma_client.py       # ChromaDB interface
│   └── db_models.py           # Pydantic models
├── api/
│   ├── cards.py               # /cards routes
│   ├── characters.py          # /characters routes
│   ├── decks.py               # /decks routes
│   └── __init__.py
└── main.py                    # FastAPI app entry
```

---

## Implementation Notes

- Use FastAPI dependency injection for ChromaDB client
- Add pagination for large result sets (e.g., `/cards?limit=50&offset=0`)
- Log all DB operations for debugging
- Handle ChromaDB exceptions gracefully (return 404/500 as appropriate)
- Backup ChromaDB data directory periodically (simple file copy)

---

## Example Usage (Internal)

```python
# In backend service or AI agent tool
from services.chroma_client import ChromaClient

db = ChromaClient()

# Get deck for analysis
deck = db.get_deck("deck_001")
cards = [db.get_card(card_id) for card_id in deck["card_list"]]

# Filter owned Seeker cards
seekers = db.search_cards({
    "class": "Seeker",
    "owned": True,
    "type": "Asset"
})
```

