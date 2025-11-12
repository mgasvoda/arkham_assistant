"""Deck API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.services.chroma_client import ChromaClient

router = APIRouter()


def get_chroma_client() -> ChromaClient:
    """Dependency to get ChromaDB client."""
    return ChromaClient()


class DeckCreate(BaseModel):
    """Request model for deck creation."""

    name: str
    investigator_code: Optional[str] = None
    investigator_name: Optional[str] = None
    cards: list[dict] = []
    archetype: Optional[str] = "balanced"
    notes: Optional[str] = ""


class DeckUpdate(BaseModel):
    """Request model for deck updates."""

    name: Optional[str] = None
    investigator_code: Optional[str] = None
    investigator_name: Optional[str] = None
    cards: Optional[list[dict]] = None
    archetype: Optional[str] = None
    notes: Optional[str] = None


@router.get("/")
async def list_decks(
    client: ChromaClient = Depends(get_chroma_client)
):
    """List all decks."""
    decks = client.list_decks()
    return decks


@router.get("/{deck_id}")
async def get_deck(
    deck_id: str,
    client: ChromaClient = Depends(get_chroma_client)
):
    """Get a single deck by ID."""
    deck = client.get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


@router.post("/")
async def create_deck(
    deck: DeckCreate,
    client: ChromaClient = Depends(get_chroma_client)
):
    """Create a new deck."""
    try:
        deck_id = client.create_deck(deck.model_dump())
        created_deck = client.get_deck(deck_id)
        return created_deck
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create deck: {str(e)}")


@router.put("/{deck_id}")
async def update_deck(
    deck_id: str,
    updates: DeckUpdate,
    client: ChromaClient = Depends(get_chroma_client)
):
    """Update an existing deck."""
    try:
        # Filter out None values
        update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
        client.update_deck(deck_id, update_data)
        updated_deck = client.get_deck(deck_id)
        return updated_deck
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update deck: {str(e)}")


@router.delete("/{deck_id}")
async def delete_deck(
    deck_id: str,
    client: ChromaClient = Depends(get_chroma_client)
):
    """Delete a deck."""
    try:
        # Check if deck exists
        deck = client.get_deck(deck_id)
        if not deck:
            raise HTTPException(status_code=404, detail="Deck not found")
        
        client.delete_deck(deck_id)
        return {"message": "Deck deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete deck: {str(e)}")

