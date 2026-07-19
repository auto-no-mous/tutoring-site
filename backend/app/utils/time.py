from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(dt: datetime) -> datetime:
    """SQLite doesn't preserve tzinfo across a round-trip, so datetimes read back
    from it come out naive even though the column is DateTime(timezone=True).
    Treat naive values as UTC (everything we store is UTC) before comparing."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """SQLite's DateTime storage keeps whatever wall-clock digits it's handed and
    drops the offset - it never converts to UTC on write. A datetime carrying a
    non-UTC offset (e.g. "+03:00" from a client) would silently be stored with the
    wrong instant if persisted as-is. Every externally-supplied datetime must be
    normalized through this before it reaches a query or the DB. Naive values are
    assumed to already be UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
