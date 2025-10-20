# Data Retrieval Tool Design — Arkham Assistant

## Overview

CLI utility for fetching card and pack data from **ArkhamDB API** and populating ChromaDB. Runs manually when new expansions are released or during initial setup.

**Key principle:** One-time fetch, no real-time API calls during normal operation.

---

## ArkhamDB API Endpoints

**Base URL:** `https://arkhamdb.com/api/public`

### 1. Get All Packs
```
GET /packs/
→ Returns list of all packs/expansions
```

**Response example:**
```json
[
  {
    "code": "core",
    "name": "Core Set",
    "position": 1,
    "size": 120,
    "cycle_position": 1
  },
  ...
]
```

### 2. Get Cards by Pack
```
GET /cards/?pack_code=core
→ Returns all cards in specified pack
```

**Response example:**
```json
[
  {
    "code": "01001",
    "name": "Roland Banks",
    "type_code": "investigator",
    "class_code": "guardian",
    "cost": null,
    "text": "...",
    "traits": "Agency. Detective.",
    "skill_willpower": 3,
    "skill_intellect": 3,
    "skill_combat": 4,
    "skill_agility": 2,
    "deck_requirements": "...",
    "pack_code": "core"
  },
  ...
]
```

---

## Data Fetching Flow

```
1. Fetch pack list from /packs/
2. For each pack:
   a. Check if pack already imported (compare code + size)
   b. If new/updated, fetch cards via /cards/?pack_code=X
   c. Transform API response to ChromaDB schema
   d. Insert/update cards in ChromaDB
3. Mark pack as imported (store metadata in ChromaDB or JSON)
4. Generate import report (# cards added/updated)
```

---

## Field Mapping (ArkhamDB → ChromaDB)

| ArkhamDB Field      | ChromaDB Field | Transform                                |
| ------------------- | -------------- | ---------------------------------------- |
| `code`              | `id`           | Direct                                   |
| `name`              | `name`         | Direct                                   |
| `class_code`        | `class`        | Map to full name (e.g., "guardian" → "Guardian") |
| `cost`              | `cost`         | Direct (handle null for investigators)   |
| `type_code`         | `type`         | Map to full name (e.g., "asset" → "Asset") |
| `subtype_code`      | `subtype`      | Map if present                           |
| `text`              | `text`         | Clean HTML tags, format plaintext        |
| `traits`            | `traits`       | Split by ". " into array                 |
| `skill_*`           | `icons`        | Aggregate into JSON: {willpower: N, ...} |
| `pack_code`         | `set`          | Direct                                   |
| `xp`                | `xp_cost`      | Default 0 if null                        |

**Derived fields:**
- `function`: Infer from card text (keywords like "investigate", "fight", "evade")
- `owned`: Set based on local config file (e.g., `owned_sets.json`)
- `upgrades`: Parse upgrade chain from ArkhamDB (or leave empty initially)

---

## Ownership Tracking

**Config file:** `scripts/owned_sets.json`

```json
{
  "owned_packs": [
    "core",
    "dwl",
    "ptc",
    "eotp"
  ]
}
```

**Logic:**
- During import, set `owned = true` if `pack_code` in `owned_packs`
- Update this file manually when acquiring new packs
- Re-run import script to update ownership flags

---

## CLI Script: `fetch_arkhamdb.py`

### Usage

```bash
# Full import (all packs)
python scripts/fetch_arkhamdb.py --full

# Import specific pack
python scripts/fetch_arkhamdb.py --pack core

# Update ownership flags only
python scripts/fetch_arkhamdb.py --update-ownership
```

### Implementation Outline

```python
import requests
from backend.services.chroma_client import ChromaClient

API_BASE = "https://arkhamdb.com/api/public"

def fetch_packs():
    """Fetch list of all packs."""
    response = requests.get(f"{API_BASE}/packs/")
    return response.json()

def fetch_cards_by_pack(pack_code: str):
    """Fetch all cards for a given pack."""
    response = requests.get(f"{API_BASE}/cards/?pack_code={pack_code}")
    return response.json()

def transform_card(arkhamdb_card: dict, owned: bool) -> dict:
    """Map ArkhamDB fields to ChromaDB schema."""
    return {
        "id": arkhamdb_card["code"],
        "name": arkhamdb_card["name"],
        "class": map_class(arkhamdb_card.get("class_code")),
        "cost": arkhamdb_card.get("cost", 0),
        "type": map_type(arkhamdb_card["type_code"]),
        "text": clean_text(arkhamdb_card.get("text", "")),
        "traits": parse_traits(arkhamdb_card.get("traits", "")),
        "icons": parse_icons(arkhamdb_card),
        "set": arkhamdb_card["pack_code"],
        "xp_cost": arkhamdb_card.get("xp", 0),
        "owned": owned,
        # ... other fields
    }

def import_pack(pack_code: str, owned: bool = False):
    """Fetch and import all cards from a pack."""
    cards = fetch_cards_by_pack(pack_code)
    db = ChromaClient()
    
    for card in cards:
        transformed = transform_card(card, owned)
        db.add_card(transformed)
    
    print(f"Imported {len(cards)} cards from {pack_code}")

def main():
    # Parse CLI args
    # Load owned_sets.json
    # Fetch packs, iterate and import
    pass

if __name__ == "__main__":
    main()
```

---

## Helper Functions

### `clean_text(html_text: str) -> str`
- Strip HTML tags (e.g., `<b>`, `<i>`)
- Replace ArkhamDB icons (e.g., `[willpower]`) with plaintext or emoji
- Normalize whitespace

### `parse_traits(traits_str: str) -> List[str]`
- Split "Weapon. Firearm." → `["Weapon", "Firearm"]`

### `parse_icons(card: dict) -> dict`
- Extract `skill_willpower`, `skill_intellect`, etc.
- Return: `{"willpower": 1, "intellect": 2, "combat": 0, "agility": 1}`

### `infer_function(text: str) -> str`
- Keyword matching: "investigate" → "clue", "fight" → "damage", etc.
- Fallback to "utility" if ambiguous

---

## Error Handling

- **API rate limits:** Add `time.sleep(0.5)` between requests
- **Missing fields:** Provide sensible defaults (e.g., `cost = 0`, `traits = []`)
- **Duplicate imports:** Use upsert logic (update if ID exists)
- **Network failures:** Retry up to 3 times with exponential backoff

---

## Import Report

After successful import, generate summary:

```
=== ArkhamDB Import Report ===
Date: 2025-10-20
Packs imported: 5
Cards added: 234
Cards updated: 12
Owned cards: 187 / 234
===========================
```

Save to `logs/import_YYYYMMDD.log` for reference.

---

## File Structure

```
scripts/
├── fetch_arkhamdb.py       # Main CLI script
├── owned_sets.json         # Ownership config
└── transforms.py           # Field mapping helpers

logs/
└── import_*.log            # Import reports
```

---

## Implementation Notes

- Run this script only when:
  1. Setting up project for first time
  2. New expansion released and purchased
  3. Ownership config changes
- Consider adding `--dry-run` flag to preview changes without writing
- Store ArkhamDB API version in metadata for future compatibility
- No need for scheduled/automated runs (data is static)

---

## Future Enhancements

- Auto-detect new packs by comparing local DB vs. API
- Generate `TextEmbedding` for semantic search (OpenAI embeddings API)
- Parse upgrade chains from ArkhamDB relationships
- Fetch investigator deckbuilding rules and store in `characters` collection

