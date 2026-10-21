"""Shared record identifiers and UTC timestamps, independent of record schemas."""
import uuid
from datetime import datetime, timezone


def new_id(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex}'


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')
