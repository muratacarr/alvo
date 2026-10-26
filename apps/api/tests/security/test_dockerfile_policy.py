"""Static policy checks for every Dockerfile in the repository."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
API_DIR = REPO_ROOT / "apps" / "api"
WEB_DIR = REPO_ROOT / "apps" / "web"
CONTEXTS = [pytest.param(API_DIR, id="api"), pytest.param(WEB_DIR, id="web")]
SECRET_NAME = re.compile(r"secret|passw|token|api_?key|private", re.IGNORECASE)


def lines(context: Path) -> list[str]:
    text = (context / "Dockerfile").read_text(encoding="utf-8")
    return [ln.strip() for ln in text.splitlines()]


@pytest.mark.parametrize("context", CONTEXTS)
def test_every_base_image_is_pinned_by_digest(context: Path) -> None:
    froms = [ln for ln in lines(context) if ln.upper().startswith("FROM ")]
    assert froms
    for ln in froms:
        image = ln.split()[1]
        assert re.search(r"@sha256:[0-9a-f]{64}$", image), ln


@pytest.mark.parametrize("context", CONTEXTS)
def test_runtime_user_is_not_root(context: Path) -> None:
    users = [ln for ln in lines(context) if ln.upper().startswith("USER ")]
    assert users
    last = users[-1].split(maxsplit=1)[1]
    assert last.split(":")[0] not in {"root", "0"}


@pytest.mark.parametrize("context", CONTEXTS)
def test_no_secret_named_arg_or_env(context: Path) -> None:
    for ln in lines(context):
        if ln.upper().startswith(("ARG ", "ENV ")):
            assert not SECRET_NAME.search(ln), ln


@pytest.mark.parametrize("context", CONTEXTS)
def test_no_latest_tags_and_no_curl_pipe_shell(context: Path) -> None:
    text = (context / "Dockerfile").read_text(encoding="utf-8")
    assert ":latest" not in text
    assert not re.search(r"(curl|wget)[^\n|]*\|\s*(ba)?sh", text)


@pytest.mark.parametrize("context", CONTEXTS)
def test_image_declares_a_healthcheck(context: Path) -> None:
    assert any(ln.upper().startswith("HEALTHCHECK") for ln in lines(context))


@pytest.mark.parametrize(
    ("context", "required"),
    [
        pytest.param(API_DIR, (".venv", ".env*", "secrets", ".git"), id="api"),
        pytest.param(WEB_DIR, ("node_modules", ".env*", "secrets", ".git"), id="web"),
    ],
)
def test_build_context_excludes_secrets_and_local_state(
    context: Path, required: tuple[str, ...]
) -> None:
    ignore = (context / ".dockerignore").read_text(encoding="utf-8").splitlines()
    entries = {e.strip().rstrip("/") for e in ignore}
    for item in required:
        assert item in entries, item


def test_python_runtime_image_ships_no_package_installer() -> None:
    runtime = (API_DIR / "Dockerfile").read_text(encoding="utf-8").split("AS runtime", 1)[1]
    assert "pip uninstall" in runtime


def test_web_runtime_image_contains_only_the_built_site() -> None:
    runtime = (WEB_DIR / "Dockerfile").read_text(encoding="utf-8").split("AS runtime", 1)[1]
    assert "COPY --from=build /app/dist" in runtime
    assert "node_modules" not in runtime and "npm " not in runtime


def test_web_dependencies_are_installed_from_the_lockfile_without_scripts() -> None:
    text = (WEB_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "npm ci" in text and "npm install" not in text
    assert "ignore-scripts=true" in (WEB_DIR / ".npmrc").read_text(encoding="utf-8")


def test_web_release_default_hides_the_development_sign_in() -> None:
    text = (WEB_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "ARG VITE_DEV_LOGIN=false" in text


def test_web_runtime_image_drops_curl_and_unused_nginx_modules() -> None:
    # They are never loaded and only drag in image, font and network libraries to patch.
    runtime = (WEB_DIR / "Dockerfile").read_text(encoding="utf-8").split("AS runtime", 1)[1]
    assert "apk del" in runtime
    for package in (
        "curl",
        "nginx-module-geoip",
        "nginx-module-image-filter",
        "nginx-module-njs",
        "nginx-module-xslt",
    ):
        assert package in runtime, package
