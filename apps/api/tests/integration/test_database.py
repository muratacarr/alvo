import secrets
import time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alvo.main import create_app
from tests.conftest import SettingsFactory

API_DIR = Path(__file__).resolve().parents[2]


def test_ready_is_200_against_a_real_database(
    database_url: str, settings_factory: SettingsFactory
) -> None:
    app = create_app(settings_factory(database_url=database_url))
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 200


def test_ready_is_503_quickly_when_the_database_is_unreachable(
    settings_factory: SettingsFactory,
) -> None:
    unreachable = f"postgresql+psycopg://alvo:{secrets.token_urlsafe(24)}@127.0.0.1:1/alvo"
    app = create_app(settings_factory(database_url=unreachable))
    started = time.monotonic()
    response = TestClient(app, raise_server_exceptions=False).get("/health/ready")
    assert time.monotonic() - started < 10
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "127.0.0.1" not in response.text


def test_migrations_upgrade_and_downgrade_cleanly(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALVO_ENVIRONMENT", "test")
    monkeypatch.setenv("ALVO_DATABASE_URL", database_url)
    monkeypatch.setenv("ALVO_SESSION_SECRET", secrets.token_urlsafe(48))
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine.dispose()
