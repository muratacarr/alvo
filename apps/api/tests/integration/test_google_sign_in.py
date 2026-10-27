"""Invite-only Google sign-in through the real routes, with a fake Google and a real database."""

import secrets
from datetime import timedelta
from urllib.parse import parse_qsl, urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from alvo.cli import main as cli_main
from alvo.identity.infrastructure import SqlIdentityStore
from alvo.main import create_app
from tests.conftest import SettingsFactory
from tests.integration.conftest import FakeClock
from tests.oidc_support import FakeGoogle

START = "/api/v1/auth/google/start"
CALLBACK = "/api/v1/auth/google/callback"


class Harness:
    def __init__(self, url: str, settings_factory: SettingsFactory) -> None:
        self.url = url
        self.google = FakeGoogle()
        self.clock = FakeClock()
        self.factory = sessionmaker(create_engine(url))
        settings = settings_factory(database_url=url, identity_provider="none")
        app = create_app(
            settings, readiness_probe=lambda: True, clock=self.clock, oidc=self.google.client()
        )
        self.client = TestClient(app, base_url="https://testserver")
        self.email = f"{uuid4().hex}@example.com"
        self.google.email = self.email
        self.google.subject = f"sub-{uuid4().hex}"

    def invite(self, role: str = "user", days: int = 14, email: str | None = None) -> None:
        with self.factory() as db:
            SqlIdentityStore(db).upsert_invite(
                email or self.email,
                "admin" if role == "admin" else "user",
                self.clock(),
                self.clock() + timedelta(days=days),
            )
            db.commit()

    def start(self) -> tuple[str, str]:
        response = self.client.get(START, follow_redirects=False)
        assert response.status_code == 302
        query = dict(parse_qsl(urlsplit(response.headers["location"]).query))
        self.google.nonce = query["nonce"]
        return query["state"], query["nonce"]

    def finish(self, state: str, code: str = "auth-code") -> tuple[str, bool]:
        response = self.client.get(
            CALLBACK, params={"code": code, "state": state}, follow_redirects=False
        )
        assert response.status_code == 302
        outcome = dict(parse_qsl(urlsplit(response.headers["location"]).query))["signin"]
        has_session = any(
            "__Host-alvo_session=" in value and "Max-Age=0" not in value
            for value in response.headers.get_list("set-cookie")
        )
        return outcome, has_session

    def sign_in(self) -> tuple[str, bool]:
        state, _ = self.start()
        return self.finish(state)

    def role_of_subject(self) -> str | None:
        with self.factory() as db:
            return db.execute(
                text("SELECT role FROM users WHERE provider = 'google' AND subject = :s"),
                {"s": self.google.subject},
            ).scalar_one_or_none()

    def invite_count(self) -> int:
        with self.factory() as db:
            return int(
                db.execute(
                    text("SELECT count(*) FROM sign_in_invites WHERE email = :e"),
                    {"e": self.email},
                ).scalar_one()
            )


@pytest.fixture
def harness(migrated_database_url: str, settings_factory: SettingsFactory) -> Harness:
    return Harness(migrated_database_url, settings_factory)


def test_start_redirects_to_google_with_a_signed_http_only_cookie(harness: Harness) -> None:
    response = harness.client.get(START, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("https://accounts.google.com/")
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Host-alvo_oidc=")
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    assert "Path=/" in cookie


def test_an_invited_person_signs_in_and_the_invite_is_used_up(harness: Harness) -> None:
    harness.invite()
    assert harness.sign_in() == ("ok", True)
    assert harness.role_of_subject() == "user"
    assert harness.invite_count() == 0
    me = harness.client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["role"] == "user"


def test_an_admin_invitation_creates_an_admin(harness: Harness) -> None:
    harness.invite(role="admin")
    assert harness.sign_in() == ("ok", True)
    assert harness.role_of_subject() == "admin"


def test_a_returning_user_signs_in_without_a_new_invite(harness: Harness) -> None:
    harness.invite()
    assert harness.sign_in()[0] == "ok"
    harness.client.cookies.clear()
    assert harness.sign_in() == ("ok", True)


def test_someone_who_was_not_invited_gets_no_account_and_no_session(harness: Harness) -> None:
    assert harness.sign_in() == ("not_invited", False)
    assert harness.role_of_subject() is None
    assert harness.client.get("/api/v1/auth/me").status_code == 401


def test_an_invite_cannot_be_used_by_a_second_google_account(harness: Harness) -> None:
    harness.invite()
    assert harness.sign_in()[0] == "ok"
    harness.client.cookies.clear()
    harness.google.subject = f"sub-{uuid4().hex}"  # same email, different account
    assert harness.sign_in() == ("not_invited", False)


def test_an_expired_invite_is_refused(harness: Harness) -> None:
    harness.invite(days=1)
    harness.clock.advance(days=2)
    assert harness.sign_in() == ("not_invited", False)
    assert harness.role_of_subject() is None


def test_an_unverified_email_never_matches_an_invite(harness: Harness) -> None:
    harness.invite()
    harness.google.email_verified = False
    assert harness.sign_in() == ("failed", False)
    assert harness.invite_count() == 1


def test_the_invite_matches_the_email_case_insensitively(harness: Harness) -> None:
    harness.invite()
    harness.google.email = harness.email.upper()
    assert harness.sign_in() == ("ok", True)


def test_a_wrong_state_is_refused_and_google_is_never_contacted(harness: Harness) -> None:
    harness.invite()
    harness.start()
    assert harness.finish("not-the-state-we-issued") == ("failed", False)
    assert harness.google.calls == []
    assert harness.invite_count() == 1


def test_a_callback_without_the_flow_cookie_is_refused(harness: Harness) -> None:
    harness.invite()
    state, _ = harness.start()
    harness.client.cookies.clear()
    assert harness.finish(state) == ("failed", False)


def test_a_callback_cannot_be_replayed(harness: Harness) -> None:
    harness.invite()
    state, _ = harness.start()
    assert harness.finish(state)[0] == "ok"
    harness.client.cookies.clear()
    assert harness.finish(state) == ("failed", False)


def test_a_slow_flow_expires(harness: Harness) -> None:
    harness.invite()
    state, _ = harness.start()
    harness.clock.advance(minutes=11)
    assert harness.finish(state) == ("failed", False)


def test_a_cookie_forged_with_another_key_is_refused(harness: Harness) -> None:
    from alvo.identity.security import seal_flow_state

    harness.invite()
    state, nonce = harness.start()
    forged = seal_flow_state(
        secrets.token_urlsafe(40), {"s": state, "n": nonce, "v": "v" * 64, "e": 9**10}
    )
    harness.client.cookies.clear()
    harness.client.cookies.set("__Host-alvo_oidc", forged)
    assert harness.finish(state) == ("failed", False)


def test_a_missing_code_such_as_access_denied_fails_quietly(harness: Harness) -> None:
    state, _ = harness.start()
    response = harness.client.get(CALLBACK, params={"state": state}, follow_redirects=False)
    assert response.status_code == 302
    assert dict(parse_qsl(urlsplit(response.headers["location"]).query))["signin"] == "failed"


def test_a_google_outage_fails_quietly_without_leaking_details(harness: Harness) -> None:
    harness.invite()
    harness.google.fail_token_endpoint = True
    state, _ = harness.start()
    response = harness.client.get(
        CALLBACK, params={"code": "c", "state": state}, follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers["location"].endswith("/?signin=failed")
    assert "provider" not in response.text


def test_signing_in_replaces_a_session_that_was_already_presented(harness: Harness) -> None:
    harness.invite()
    assert harness.sign_in()[0] == "ok"
    old = harness.client.cookies.get("__Host-alvo_session")
    assert old
    assert harness.sign_in() == ("ok", True)  # signs in again while still holding the old session
    assert harness.client.cookies.get("__Host-alvo_session") != old

    def status_with(token: str) -> int:
        probe = TestClient(harness.client.app, base_url="https://testserver")
        probe.cookies.set("__Host-alvo_session", token, domain="testserver.local")
        return probe.get("/api/v1/auth/me").status_code

    current = harness.client.cookies.get("__Host-alvo_session")
    assert current
    assert status_with(current) == 200  # control: this way of sending the cookie works
    assert status_with(old) == 401


def test_the_sign_in_routes_are_rate_limited_per_address(
    migrated_database_url: str, settings_factory: SettingsFactory
) -> None:
    settings = settings_factory(
        database_url=migrated_database_url,
        identity_provider="none",
        auth_attempts_per_minute="2",
        trust_forwarded_for="true",
    )
    app = create_app(settings, readiness_probe=lambda: True, oidc=FakeGoogle().client())
    client = TestClient(app, base_url="https://testserver")
    headers = {"X-Forwarded-For": f"198.51.100.{secrets.randbelow(200) + 1}"}
    codes = [
        client.get(START, headers=headers, follow_redirects=False).status_code for _ in range(3)
    ]
    assert codes == [302, 302, 429]


def test_google_routes_do_not_exist_unless_google_sign_in_is_configured(
    migrated_database_url: str, settings_factory: SettingsFactory
) -> None:
    settings = settings_factory(database_url=migrated_database_url, identity_provider="none")
    client = TestClient(
        create_app(settings, readiness_probe=lambda: True), base_url="https://testserver"
    )
    assert client.get(START, follow_redirects=False).status_code == 404


def test_cli_invite_and_revoke(migrated_database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALVO_ENVIRONMENT", "test")
    monkeypatch.setenv("ALVO_DATABASE_URL", migrated_database_url)
    monkeypatch.setenv("ALVO_SESSION_SECRET", secrets.token_urlsafe(48))
    email = f"  {uuid4().hex}@Example.com "
    stored = email.strip().lower()

    def row() -> tuple[str, str] | None:
        engine = create_engine(migrated_database_url)
        with engine.connect() as connection:
            found = connection.execute(
                text("SELECT email, role FROM sign_in_invites WHERE email = :e"), {"e": stored}
            ).first()
        engine.dispose()
        return (found[0], found[1]) if found else None

    assert cli_main(["invite", "--email", email]) == 0
    assert row() == (stored, "user")
    assert cli_main(["invite", "--email", email, "--admin"]) == 0  # re-inviting updates it
    assert row() == (stored, "admin")
    assert cli_main(["revoke-invite", "--email", email]) == 0
    assert row() is None
    assert cli_main(["revoke-invite", "--email", email]) == 1


@pytest.mark.parametrize("bad", ["not-an-email", "a@b", "x" * 300 + "@example.com", "a b@c.de"])
def test_cli_rejects_malformed_emails(bad: str) -> None:
    with pytest.raises(SystemExit):
        cli_main(["invite", "--email", bad])


@pytest.mark.parametrize("days", ["0", "91", "abc"])
def test_cli_rejects_unreasonable_invite_lifetimes(days: str) -> None:
    with pytest.raises(SystemExit):
        cli_main(["invite", "--email", "a@example.com", "--days", days])
