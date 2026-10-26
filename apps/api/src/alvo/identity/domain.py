"""Identity domain: pure rules, no framework or database imports."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

# Tolerance for harmless clock jitter; anything earlier than this is treated as invalid.
_CLOCK_SKEW = timedelta(seconds=5)


@dataclass(frozen=True)
class VerifiedIdentity:
    """A subject asserted by a trusted identity provider (the mock one in development)."""

    provider: str
    subject: str


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. Modules must take their user id from here, never the client."""

    user_id: UUID


@dataclass(frozen=True)
class SessionRecord:
    id: UUID
    user_id: UUID
    created_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True)
class SessionPolicy:
    idle: timedelta
    absolute: timedelta

    def is_active(self, session: SessionRecord, now: datetime) -> bool:
        if session.revoked_at is not None:
            return False
        if now < session.created_at - _CLOCK_SKEW:
            return False
        if now - session.created_at > self.absolute:
            return False
        return now - session.last_seen_at <= self.idle
