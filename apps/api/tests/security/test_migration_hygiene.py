"""Migrations may change schema only: no secrets, no environment access, no external calls."""

import re
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[2]
VERSIONS = API_DIR / "alembic" / "versions"
FORBIDDEN_IMPORTS = re.compile(
    r"^\s*(import|from)\s+(os|secrets|subprocess|requests|httpx|socket)\b", re.MULTILINE
)
SECRETISH_LITERAL = re.compile(
    r"(password|passwd|secret|token|api_?key)\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE
)


def revision_files() -> list[Path]:
    return sorted(VERSIONS.glob("*.py"))


def test_there_is_a_baseline_revision() -> None:
    assert revision_files()


def test_revisions_do_not_touch_environment_or_network() -> None:
    for path in revision_files():
        assert not FORBIDDEN_IMPORTS.search(path.read_text(encoding="utf-8")), path.name


def test_revisions_contain_no_credential_literals() -> None:
    for path in revision_files():
        assert not SECRETISH_LITERAL.search(path.read_text(encoding="utf-8")), path.name


def test_alembic_ini_holds_no_connection_url() -> None:
    ini = (API_DIR / "alembic.ini").read_text(encoding="utf-8")
    assert not re.search(r"^\s*sqlalchemy\.url\s*=\s*\S+", ini, re.MULTILINE)
