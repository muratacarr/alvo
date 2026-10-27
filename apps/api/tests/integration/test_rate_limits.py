from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from alvo.main import create_app
from alvo.shared.ratelimit import hit
from tests.conftest import SettingsFactory
from tests.integration.support import ORIGIN, Actor

NOW = datetime(2026, 3, 1, 12, 0, 30, tzinfo=UTC)


def test_a_user_is_limited_per_minute_and_other_users_are_not(
    new_actor: Callable[..., Actor],
) -> None:
    busy = new_actor(user_requests_per_minute="3")
    for _ in range(3):
        assert busy.get("/api/v1/auth/me").status_code == 200
    limited = busy.get("/api/v1/auth/me")
    assert limited.status_code == 429
    assert limited.json() == {"error": "rate_limited"}

    other = new_actor(user_requests_per_minute="3")
    assert other.get("/api/v1/auth/me").status_code == 200


def test_unsafe_auth_requests_are_limited_per_client_address(
    migrated_database_url: str, settings_factory: SettingsFactory
) -> None:
    settings = settings_factory(
        database_url=migrated_database_url,
        auth_attempts_per_minute="2",
        trust_forwarded_for="true",
    )
    client = TestClient(
        create_app(settings, readiness_probe=lambda: True), base_url="https://testserver"
    )
    attacker = {"X-Forwarded-For": "203.0.113.7"}
    statuses = [
        client.post(
            "/api/v1/auth/dev-login",
            json={"subject": uuid4().hex},
            headers={**ORIGIN, **attacker},
        ).status_code
        for _ in range(3)
    ]
    assert statuses == [200, 200, 429]

    elsewhere = client.post(
        "/api/v1/auth/dev-login",
        json={"subject": uuid4().hex},
        headers={**ORIGIN, "X-Forwarded-For": "203.0.113.8"},
    )
    assert elsewhere.status_code == 200


def test_the_counter_resets_in_the_next_window_and_old_rows_are_pruned(
    migrated_database_url: str,
) -> None:
    engine = create_engine(migrated_database_url)
    factory = sessionmaker(engine)
    bucket = f"test:{uuid4().hex}"
    stale = f"test:{uuid4().hex}"
    with factory() as db, db.begin():
        db.execute(
            text("INSERT INTO rate_limit_counters VALUES (:b, :w, 1)"),
            {"b": stale, "w": NOW - timedelta(hours=3)},
        )

    assert hit(factory, bucket, 2, NOW)
    assert hit(factory, bucket, 2, NOW + timedelta(seconds=5))
    assert not hit(factory, bucket, 2, NOW + timedelta(seconds=10))
    assert hit(factory, bucket, 2, NOW + timedelta(seconds=40))  # next minute

    with factory() as db:
        remaining = db.execute(
            text("SELECT count(*) FROM rate_limit_counters WHERE bucket = :b"), {"b": stale}
        ).scalar_one()
    assert remaining == 0
    engine.dispose()
