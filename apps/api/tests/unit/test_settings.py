import secrets

import pytest
from pydantic import ValidationError

from alvo.shared.config import Settings

# Generated per run so no secret-looking literal lives in the repository.
STRONG_SECRET = secrets.token_urlsafe(48)
STRONG_DB_PASSWORD = secrets.token_urlsafe(24)
STRONG_DB_URL = f"postgresql://alvo_app:{STRONG_DB_PASSWORD}@db:5432/alvo"


def make(**overrides: str) -> Settings:
    values = {
        "environment": "production",
        "database_url": STRONG_DB_URL,
        "session_secret": STRONG_SECRET,
        "public_origin": "https://alvo.example.org",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ALVO_ENVIRONMENT", "ALVO_DATABASE_URL", "ALVO_SESSION_SECRET"):
        monkeypatch.delenv(name, raising=False)


def test_accepts_strong_secrets() -> None:
    settings = make()
    assert settings.environment == "production"


@pytest.mark.parametrize(
    "placeholder",
    ["CHANGE_ME", "changeme-changeme-changeme-changeme", "YOUR_SESSION_SECRET_GOES_HERE_PLEASE"],
)
def test_rejects_placeholder_session_secret(placeholder: str) -> None:
    with pytest.raises(ValidationError):
        make(session_secret=placeholder)


def test_rejects_short_session_secret() -> None:
    with pytest.raises(ValidationError):
        make(session_secret="too-short-value")


def test_rejects_low_entropy_session_secret() -> None:
    with pytest.raises(ValidationError):
        make(session_secret="a" * 48)


def test_rejects_placeholder_database_password() -> None:
    with pytest.raises(ValidationError):
        make(database_url="postgresql://alvo_app:CHANGE_ME@db:5432/alvo")


def test_rejects_database_url_without_password() -> None:
    with pytest.raises(ValidationError):
        make(database_url="postgresql://alvo_app@db:5432/alvo")


def test_rejects_unknown_environment() -> None:
    with pytest.raises(ValidationError):
        make(environment="staging-ish")


def test_missing_secrets_fail_closed() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_secrets_are_not_in_repr_or_str() -> None:
    settings = make()
    rendered = repr(settings) + str(settings)
    assert STRONG_SECRET not in rendered
    assert STRONG_DB_PASSWORD not in rendered


def test_validation_errors_do_not_echo_secret_values() -> None:
    weak = "too-short-value"
    with pytest.raises(ValidationError) as excinfo:
        make(session_secret=weak)
    assert weak not in str(excinfo.value)


def test_reads_prefixed_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALVO_ENVIRONMENT", "development")
    monkeypatch.setenv("ALVO_DATABASE_URL", STRONG_DB_URL)
    monkeypatch.setenv("ALVO_SESSION_SECRET", STRONG_SECRET)
    settings = Settings(_env_file=None)
    assert settings.environment == "development"


def test_production_requires_an_https_public_origin() -> None:
    with pytest.raises(ValidationError):
        make(public_origin="http://alvo.example.org")


def test_non_production_may_use_http_localhost() -> None:
    assert make(environment="development", public_origin="http://localhost:8000")


def test_mock_identity_provider_is_forbidden_in_production() -> None:
    with pytest.raises(ValidationError):
        make(identity_provider="mock")


def test_mock_identity_provider_is_allowed_outside_production() -> None:
    assert make(environment="development", identity_provider="mock")


def test_identity_provider_defaults_to_none() -> None:
    assert make().identity_provider == "none"


def test_session_lifetimes_must_be_positive_and_ordered() -> None:
    with pytest.raises(ValidationError):
        make(session_idle_minutes="0")
    with pytest.raises(ValidationError):
        make(session_idle_minutes="600", session_absolute_minutes="60")
