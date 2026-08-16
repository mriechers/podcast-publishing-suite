from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from api.models.item import Item, ItemCreate, ItemUpdate, ItemsResponse, ItemStats
from api.services.mock_data import store
from api.routers.websocket import broadcast_update

router = APIRouter()


@router.get("/api/items", response_model=ItemsResponse)
async def get_items(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title and description")
):
    """Get paginated list of items with optional filters."""
    return store.get_all(
        page=page,
        page_size=page_size,
        status=status,
        search=search
    )


@router.get("/api/items/stats", response_model=ItemStats)
async def get_items_stats():
    """Get statistics for all items."""
    return store.get_stats()


@router.get("/api/items/{item_id}", response_model=Item)
async def get_item(item_id: int):
    """Get a single item by ID."""
    item = store.get_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/api/items", response_model=Item, status_code=201)
async def create_item(item_create: ItemCreate):
    """Create a new item."""
    new_item = store.create(item_create)

    # Broadcast updates via WebSocket
    await broadcast_update("item_created", item=new_item)

    stats = store.get_stats()
    await broadcast_update("stats_updated", stats=stats)

    return new_item


@router.patch("/api/items/{item_id}", response_model=Item)
async def update_item(item_id: int, item_update: ItemUpdate):
    """Partially update an item."""
    updated_item = store.update(item_id, item_update)
    if updated_item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    # Broadcast updates via WebSocket
    await broadcast_update("item_updated", item=updated_item)

    stats = store.get_stats()
    await broadcast_update("stats_updated", stats=stats)

    return updated_item


@router.delete("/api/items/{item_id}")
async def delete_item(item_id: int):
    """Delete an item."""
    success = store.delete(item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")

    # Broadcast updates via WebSocket
    await broadcast_update("item_deleted", item={"id": item_id})

    stats = store.get_stats()
    await broadcast_update("stats_updated", stats=stats)

    return {"message": "Item deleted"}
