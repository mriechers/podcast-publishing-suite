from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set, Optional, Any
import json

router = APIRouter()

# Set of connected WebSocket clients
connected_clients: Set[WebSocket] = set()


@router.websocket("/api/ws/updates")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    connected_clients.add(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            # Handle ping messages (frontend sends JSON: {"type": "ping"})
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except (json.JSONDecodeError, TypeError):
                if data == "ping":
                    await websocket.send_text("pong")
    except WebSocketDisconnect:
        connected_clients.remove(websocket)


async def broadcast_update(
    event_type: str,
    item: Optional[Any] = None,
    stats: Optional[Any] = None
):
    """Broadcast an update to all connected WebSocket clients.

    Args:
        event_type: Type of event (item_created, item_updated, item_deleted, stats_updated)
        item: Item data to broadcast (optional)
        stats: Stats data to broadcast (optional)
    """
    message = {
        "type": event_type,
    }

    if item:
        # Convert Pydantic model to dict for JSON serialization
        message["item"] = item.model_dump(mode="json")

    if stats:
        # Convert Pydantic model to dict for JSON serialization
        message["stats"] = stats.model_dump(mode="json")

    # Send to all connected clients
    disconnected_clients = set()
    for client in connected_clients:
        try:
            await client.send_json(message)
        except Exception:
            # Client disconnected, mark for removal
            disconnected_clients.add(client)

    # Remove disconnected clients
    for client in disconnected_clients:
        connected_clients.discard(client)
