from __future__ import annotations

from datetime import UTC, datetime


def get_utc_now() -> str:
    return datetime.now(UTC).isoformat()
