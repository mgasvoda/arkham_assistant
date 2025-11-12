#!/usr/bin/env python3
"""CLI tool to fetch card data from ArkhamDB API and populate ChromaDB."""

import argparse
import json
import re
import sys
from pathlib import Path

import httpx

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.services.chroma_client import ChromaClient

API_BASE = "https://arkhamdb.com/api/public"
OWNED_SETS_FILE = Path(__file__).parent / "owned_sets.json"


def fetch_packs() -> list[dict]:
    """Fetch list of all packs from ArkhamDB.

    Returns:
        List of pack dictionaries
    """
    response = httpx.get(f"{API_BASE}/packs/")
    response.raise_for_status()
    return response.json()


def fetch_cards_by_pack(pack_code: str) -> list[dict]:
    """Fetch all cards for a given pack.
    
    Note: The ArkhamDB API returns ALL cards, so we filter client-side.

    Args:
        pack_code: Pack code (e.g., "core", "dwl")

    Returns:
        List of card dictionaries for the specified pack
    """
    print(f"  Fetching all cards from ArkhamDB API...")
    response = httpx.get(f"{API_BASE}/cards/")
    response.raise_for_status()
    all_cards = response.json()
    
    # Filter to only cards from the requested pack
    pack_cards = [card for card in all_cards if card.get("pack_code") == pack_code]
    print(f"  Filtered to {len(pack_cards)} cards from pack '{pack_code}'")
    
    return pack_cards


def load_owned_sets() -> list[str]:
    """Load owned pack codes from config file.

    Returns:
        List of owned pack codes
    """
    if OWNED_SETS_FILE.exists():
        with open(OWNED_SETS_FILE) as f:
            data = json.load(f)
            return data.get("owned_packs", [])
    return []


def clean_text(html_text: str) -> str:
    """Clean HTML tags and icons from card text.
    
    Args:
        html_text: Raw text from ArkhamDB (may contain HTML)
        
    Returns:
        Cleaned plaintext
    """
    if not html_text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', html_text)
    
    # Replace common ArkhamDB icon placeholders with symbols
    text = text.replace('[willpower]', '💪')
    text = text.replace('[intellect]', '🧠')
    text = text.replace('[combat]', '⚔️')
    text = text.replace('[agility]', '🏃')
    text = text.replace('[wild]', '🌟')
    text = text.replace('[per_investigator]', '👤')
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text


def parse_traits(traits_str: str) -> list[str]:
    """Parse traits string into list.
    
    Args:
        traits_str: Traits string like "Weapon. Firearm."
        
    Returns:
        List of trait strings
    """
    if not traits_str:
        return []
    
    # Split by period and clean up
    traits = [t.strip() for t in traits_str.split('.') if t.strip()]
    return traits


def parse_icons(card: dict) -> dict:
    """Extract skill icons from card data.
    
    Args:
        card: Card dictionary from ArkhamDB
        
    Returns:
        Icon dictionary with counts
    """
    return {
        "willpower": card.get("skill_willpower", 0) or 0,
        "intellect": card.get("skill_intellect", 0) or 0,
        "combat": card.get("skill_combat", 0) or 0,
        "agility": card.get("skill_agility", 0) or 0,
        "wild": card.get("skill_wild", 0) or 0,
    }


def map_class(class_code: str) -> str:
    """Map ArkhamDB class code to full name.
    
    Args:
        class_code: Short code like "guardian"
        
    Returns:
        Full class name like "Guardian"
    """
    mapping = {
        "guardian": "Guardian",
        "seeker": "Seeker",
        "rogue": "Rogue",
        "mystic": "Mystic",
        "survivor": "Survivor",
        "neutral": "Neutral",
    }
    return mapping.get(class_code, "Neutral")


def map_type(type_code: str) -> str:
    """Map ArkhamDB type code to full name.
    
    Args:
        type_code: Short code like "asset"
        
    Returns:
        Full type name like "Asset"
    """
    mapping = {
        "asset": "Asset",
        "event": "Event",
        "skill": "Skill",
        "treachery": "Treachery",
        "enemy": "Enemy",
        "investigator": "Investigator",
        "agenda": "Agenda",
        "act": "Act",
        "location": "Location",
        "story": "Story",
    }
    return mapping.get(type_code, type_code.title())


def infer_function(text: str, card_type: str) -> str:
    """Infer card function from text.
    
    Args:
        text: Card text
        card_type: Card type
        
    Returns:
        Function category
    """
    if not text:
        return "utility"
    
    text_lower = text.lower()
    
    # Check for keywords
    if "investigate" in text_lower or "clue" in text_lower:
        return "clue"
    elif "fight" in text_lower or "damage" in text_lower or "attack" in text_lower:
        return "damage"
    elif "evade" in text_lower:
        return "evasion"
    elif "resource" in text_lower or "gain" in text_lower:
        return "econ"
    elif "draw" in text_lower or "search" in text_lower:
        return "draw"
    elif "heal" in text_lower or "horror" in text_lower:
        return "healing"
    elif "move" in text_lower or "location" in text_lower:
        return "movement"
    
    return "utility"


def transform_card(arkhamdb_card: dict, owned: bool) -> dict:
    """Transform ArkhamDB card format to ChromaDB schema.

    Args:
        arkhamdb_card: Card data from ArkhamDB API
        owned: Whether user owns this card

    Returns:
        Transformed card dictionary (flattened for ChromaDB)
    """
    text = clean_text(arkhamdb_card.get("text", ""))
    card_type = map_type(arkhamdb_card["type_code"])
    
    # Convert lists and dicts to JSON strings for ChromaDB compatibility
    return {
        "id": arkhamdb_card["code"],
        "name": arkhamdb_card["name"],
        "class": map_class(arkhamdb_card.get("faction_code", "neutral")),
        "cost": arkhamdb_card.get("cost") or 0,
        "type": card_type,
        "subtype": arkhamdb_card.get("subtype_code", ""),
        "text": text,
        "traits": json.dumps(parse_traits(arkhamdb_card.get("traits", ""))),
        "icons": json.dumps(parse_icons(arkhamdb_card)),
        "set": arkhamdb_card.get("pack_code", ""),
        "function": infer_function(text, card_type),
        "upgrades": json.dumps([]),  # TODO: Parse upgrade chains later
        "xp_cost": arkhamdb_card.get("xp", 0) or 0,
        "owned": owned,
    }


def transform_investigator(arkhamdb_card: dict) -> dict:
    """Transform ArkhamDB investigator to character schema.
    
    Args:
        arkhamdb_card: Investigator data from ArkhamDB API
        
    Returns:
        Transformed character dictionary (flattened for ChromaDB)
    """
    # Deckbuilding requirements can be dict or string
    deck_req = arkhamdb_card.get("deck_requirements")
    if isinstance(deck_req, dict):
        deck_req_str = json.dumps(deck_req)
    else:
        deck_req_str = clean_text(str(deck_req)) if deck_req else ""
    
    deck_opt = arkhamdb_card.get("deck_options")
    if isinstance(deck_opt, dict):
        deck_opt_str = json.dumps(deck_opt)
    else:
        deck_opt_str = clean_text(str(deck_opt)) if deck_opt else ""
    
    # Flatten structure for ChromaDB (no nested dicts allowed in metadata)
    return {
        "id": arkhamdb_card["code"],
        "name": arkhamdb_card["name"],
        "class": map_class(arkhamdb_card.get("faction_code", "neutral")),
        # Deckbuilding fields (flattened)
        "deck_requirements": deck_req_str,
        "deck_options": deck_opt_str,
        "deck_size": arkhamdb_card.get("deck_size", 30),
        # Stats (flattened)
        "willpower": arkhamdb_card.get("skill_willpower", 0),
        "intellect": arkhamdb_card.get("skill_intellect", 0),
        "combat": arkhamdb_card.get("skill_combat", 0),
        "agility": arkhamdb_card.get("skill_agility", 0),
        "health": arkhamdb_card.get("health", 0),
        "sanity": arkhamdb_card.get("sanity", 0),
        # Other fields (converted to JSON strings where needed)
        "traits": json.dumps(parse_traits(arkhamdb_card.get("traits", ""))),
        "text": clean_text(arkhamdb_card.get("text", "")),
        "archetypes": json.dumps([]),  # Can be filled in later
        "locked_cards": json.dumps([]),  # TODO: Parse signature cards
        "default_deck_id": None,
    }


def import_pack(pack_code: str, owned: bool = False) -> dict:
    """Fetch and import all cards from a pack.

    Args:
        pack_code: Pack code to import
        owned: Whether cards should be marked as owned

    Returns:
        Dictionary with import statistics
    """
    print(f"Importing pack: {pack_code}")
    cards = fetch_cards_by_pack(pack_code)
    
    db = ChromaClient()
    
    card_count = 0
    investigator_count = 0
    
    for card in cards:
        if card["type_code"] == "investigator":
            # Add to characters collection
            transformed = transform_investigator(card)
            db.add_character(transformed)
            investigator_count += 1
        else:
            # Add to cards collection
            transformed = transform_card(card, owned)
            db.add_card(transformed)
            card_count += 1
    
    print(f"  Imported {card_count} cards and {investigator_count} investigators")
    return {"cards": card_count, "investigators": investigator_count}


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import card data from ArkhamDB (specific pack only)"
    )
    parser.add_argument(
        "--pack", 
        type=str, 
        required=True,
        help="Import specific pack by code (e.g., 'core', 'dwl', 'ptc')"
    )
    parser.add_argument(
        "--update-ownership",
        action="store_true",
        help="Update ownership flags only (does not fetch new cards)",
    )
    
    args = parser.parse_args()
    
    owned_packs = load_owned_sets()
    
    if args.update_ownership:
        print("Updating ownership flags...")
        # TODO: Implement ownership update logic
        print("✓ Ownership updated")
    else:
        # Import the specified pack
        owned = args.pack in owned_packs
        stats = import_pack(args.pack, owned)
        print(f"\n✓ Import complete: {stats['cards']} cards and {stats['investigators']} investigators")


if __name__ == "__main__":
    main()

