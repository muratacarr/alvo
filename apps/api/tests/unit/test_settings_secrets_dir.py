"""Docker/Compose secrets are mounted as files; Settings must read them."""

import secrets
from pathlib import Path

from alvo.shared.config import Settings


def test_reads_secrets_from_mounted_files(tmp_path: Path) -> None:
    session_secret = secrets.token_urlsafe(48)
    database_url = f"postgresql+psycopg://alvo_app:{secrets.token_urlsafe(24)}@db:5432/alvo"
    (tmp_path / "alvo_session_secret").write_text(session_secret, encoding="utf-8")
    (tmp_path / "alvo_database_url").write_text(database_url + "\n", encoding="utf-8")

    settings = Settings(_env_file=None, _secrets_dir=tmp_path, environment="development")

    assert settings.session_secret.get_secret_value() == session_secret
    assert settings.database_url.get_secret_value() == database_url
