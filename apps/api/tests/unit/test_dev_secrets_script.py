import importlib.util
from pathlib import Path
from types import ModuleType

from alvo.shared.config import Settings

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "make_dev_secrets.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("make_dev_secrets", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_secrets_boot_the_application(tmp_path: Path) -> None:
    load_script().write_dev_secrets(tmp_path)
    settings = Settings(_env_file=None, _secrets_dir=tmp_path, environment="development")
    assert settings.environment == "development"


def test_database_password_is_shared_between_postgres_and_the_url(tmp_path: Path) -> None:
    load_script().write_dev_secrets(tmp_path)
    password = (tmp_path / "db_password").read_text(encoding="utf-8").strip()
    assert password in (tmp_path / "alvo_database_url").read_text(encoding="utf-8")


def test_existing_secrets_are_never_overwritten(tmp_path: Path) -> None:
    module = load_script()
    module.write_dev_secrets(tmp_path)
    before = (tmp_path / "alvo_session_secret").read_text(encoding="utf-8")
    module.write_dev_secrets(tmp_path)
    assert (tmp_path / "alvo_session_secret").read_text(encoding="utf-8") == before
