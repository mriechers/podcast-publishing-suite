from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import health, items, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Cardigan Dashboard API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - allow all origins for local dev template
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(items.router, tags=["items"])
app.include_router(websocket.router, tags=["websocket"])
