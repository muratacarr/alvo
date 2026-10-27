"""PostgreSQL-backed fixed-window rate limiter (ADR 0009).

One row per (bucket, window). Counting happens in a short transaction of its own, so a
request that later fails and rolls back still counts. The counters live in the database, not
in process memory, so they survive restarts and stay correct if the API runs several workers.
They are NOT designed for several database primaries; the project runs one instance.

A fixed window lets a client use up to twice the limit across a window boundary. That is an
accepted trade-off for a limiter whose job is to stop abuse, not to meter usage.
"""

from datetime import datetime, timedelta

from fastapi import Request
from sqlalchemy import DateTime, Integer, String, delete, text
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from alvo.shared.errors import ApiError
from alvo.shared.orm import Base

WINDOW_SECONDS = 60
# Rows older than this are deleted whenever a bucket opens a new window.
_KEEP = timedelta(hours=2)


class RateLimitCounterRow(Base):
    __tablename__ = "rate_limit_counters"

    bucket: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    hits: Mapped[int] = mapped_column(Integer)


def _window_start(now: datetime) -> datetime:
    return now.replace(second=0, microsecond=0)


def hit(factory: sessionmaker[Session], bucket: str, limit: int, now: datetime) -> bool:
    """Count one request against `bucket`; False when the limit for this window is exceeded."""
    window = _window_start(now)
    with factory() as db, db.begin():
        hits = db.execute(
            text(
                "INSERT INTO rate_limit_counters (bucket, window_start, hits) "
                "VALUES (:bucket, :window, 1) "
                "ON CONFLICT (bucket, window_start) "
                "DO UPDATE SET hits = rate_limit_counters.hits + 1 "
                "RETURNING hits"
            ),
            {"bucket": bucket, "window": window},
        ).scalar_one()
        if hits == 1:
            db.execute(
                delete(RateLimitCounterRow).where(RateLimitCounterRow.window_start < now - _KEEP)
            )
    return int(hits) <= limit


def enforce(request: Request, bucket: str, limit: int) -> None:
    """Raise 429 when `bucket` is over `limit` for the current minute."""
    if not hit(request.app.state.session_factory, bucket, limit, request.app.state.clock()):
        raise ApiError(429, "rate_limited")
