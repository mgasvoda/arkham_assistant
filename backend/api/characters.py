"""Character/Investigator API endpoints."""

from fastapi import APIRouter, HTTPException, Depends

from backend.services.chroma_client import ChromaClient

router = APIRouter()


def get_chroma_client() -> ChromaClient:
    """Dependency to get ChromaDB client."""
    return ChromaClient()


@router.get("/")
async def list_characters(
    client: ChromaClient = Depends(get_chroma_client)
):
    """List all investigators."""
    characters = client.list_characters()
    return characters


@router.get("/{character_id}")
async def get_character(
    character_id: str,
    client: ChromaClient = Depends(get_chroma_client)
):
    """Get a single investigator by ID."""
    character = client.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character

