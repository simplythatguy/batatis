"""Purpose-based inactivity windows. Reading never extends retention."""
from datetime import datetime, timedelta, timezone

RETENTION_DAYS = 7
DRAFT_RETENTION_DAYS = 180
CLOSED_RETENTION_DAYS = 730
ACTIVE_REVIEW_STATUSES = frozenset({'submitted', 'in_review', 'returned'})


def expiry_at(updated_at: str, *, status: str = 'draft', owner_id: str | None = None) -> str | None:
    if status in ACTIVE_REVIEW_STATUSES:
        return None
    days = CLOSED_RETENTION_DAYS if status in {'accepted', 'refused', 'withdrawn'} else DRAFT_RETENTION_DAYS if owner_id else RETENTION_DAYS
    try:
        updated = datetime.fromisoformat(updated_at)
    except (ValueError, TypeError):
        return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return (updated + timedelta(days=days)).isoformat()
