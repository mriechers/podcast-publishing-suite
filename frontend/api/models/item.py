from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ItemStatus(str, Enum):
    pending = "pending"
    active = "active"
    completed = "completed"
    failed = "failed"


class ItemBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: ItemStatus = ItemStatus.pending
    priority: int = 0


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ItemStatus] = None
    priority: Optional[int] = None


class Item(ItemBase):
    id: int
    created_at: datetime
    updated_at: datetime


class ItemsResponse(BaseModel):
    items: list[Item]
    total: int
    page: int
    page_size: int
    total_pages: int


class ItemStats(BaseModel):
    pending: int
    active: int
    completed: int
    failed: int
    total: int
