from datetime import datetime, timedelta
from typing import Optional
import math

from api.models.item import Item, ItemCreate, ItemUpdate, ItemStatus, ItemsResponse, ItemStats


class Store:
    def __init__(self):
        self.next_id = 16
        self.items: list[Item] = self._seed_items()

    def _seed_items(self) -> list[Item]:
        """Seed the store with 15 realistic items spread across all statuses."""
        now = datetime.now()

        seed_data = [
            # 4 pending
            {"id": 1, "title": "Import user data", "description": "Import CSV file with 10k user records", "status": ItemStatus.pending, "priority": 3, "days_ago": 1},
            {"id": 2, "title": "Generate monthly report", "description": "Create analytics report for January", "status": ItemStatus.pending, "priority": 2, "days_ago": 2},
            {"id": 3, "title": "Backup database", "description": "Full database backup to S3", "status": ItemStatus.pending, "priority": 5, "days_ago": 0},
            {"id": 4, "title": "Process invoices", "description": "Batch process pending invoices", "status": ItemStatus.pending, "priority": 4, "days_ago": 3},

            # 3 active
            {"id": 5, "title": "Update permissions", "description": "Review and update user access permissions", "status": ItemStatus.active, "priority": 3, "days_ago": 1},
            {"id": 6, "title": "Sync inventory", "description": "Synchronize inventory with warehouse system", "status": ItemStatus.active, "priority": 2, "days_ago": 0},
            {"id": 7, "title": "Deploy staging", "description": "Deploy latest build to staging environment", "status": ItemStatus.active, "priority": 4, "days_ago": 2},

            # 5 completed
            {"id": 8, "title": "Review analytics", "description": "Weekly analytics review meeting", "status": ItemStatus.completed, "priority": 1, "days_ago": 6},
            {"id": 9, "title": "Archive old records", "description": "Archive records older than 2 years", "status": ItemStatus.completed, "priority": 2, "days_ago": 5},
            {"id": 10, "title": "Configure notifications", "description": "Set up email notification system", "status": ItemStatus.completed, "priority": 3, "days_ago": 4},
            {"id": 11, "title": "Migrate legacy data", "description": "Migrate data from old system", "status": ItemStatus.completed, "priority": 5, "days_ago": 7},
            {"id": 12, "title": "Validate schemas", "description": "Validate all database schemas", "status": ItemStatus.completed, "priority": 2, "days_ago": 6},

            # 3 failed
            {"id": 13, "title": "Optimize queries", "description": "Optimize slow-running database queries", "status": ItemStatus.failed, "priority": 4, "days_ago": 3},
            {"id": 14, "title": "Build dashboard widgets", "description": "Create new dashboard widget components", "status": ItemStatus.failed, "priority": 2, "days_ago": 4},
            {"id": 15, "title": "Test payment flow", "description": "End-to-end testing of payment processing", "status": ItemStatus.failed, "priority": 5, "days_ago": 2},
        ]

        items = []
        for data in seed_data:
            created = now - timedelta(days=data["days_ago"])
            updated = created + timedelta(hours=data["days_ago"] * 3)  # Some time after creation

            items.append(Item(
                id=data["id"],
                title=data["title"],
                description=data["description"],
                status=data["status"],
                priority=data["priority"],
                created_at=created,
                updated_at=updated
            ))

        return items

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> ItemsResponse:
        """Get all items with pagination, optional status filter, and search."""
        filtered_items = self.items

        # Apply status filter
        if status:
            try:
                status_enum = ItemStatus(status)
                filtered_items = [item for item in filtered_items if item.status == status_enum]
            except ValueError:
                pass  # Invalid status, ignore filter

        # Apply search filter (search in title and description)
        if search:
            search_lower = search.lower()
            filtered_items = [
                item for item in filtered_items
                if search_lower in item.title.lower() or
                   (item.description and search_lower in item.description.lower())
            ]

        total = len(filtered_items)
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0

        # Calculate pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_items = filtered_items[start_idx:end_idx]

        return ItemsResponse(
            items=paginated_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    def get_by_id(self, item_id: int) -> Optional[Item]:
        """Get a single item by ID."""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def create(self, item_create: ItemCreate) -> Item:
        """Create a new item."""
        now = datetime.now()
        new_item = Item(
            id=self.next_id,
            title=item_create.title,
            description=item_create.description,
            status=item_create.status,
            priority=item_create.priority,
            created_at=now,
            updated_at=now
        )
        self.items.append(new_item)
        self.next_id += 1
        return new_item

    def update(self, item_id: int, item_update: ItemUpdate) -> Optional[Item]:
        """Update an existing item."""
        for idx, item in enumerate(self.items):
            if item.id == item_id:
                # Update only provided fields
                update_data = item_update.model_dump(exclude_unset=True)
                updated_item = item.model_copy(update={
                    **update_data,
                    "updated_at": datetime.now()
                })
                self.items[idx] = updated_item
                return updated_item
        return None

    def delete(self, item_id: int) -> bool:
        """Delete an item by ID."""
        for idx, item in enumerate(self.items):
            if item.id == item_id:
                self.items.pop(idx)
                return True
        return False

    def get_stats(self) -> ItemStats:
        """Get statistics for all items."""
        stats = {
            "pending": 0,
            "active": 0,
            "completed": 0,
            "failed": 0,
        }

        for item in self.items:
            stats[item.status.value] += 1

        return ItemStats(
            pending=stats["pending"],
            active=stats["active"],
            completed=stats["completed"],
            failed=stats["failed"],
            total=len(self.items)
        )


# Global store instance
store = Store()
