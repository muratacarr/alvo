"""Application settings with fail-closed secret validation.

Secrets are required, never defaulted, and rejected when they look like
placeholders or are too weak. This applies in every environment so that
`.env.example` can never boot a working instance.
"""

import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER = re.compile(r"change_?me|your_|placeholder|example|todo|xxx", re.IGNORECASE)
_MIN_SESSION_SECRET_LENGTH = 32
_MIN_DB_PASSWORD_LENGTH = 16
_MIN_DISTINCT_CHARS = 10
# Docker/Compose mount secrets as files here; absent on a developer machine.
_RUNTIME_SECRETS_DIR = Path("/run/secrets")


def _reject_placeholder(value: str, label: str) -> None:
    if _PLACEHOLDER.search(value):
        raise ValueError(f"{label} looks like a placeholder")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ALVO_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
        secrets_dir=_RUNTIME_SECRETS_DIR if _RUNTIME_SECRETS_DIR.is_dir() else None,
    )

    environment: Literal["development", "test", "production"]
    database_url: SecretStr
    session_secret: SecretStr
    # Exact origin the PWA is served from; unsafe requests must carry it in `Origin`.
    public_origin: str = "http://localhost:8000"
    # "mock" exposes a development-only login route; it is rejected in production.
    identity_provider: Literal["none", "mock"] = "none"
    session_idle_minutes: int = 30
    session_absolute_minutes: int = 720

    @field_validator("session_secret")
    @classmethod
    def _validate_session_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        _reject_placeholder(raw, "session_secret")
        if len(raw) < _MIN_SESSION_SECRET_LENGTH:
            raise ValueError("session_secret is too short")
        if len(set(raw)) < _MIN_DISTINCT_CHARS:
            raise ValueError("session_secret has too little entropy")
        return value

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        try:
            password = urlsplit(raw).password
        except ValueError as exc:
            raise ValueError("database_url is malformed") from exc
        if not password:
            raise ValueError("database_url must include a password")
        _reject_placeholder(password, "database password")
        if len(password) < _MIN_DB_PASSWORD_LENGTH:
            raise ValueError("database password is too short")
        return value

    @field_validator("public_origin")
    @classmethod
    def _validate_public_origin(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.netloc or parts.path not in {"", "/"}:
            raise ValueError("public_origin must be an origin like https://host[:port]")
        return f"{parts.scheme}://{parts.netloc}"

    @model_validator(mode="after")
    def _validate_environment_rules(self) -> "Settings":
        if not 0 < self.session_idle_minutes <= self.session_absolute_minutes:
            raise ValueError("session lifetimes must satisfy 0 < idle <= absolute")
        if self.environment == "production":
            if not self.public_origin.startswith("https://"):
                raise ValueError("public_origin must use https in production")
            if self.identity_provider == "mock":
                raise ValueError("the mock identity provider is forbidden in production")
        return self
