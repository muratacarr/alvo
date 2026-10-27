"""Static policy checks for the production Compose file."""

from pathlib import Path
from typing import Any

import yaml

COMPOSE = Path(__file__).resolve().parents[4] / "compose.prod.yaml"
SECRET_WORDS = ("password", "secret", "token")
EXPECTED_SERVICES = {"db", "api", "web", "cloudflared"}


def load() -> dict[str, Any]:
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def services() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = load()["services"]
    return result


def test_the_stack_has_exactly_the_expected_services() -> None:
    assert set(services()) == EXPECTED_SERVICES


def test_nothing_is_published_on_the_host() -> None:
    # The only way in is the outbound tunnel; Docker would bypass the host firewall for ports.
    for name, svc in services().items():
        assert "ports" not in svc, name
        assert "expose" not in svc, name


def test_the_database_and_api_are_only_on_internal_networks() -> None:
    compose = load()
    for name in ("db", "api"):
        networks = services()[name]["networks"]
        assert networks, name
        for network in networks:
            assert compose["networks"][network].get("internal") is True, (name, network)


def test_only_the_web_server_and_the_tunnel_can_reach_the_internet() -> None:
    compose = load()
    open_networks = {n for n, cfg in compose["networks"].items() if not (cfg or {}).get("internal")}
    on_open = {
        name for name, svc in services().items() if open_networks & set(svc.get("networks", []))
    }
    assert on_open == {"web", "cloudflared"}


def test_the_tunnel_does_not_share_a_network_with_the_api() -> None:
    assert not set(services()["cloudflared"]["networks"]) & set(services()["api"]["networks"])


def test_images_are_pinned_by_digest_and_never_built_on_the_host() -> None:
    for name, svc in services().items():
        assert "build" not in svc, name
        image = svc["image"]
        assert not image.endswith(":latest"), name
        if name in {"db", "cloudflared"}:
            assert "@sha256:" in image, name
        else:
            # The approved digest comes from the release manifest and must be supplied.
            assert "@${ALVO_" in image and ":?" in image, name


def test_every_service_is_hardened() -> None:
    for name, svc in services().items():
        assert svc.get("read_only") is True, name
        assert svc.get("cap_drop") == ["ALL"], name
        assert "no-new-privileges:true" in svc.get("security_opt", []), name
        assert "mem_limit" in svc, name
        assert "pids_limit" in svc, name
        assert "healthcheck" in svc, name
        assert svc.get("restart") == "unless-stopped", name
        assert "max-size" in svc["logging"]["options"], name


def test_no_service_is_privileged_or_touches_the_host() -> None:
    for name, svc in services().items():
        assert not svc.get("privileged"), name
        assert svc.get("network_mode") != "host", name
        assert svc.get("pid") != "host", name
        assert not svc.get("cap_add"), name
        for volume in svc.get("volumes", []):
            assert "docker.sock" not in str(volume), name
            assert not str(volume).startswith("/"), (name, volume)  # named volumes only


def test_every_container_runs_as_a_non_root_user() -> None:
    for name, svc in services().items():
        user = str(svc.get("user", ""))
        assert user.split(":")[0] not in {"", "root", "0"}, name


def test_production_settings_and_no_development_login() -> None:
    environment = services()["api"]["environment"]
    assert environment["ALVO_ENVIRONMENT"] == "production"
    assert environment["ALVO_IDENTITY_PROVIDER"] != "mock"
    assert environment["ALVO_PUBLIC_ORIGIN"].startswith("${ALVO_PUBLIC_ORIGIN:?")
    assert "VITE_DEV_LOGIN" not in COMPOSE.read_text(encoding="utf-8")


def test_secrets_are_root_owned_files_outside_the_checkout() -> None:
    declared = load()["secrets"]
    assert set(declared) == {
        "db_password",
        "alvo_database_url",
        "alvo_session_secret",
        "tunnel_token",
    }
    for secret in declared.values():
        assert str(secret["file"]).startswith("/etc/alvo/secrets/")


def test_no_credentials_in_environment_values_or_commands() -> None:
    for name, svc in services().items():
        for key, value in svc.get("environment", {}).items():
            if any(word in key.lower() for word in SECRET_WORDS):
                assert key.endswith("_FILE"), (name, key)
            assert "://" not in str(value) or "@" not in str(value), (name, key)
    command = " ".join(services()["cloudflared"]["command"])
    assert "--token-file" in command
    assert "--token " not in f"{command} "


def test_every_secret_a_service_uses_is_declared() -> None:
    declared = set(load()["secrets"])
    for name, svc in services().items():
        assert set(svc.get("secrets", [])) <= declared, name


def test_the_api_trusts_forwarded_for_only_because_it_is_unreachable_except_through_nginx() -> None:
    api = services()["api"]
    assert api["environment"]["ALVO_TRUST_FORWARDED_FOR"] == "true"
    assert "ports" not in api
    assert not any(not load()["networks"][n].get("internal") for n in api["networks"])
