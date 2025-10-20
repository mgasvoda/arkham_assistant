"""Character/Investigator API endpoints."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/")
async def list_characters():
    """List all investigators."""
    # TODO: Implement character listing
    return {"characters": []}


@router.get("/{character_id}")
async def get_character(character_id: str):
    """Get a single investigator by ID."""
    # TODO: Implement character retrieval
    raise HTTPException(status_code=404, detail="Character not found")

