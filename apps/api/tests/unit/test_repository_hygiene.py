"""Public-repo hygiene: the example env file must never boot the application."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from alvo.shared.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[4]
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def test_env_example_exists() -> None:
    assert ENV_EXAMPLE.is_file()


def test_env_example_alone_does_not_boot_the_application() -> None:
    values = parse_env(ENV_EXAMPLE)
    kwargs = {k.removeprefix("ALVO_").lower(): v for k, v in values.items()}
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def test_env_example_declares_every_required_setting() -> None:
    values = parse_env(ENV_EXAMPLE)
    assert {"ALVO_ENVIRONMENT", "ALVO_DATABASE_URL", "ALVO_SESSION_SECRET"} <= values.keys()
