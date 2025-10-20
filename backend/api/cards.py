"""Card API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


@router.get("/")
async def search_cards(
    q: Optional[str] = Query(None, description="Search query for card name or text"),
    class_filter: Optional[str] = Query(None, alias="class", description="Filter by class"),
    type_filter: Optional[str] = Query(None, alias="type", description="Filter by type"),
    cost: Optional[int] = Query(None, description="Filter by resource cost"),
    owned: Optional[bool] = Query(None, description="Filter by ownership status"),
):
    """Search and filter cards."""
    # TODO: Implement card search using ChromaDB
    return {
        "cards": [],
        "filters": {
            "query": q,
            "class": class_filter,
            "type": type_filter,
            "cost": cost,
            "owned": owned,
        },
    }


@router.get("/{card_id}")
async def get_card(card_id: str):
    """Get a single card by ID."""
    # TODO: Implement card retrieval
    raise HTTPException(status_code=404, detail="Card not found")

