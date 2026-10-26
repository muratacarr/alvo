"""Session, CSRF and isolation behaviour of the identity API against a real PostgreSQL."""

import logging
import re
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alvo.main import create_app
from tests.conftest import SettingsFactory
from tests.integration.conftest import FakeClock

COOKIE = "__Host-alvo_session"
ORIGIN = {"Origin": "https://testserver"}
LOGIN = "/api/v1/auth/dev-login"
ME = "/api/v1/auth/me"
LOGOUT = "/api/v1/auth/logout"


@pytest.fixture
def make_client(
    migrated_database_url: str, settings_factory: SettingsFactory, clock: FakeClock
) -> Callable[..., TestClient]:
    def build(**overrides: str) -> TestClient:
        settings = settings_factory(database_url=migrated_database_url, **overrides)
        app = create_app(settings, readiness_probe=lambda: True, clock=clock)
        return TestClient(app, base_url="https://testserver")

    return build


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


def login(client: TestClient, subject: str | None = None) -> dict[str, Any]:
    response = client.post(LOGIN, json={"subject": subject or uuid4().hex}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_unauthenticated_requests_get_a_generic_401(client: TestClient) -> None:
    response = client.get(ME)
    assert response.status_code == 401
    assert response.json() == {"error": "unauthenticated"}


def test_login_sets_a_hardened_session_cookie(client: TestClient) -> None:
    response = client.post(LOGIN, json={"subject": uuid4().hex}, headers=ORIGIN)
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE}=")
    for attribute in ("HttpOnly", "Secure", "SameSite=lax", "Path=/"):
        assert attribute.lower() in cookie.lower(), attribute
    assert "domain" not in cookie.lower()
    assert "max-age" in cookie.lower() or "expires" in cookie.lower()


def test_authenticated_request_returns_the_user(client: TestClient) -> None:
    body = login(client)
    me = client.get(ME)
    assert me.status_code == 200
    assert me.json() == {"user_id": body["user_id"], "role": "user"}


def test_session_token_is_never_stored_in_clear_text(
    client: TestClient, migrated_database_url: str
) -> None:
    body = login(client)
    raw_token = client.cookies[COOKIE]
    engine = create_engine(migrated_database_url)
    with engine.connect() as connection:
        hashes = (
            connection.execute(
                text("SELECT token_hash FROM sessions WHERE user_id = :u"), {"u": body["user_id"]}
            )
            .scalars()
            .all()
        )
    engine.dispose()
    assert hashes
    assert all(raw_token not in value and re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes)


def test_logout_requires_a_csrf_token(client: TestClient) -> None:
    login(client)
    assert client.post(LOGOUT, headers=ORIGIN).status_code == 403
    assert client.get(ME).status_code == 200


def test_logout_rejects_a_wrong_origin_or_a_missing_origin(client: TestClient) -> None:
    csrf = login(client)["csrf_token"]
    bad = client.post(LOGOUT, headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf})
    missing = client.post(LOGOUT, headers={"X-CSRF-Token": csrf})
    assert bad.status_code == 403
    assert missing.status_code == 403
    assert client.get(ME).status_code == 200


def test_logout_with_valid_csrf_revokes_the_session_for_replay(client: TestClient) -> None:
    csrf = login(client)["csrf_token"]
    stolen_cookie = client.cookies[COOKIE]
    response = client.post(LOGOUT, headers={**ORIGIN, "X-CSRF-Token": csrf})
    assert response.status_code == 204
    client.cookies.clear()
    client.cookies.set(COOKIE, stolen_cookie, domain="testserver.local")
    assert client.get(ME).status_code == 401


def test_a_csrf_token_from_another_session_is_rejected(
    make_client: Callable[..., TestClient],
) -> None:
    alice, bob = make_client(), make_client()
    alice_csrf = login(alice)["csrf_token"]
    login(bob)
    response = bob.post(LOGOUT, headers={**ORIGIN, "X-CSRF-Token": alice_csrf})
    assert response.status_code == 403
    assert bob.get(ME).status_code == 200


def test_login_ignores_an_attacker_chosen_cookie(client: TestClient) -> None:
    client.cookies.set(COOKIE, "attacker-chosen-value", domain="testserver.local")
    login(client)
    assert client.cookies[COOKIE] != "attacker-chosen-value"


def test_login_rotates_and_revokes_the_previous_session(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client()
    subject = uuid4().hex
    login(client, subject)
    old_cookie = client.cookies[COOKIE]
    login(client, subject)
    assert client.cookies[COOKIE] != old_cookie
    replay = make_client()
    replay.cookies.set(COOKIE, old_cookie, domain="testserver.local")
    assert replay.get(ME).status_code == 401


def test_same_subject_maps_to_the_same_user_and_different_subjects_do_not(
    make_client: Callable[..., TestClient],
) -> None:
    subject = uuid4().hex
    first = login(make_client(), subject)["user_id"]
    again = login(make_client(), subject)["user_id"]
    other = login(make_client())["user_id"]
    assert first == again
    assert first != other


def test_each_user_only_sees_their_own_identity(
    make_client: Callable[..., TestClient],
) -> None:
    alice, bob = make_client(), make_client()
    alice_id, bob_id = login(alice)["user_id"], login(bob)["user_id"]
    assert alice.get(ME).json() == {"user_id": alice_id, "role": "user"}
    assert bob.get(ME).json() == {"user_id": bob_id, "role": "user"}


def test_idle_session_expires(client: TestClient, clock: FakeClock) -> None:
    login(client)
    clock.advance(minutes=31)
    assert client.get(ME).status_code == 401


def test_activity_slides_the_idle_window_but_not_past_the_absolute_limit(
    client: TestClient, clock: FakeClock
) -> None:
    login(client)
    for _ in range(35):  # 35 x 20 min = 11h40m, always inside the idle window
        clock.advance(minutes=20)
        assert client.get(ME).status_code == 200
    clock.advance(minutes=21)  # 12h01m after login: past the absolute limit
    assert client.get(ME).status_code == 401


def test_csrf_endpoint_returns_the_session_bound_token(client: TestClient) -> None:
    body = login(client)
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    assert response.json() == {"csrf_token": body["csrf_token"]}


def test_dev_login_does_not_exist_in_production(
    make_client: Callable[..., TestClient],
) -> None:
    production = make_client(environment="production", identity_provider="none")
    response = production.post(LOGIN, json={"subject": "x"}, headers=ORIGIN)
    assert response.status_code == 404


def test_dev_login_does_not_exist_when_no_provider_is_configured(
    make_client: Callable[..., TestClient],
) -> None:
    disabled = make_client(identity_provider="none")
    assert disabled.post(LOGIN, json={"subject": "x"}, headers=ORIGIN).status_code == 404


def test_login_rejects_invalid_subjects(client: TestClient) -> None:
    for payload in ({}, {"subject": ""}, {"subject": "x" * 201}, {"subject": 5}):
        assert client.post(LOGIN, json=payload, headers=ORIGIN).status_code == 422


def test_login_rejects_a_foreign_origin(client: TestClient) -> None:
    response = client.post(LOGIN, json={"subject": "x"}, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert COOKIE not in client.cookies


def test_audit_events_never_contain_tokens(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="alvo.audit"):
        body = login(client)
        raw_token = client.cookies[COOKIE]
        client.post(LOGOUT, headers={**ORIGIN, "X-CSRF-Token": body["csrf_token"]})
    audit = "\n".join(r.getMessage() for r in caplog.records if r.name == "alvo.audit")
    assert "login" in audit
    assert "logout" in audit
    assert body["user_id"] in audit
    assert raw_token not in audit
    assert body["csrf_token"] not in audit
