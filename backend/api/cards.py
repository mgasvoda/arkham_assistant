"""Card API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from backend.services.chroma_client import ChromaClient

router = APIRouter()


def get_chroma_client() -> ChromaClient:
    """Dependency to get ChromaDB client."""
    return ChromaClient()


@router.get("/")
async def search_cards(
    search: Optional[str] = Query(None, description="Search query for card name or text"),
    class_filter: Optional[str] = Query(None, alias="class", description="Filter by class"),
    type_filter: Optional[str] = Query(None, alias="type", description="Filter by type"),
    owned: Optional[bool] = Query(None, description="Filter by ownership status"),
    limit: int = Query(100, description="Maximum number of results"),
    client: ChromaClient = Depends(get_chroma_client),
):
    """Search and filter cards."""
    cards = client.search_cards(
        query=search,
        class_filter=class_filter,
        type_filter=type_filter,
        owned=owned,
        limit=limit
    )
    return cards


@router.get("/{card_id}")
async def get_card(
    card_id: str,
    client: ChromaClient = Depends(get_chroma_client)
):
    """Get a single card by ID."""
    card = client.get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card

