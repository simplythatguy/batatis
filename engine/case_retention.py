"""One creation-based case expiry policy, shared by storage and its visible notice."""
from datetime import datetime, timedelta, timezone

RETENTION_DAYS = 7


def expiry_at(created_at: str) -> str | None:
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (created + timedelta(days=RETENTION_DAYS)).isoformat()
