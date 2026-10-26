import os
import secrets
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer

# Same digest as compose.yaml so tests exercise the version we deploy.
POSTGRES_IMAGE = (
    "postgres:18-trixie@sha256:edb0c08dc33befd0262ab3b5cf1c4f3f8cfd8b09e88c05b45adee29d6761ddb6"
)


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    # Locally these tests skip without Docker; in CI a missing Docker must fail, not skip.
    if shutil.which("docker") is None and not os.environ.get("CI"):
        pytest.skip("docker not available")
    with PostgresContainer(
        POSTGRES_IMAGE,
        username="alvo_test",
        password=secrets.token_urlsafe(24),
        dbname="alvo_test",
        driver="psycopg",
    ) as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def migrated_database_url(database_url: str) -> str:
    """The shared test database with all migrations applied (once per session)."""
    api_dir = Path(__file__).resolve().parents[2]
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("ALVO_ENVIRONMENT", "test")
        patch.setenv("ALVO_DATABASE_URL", database_url)
        patch.setenv("ALVO_SESSION_SECRET", secrets.token_urlsafe(48))
        config = Config(str(api_dir / "alembic.ini"))
        config.set_main_option("script_location", str(api_dir / "alembic"))
        command.upgrade(config, "head")
    return database_url


class FakeClock:
    """Controllable time source injected into the application under test."""

    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs: float) -> None:
        self.current += timedelta(**kwargs)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
