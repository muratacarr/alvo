"""Generate local development secrets for Docker Compose.

Writes random values into the given directory (default: <repo>/secrets, which is
gitignored). Existing files are never overwritten. Never run this for production:
production secrets are provisioned outside the repository.
"""

import secrets
import sys
from pathlib import Path

DB_USER = "alvo_app"
DB_NAME = "alvo"
DB_HOST = "db"


def _write_new(path: Path, value: str) -> None:
    if path.exists():
        return
    path.write_text(value, encoding="utf-8")
    # Bind-mounted secrets keep host permissions and the container runs as another uid,
    # so the file must be world-readable; the directory below stays private to the owner.
    path.chmod(0o644)


def write_dev_secrets(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    password_file = directory / "db_password"
    _write_new(password_file, secrets.token_urlsafe(24))
    password = password_file.read_text(encoding="utf-8").strip()
    _write_new(
        directory / "alvo_database_url",
        f"postgresql+psycopg://{DB_USER}:{password}@{DB_HOST}:5432/{DB_NAME}",
    )
    _write_new(directory / "alvo_session_secret", secrets.token_urlsafe(48))


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3] / "secrets"
    )
    write_dev_secrets(target)
    print(f"Development secrets are in {target} (not printed).")
