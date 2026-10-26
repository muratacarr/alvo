"""Static policy checks for the API Dockerfile."""

import re
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[2]
DOCKERFILE = API_DIR / "Dockerfile"
DOCKERIGNORE = API_DIR / ".dockerignore"
SECRET_NAME = re.compile(r"secret|passw|token|api_?key|private", re.IGNORECASE)


def lines() -> list[str]:
    return [ln.strip() for ln in DOCKERFILE.read_text(encoding="utf-8").splitlines()]


def test_every_base_image_is_pinned_by_digest() -> None:
    froms = [ln for ln in lines() if ln.upper().startswith("FROM ")]
    assert froms
    for ln in froms:
        image = ln.split()[1]
        assert re.search(r"@sha256:[0-9a-f]{64}$", image), ln


def test_runtime_user_is_not_root() -> None:
    users = [ln for ln in lines() if ln.upper().startswith("USER ")]
    assert users
    last = users[-1].split(maxsplit=1)[1]
    assert last.split(":")[0] not in {"root", "0"}


def test_no_secret_named_arg_or_env() -> None:
    for ln in lines():
        if ln.upper().startswith(("ARG ", "ENV ")):
            assert not SECRET_NAME.search(ln), ln


def test_no_latest_tags_and_no_curl_pipe_shell() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert ":latest" not in text
    assert not re.search(r"(curl|wget)[^\n|]*\|\s*(ba)?sh", text)


def test_image_declares_a_healthcheck() -> None:
    assert any(ln.upper().startswith("HEALTHCHECK") for ln in lines())


def test_build_context_excludes_secrets_and_local_state() -> None:
    entries = {e.strip().rstrip("/") for e in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()}
    for required in (".venv", ".env*", "secrets", ".git"):
        assert required in entries, required


def test_runtime_image_ships_no_package_installer() -> None:
    runtime = DOCKERFILE.read_text(encoding="utf-8").split("AS runtime", 1)[1]
    assert "pip uninstall" in runtime
