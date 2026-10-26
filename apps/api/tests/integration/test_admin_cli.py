"""The only way to create an admin is a host-side command, never a web request."""

import secrets
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from alvo.cli import main


@pytest.fixture
def cli_env(migrated_database_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("ALVO_ENVIRONMENT", "test")
    monkeypatch.setenv("ALVO_DATABASE_URL", migrated_database_url)
    monkeypatch.setenv("ALVO_SESSION_SECRET", secrets.token_urlsafe(48))
    return migrated_database_url


def role_of(url: str, provider: str, subject: str) -> str | None:
    engine = create_engine(url)
    with engine.connect() as connection:
        value = connection.execute(
            text("SELECT role FROM users WHERE provider = :p AND subject = :s"),
            {"p": provider, "s": subject},
        ).scalar_one_or_none()
    engine.dispose()
    return value


def test_create_admin_creates_the_user_with_the_admin_role(cli_env: str) -> None:
    subject = uuid4().hex
    assert main(["create-admin", "--provider", "mock", "--subject", subject]) == 0
    assert role_of(cli_env, "mock", subject) == "admin"


def test_create_admin_promotes_an_existing_user_and_is_idempotent(cli_env: str) -> None:
    subject = uuid4().hex
    engine = create_engine(cli_env)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, provider, subject, created_at, role) "
                "VALUES (:i, 'mock', :s, now(), 'user')"
            ),
            {"i": uuid4(), "s": subject},
        )
    engine.dispose()
    assert main(["create-admin", "--provider", "mock", "--subject", subject]) == 0
    assert main(["create-admin", "--provider", "mock", "--subject", subject]) == 0
    assert role_of(cli_env, "mock", subject) == "admin"


def test_revoke_admin_demotes_to_user(cli_env: str) -> None:
    subject = uuid4().hex
    main(["create-admin", "--provider", "mock", "--subject", subject])
    assert main(["revoke-admin", "--provider", "mock", "--subject", subject]) == 0
    assert role_of(cli_env, "mock", subject) == "user"


def test_revoke_admin_for_an_unknown_user_fails_without_creating_one(cli_env: str) -> None:
    subject = uuid4().hex
    assert main(["revoke-admin", "--provider", "mock", "--subject", subject]) == 1
    assert role_of(cli_env, "mock", subject) is None


def test_unknown_commands_and_missing_arguments_fail(cli_env: str) -> None:
    with pytest.raises(SystemExit):
        main(["create-admin"])
    with pytest.raises(SystemExit):
        main(["drop-database"])
