#!/usr/bin/env python3
"""CLI tool to fetch card data from ArkhamDB API and populate ChromaDB."""

import argparse
import json
from pathlib import Path

import httpx

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

    Args:
        pack_code: Pack code (e.g., "core", "dwl")

    Returns:
        List of card dictionaries
    """
    response = httpx.get(f"{API_BASE}/cards/", params={"pack_code": pack_code})
    response.raise_for_status()
    return response.json()


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


def transform_card(arkhamdb_card: dict, owned: bool) -> dict:
    """Transform ArkhamDB card format to ChromaDB schema.

    Args:
        arkhamdb_card: Card data from ArkhamDB API
        owned: Whether user owns this card

    Returns:
        Transformed card dictionary
    """
    # TODO: Implement full transformation logic
    return {
        "id": arkhamdb_card["code"],
        "name": arkhamdb_card["name"],
        "class": arkhamdb_card.get("class_code", "neutral"),
        "cost": arkhamdb_card.get("cost", 0),
        "type": arkhamdb_card["type_code"],
        "text": arkhamdb_card.get("text", ""),
        "owned": owned,
    }


def import_pack(pack_code: str, owned: bool = False) -> int:
    """Fetch and import all cards from a pack.

    Args:
        pack_code: Pack code to import
        owned: Whether cards should be marked as owned

    Returns:
        Number of cards imported
    """
    print(f"Importing pack: {pack_code}")
    cards = fetch_cards_by_pack(pack_code)
    
    # TODO: Transform and insert into ChromaDB
    for card in cards:
        transformed = transform_card(card, owned)
        # Insert into ChromaDB
    
    print(f"  Imported {len(cards)} cards")
    return len(cards)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Import card data from ArkhamDB")
    parser.add_argument("--full", action="store_true", help="Import all packs")
    parser.add_argument("--pack", type=str, help="Import specific pack by code")
    parser.add_argument(
        "--update-ownership",
        action="store_true",
        help="Update ownership flags only",
    )
    
    args = parser.parse_args()
    
    owned_packs = load_owned_sets()
    
    if args.full:
        print("Fetching all packs from ArkhamDB...")
        packs = fetch_packs()
        total_cards = 0
        
        for pack in packs:
            owned = pack["code"] in owned_packs
            cards_imported = import_pack(pack["code"], owned)
            total_cards += cards_imported
        
        print(f"\n✓ Import complete: {total_cards} cards from {len(packs)} packs")
    
    elif args.pack:
        owned = args.pack in owned_packs
        cards_imported = import_pack(args.pack, owned)
        print(f"\n✓ Import complete: {cards_imported} cards")
    
    elif args.update_ownership:
        print("Updating ownership flags...")
        # TODO: Implement ownership update logic
        print("✓ Ownership updated")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

