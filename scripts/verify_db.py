#!/usr/bin/env python3
"""Verify ChromaDB contents."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.services.chroma_client import ChromaClient


def main():
    """Check ChromaDB collections and contents."""
    db = ChromaClient()
    
    # Get collection counts
    cards_count = db.cards.count()
    characters_count = db.characters.count()
    decks_count = db.decks.count()
    
    print("=== ChromaDB Status ===")
    print(f"Cards: {cards_count}")
    print(f"Characters: {characters_count}")
    print(f"Decks: {decks_count}")
    print()
    
    # Show a sample card
    if cards_count > 0:
        print("=== Sample Card ===")
        sample = db.cards.get(limit=1, include=["metadatas", "documents"])
        if sample and sample["ids"]:
            card_id = sample["ids"][0]
            metadata = sample["metadatas"][0]
            doc = sample["documents"][0]
            print(f"ID: {card_id}")
            print(f"Name: {doc}")
            print(f"Class: {metadata.get('class')}")
            print(f"Type: {metadata.get('type')}")
            print(f"Cost: {metadata.get('cost')}")
            print(f"Owned: {metadata.get('owned')}")
            print()
    
    # Show a sample investigator
    if characters_count > 0:
        print("=== Sample Investigator ===")
        sample = db.characters.get(limit=1, include=["metadatas", "documents"])
        if sample and sample["ids"]:
            char_id = sample["ids"][0]
            metadata = sample["metadatas"][0]
            doc = sample["documents"][0]
            print(f"ID: {char_id}")
            print(f"Name: {doc}")
            print(f"Class: {metadata.get('class')}")
            print(f"Stats: WIL {metadata.get('willpower')} INT {metadata.get('intellect')} "
                  f"COM {metadata.get('combat')} AGI {metadata.get('agility')}")
            print(f"Health: {metadata.get('health')} Sanity: {metadata.get('sanity')}")
            print()
    
    print("✓ Database verification complete!")


if __name__ == "__main__":
    main()

