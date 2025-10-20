"""Deck API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class DeckCreate(BaseModel):
    """Request model for deck creation."""

    name: str
    character_id: str
    card_list: list[str]
    archetype: Optional[str] = "balanced"
    notes: Optional[str] = ""


class DeckUpdate(BaseModel):
    """Request model for deck updates."""

    name: Optional[str] = None
    card_list: Optional[list[str]] = None
    archetype: Optional[str] = None
    notes: Optional[str] = None


@router.get("/")
async def list_decks():
    """List all decks."""
    # TODO: Implement deck listing
    return {"decks": []}


@router.get("/{deck_id}")
async def get_deck(deck_id: str):
    """Get a single deck by ID."""
    # TODO: Implement deck retrieval
    raise HTTPException(status_code=404, detail="Deck not found")


@router.post("/")
async def create_deck(deck: DeckCreate):
    """Create a new deck."""
    # TODO: Implement deck creation
    return {"deck_id": "new_deck_id", "message": "Deck created"}


@router.put("/{deck_id}")
async def update_deck(deck_id: str, updates: DeckUpdate):
    """Update an existing deck."""
    # TODO: Implement deck update
    return {"deck_id": deck_id, "message": "Deck updated"}


@router.delete("/{deck_id}")
async def delete_deck(deck_id: str):
    """Delete a deck."""
    # TODO: Implement deck deletion
    return {"message": "Deck deleted"}

