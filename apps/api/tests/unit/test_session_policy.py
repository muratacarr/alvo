from datetime import UTC, datetime, timedelta
from uuid import uuid4

from alvo.identity.domain import SessionPolicy, SessionRecord

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
POLICY = SessionPolicy(idle=timedelta(minutes=30), absolute=timedelta(hours=12))


def record(**overrides: object) -> SessionRecord:
    values: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "created_at": T0,
        "last_seen_at": T0,
        "revoked_at": None,
    }
    values.update(overrides)
    return SessionRecord(**values)  # type: ignore[arg-type]


def test_active_inside_both_windows() -> None:
    assert POLICY.is_active(record(), T0 + timedelta(minutes=29))


def test_expires_after_idle_timeout() -> None:
    assert not POLICY.is_active(record(), T0 + timedelta(minutes=31))


def test_idle_window_slides_with_activity() -> None:
    seen = record(last_seen_at=T0 + timedelta(minutes=25))
    assert POLICY.is_active(seen, T0 + timedelta(minutes=50))


def test_expires_at_absolute_limit_even_when_active() -> None:
    busy = record(last_seen_at=T0 + timedelta(hours=12, minutes=-1))
    assert not POLICY.is_active(busy, T0 + timedelta(hours=12, seconds=1))


def test_revoked_session_is_never_active() -> None:
    assert not POLICY.is_active(record(revoked_at=T0), T0 + timedelta(minutes=1))


def test_clock_skew_into_the_past_does_not_extend_a_session() -> None:
    assert not POLICY.is_active(record(), T0 - timedelta(hours=13))
