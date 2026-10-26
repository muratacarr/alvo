"""Static policy checks for the development Compose file."""

from pathlib import Path
from typing import Any

import yaml

COMPOSE = Path(__file__).resolve().parents[4] / "compose.yaml"
SECRET_WORDS = ("password", "secret", "token")


def load() -> dict[str, Any]:
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def services() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = load()["services"]
    return result


def test_project_is_named_alvo() -> None:
    assert load()["name"] == "alvo"


def test_database_publishes_no_host_port() -> None:
    assert "ports" not in services()["db"]


def test_database_is_only_on_internal_networks() -> None:
    compose = load()
    db_networks = services()["db"]["networks"]
    assert db_networks
    for name in db_networks:
        assert compose["networks"][name].get("internal") is True


def test_only_the_web_entrypoint_publishes_ports_and_only_on_loopback() -> None:
    for name, svc in services().items():
        for port in svc.get("ports", []):
            assert name == "web", name
            assert str(port).startswith("127.0.0.1:"), port
    assert services()["web"]["ports"]


def test_the_api_is_reachable_only_through_the_web_proxy() -> None:
    assert "ports" not in services()["api"]
    assert "web" not in services()["api"].get("depends_on", {})
    assert "api" in services()["web"]["depends_on"]


def test_the_public_origin_matches_the_published_web_port() -> None:
    origin = services()["api"]["environment"]["ALVO_PUBLIC_ORIGIN"]
    port = str(services()["web"]["ports"][0]).split(":")[1]
    assert origin == f"http://localhost:{port}"


def test_no_service_is_privileged_or_mounts_the_docker_socket() -> None:
    for name, svc in services().items():
        assert not svc.get("privileged"), name
        assert svc.get("network_mode") != "host", name
        assert svc.get("pid") != "host", name
        for volume in svc.get("volumes", []):
            assert "docker.sock" not in str(volume), name


def test_every_service_is_hardened() -> None:
    for name, svc in services().items():
        assert svc.get("read_only") is True, name
        assert svc.get("cap_drop") == ["ALL"], name
        assert "no-new-privileges:true" in svc.get("security_opt", []), name
        assert "mem_limit" in svc, name
        assert "healthcheck" in svc, name


def test_application_containers_run_as_non_root_users() -> None:
    for name in ("api", "web", "db"):
        user = str(services()[name].get("user", ""))
        assert user.split(":")[0] not in {"", "root", "0"}, name


def test_database_image_is_pinned_by_digest() -> None:
    image = services()["db"]["image"]
    assert "@sha256:" in image
    assert not image.endswith(":latest")


def test_no_credentials_in_environment_values() -> None:
    for name, svc in services().items():
        for key, value in svc.get("environment", {}).items():
            if any(word in key.lower() for word in SECRET_WORDS):
                assert key.endswith("_FILE"), (name, key)
            assert "://" not in str(value) or "@" not in str(value), (name, key)


def test_secrets_come_from_gitignored_files() -> None:
    declared = load()["secrets"]
    assert declared
    for secret in declared.values():
        assert str(secret["file"]).startswith("./secrets/")
