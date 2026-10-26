import secrets
from collections.abc import Callable
from typing import Any

import pytest

from alvo.shared.config import Settings

SettingsFactory = Callable[..., Settings]


@pytest.fixture
def settings_factory() -> SettingsFactory:
    """Build valid Settings with per-run random secrets (no secret literals in the repo)."""

    def make(**overrides: str) -> Settings:
        values: dict[str, Any] = {
            "environment": "test",
            "database_url": f"postgresql+psycopg://alvo_app:{secrets.token_urlsafe(24)}@db:5432/alvo",
            "session_secret": secrets.token_urlsafe(48),
            "public_origin": "https://testserver",
            "identity_provider": "mock",
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)

    return make
