from fastapi import APIRouter

from api.services.mock_data import store

router = APIRouter()


@router.get("/api/health")
async def health_check():
    """Health check endpoint with current stats."""
    stats = store.get_stats()
    return {
        "status": "ok",
        "stats": {
            "pending": stats.pending,
            "active": stats.active,
            "completed": stats.completed,
            "failed": stats.failed,
            "total": stats.total
        }
    }
