"""The web server configuration must keep the browser-side security guarantees."""

import re
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[4] / "apps" / "web"
CONF = (WEB_DIR / "nginx.conf").read_text(encoding="utf-8")
HEADERS = (WEB_DIR / "security-headers.conf").read_text(encoding="utf-8")


def csp() -> str:
    match = re.search(r'Content-Security-Policy "([^"]+)"', HEADERS)
    assert match
    return match.group(1)


def test_server_version_is_hidden_and_listing_is_off() -> None:
    assert "server_tokens off;" in CONF
    assert "autoindex on" not in CONF


def directives() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for part in csp().split(";"):
        name, *values = part.split()
        result[name] = values
    return result


def test_scripts_are_strictly_limited_to_our_own_files() -> None:
    # The part of the policy that stops injected JavaScript. It must never be relaxed.
    policy = directives()
    assert policy["script-src"] == ["'self'"]
    assert policy["default-src"] == ["'self'"]
    assert "'unsafe-eval'" not in csp()


def test_inline_styles_are_allowed_only_because_ant_design_injects_them_at_runtime() -> None:
    # Documented trade-off (ADR 0008): CSS-in-JS needs inline styles; scripts stay strict.
    policy = directives()
    assert policy["style-src"] == ["'self'", "'unsafe-inline'"]
    for name, values in policy.items():
        if name != "style-src":
            assert "'unsafe-inline'" not in values, name


def test_the_csp_allows_no_other_origins_and_locks_down_framing_and_plugins() -> None:
    policy = directives()
    assert "http:" not in csp() and "*" not in csp()
    assert policy["frame-ancestors"] == ["'none'"]
    assert policy["object-src"] == ["'none'"]
    assert policy["base-uri"] == ["'none'"]
    assert policy["connect-src"] == ["'self'"]


def test_the_baseline_security_headers_are_present() -> None:
    for header in (
        "X-Content-Type-Options",
        "Referrer-Policy",
        "X-Frame-Options",
        "Permissions-Policy",
        "Cross-Origin-Opener-Policy",
    ):
        assert header in HEADERS


def test_every_location_that_adds_headers_also_includes_the_shared_snippet() -> None:
    # nginx discards inherited add_header lines once a location sets its own.
    blocks = re.split(r"\n    location ", CONF)[1:]
    for block in blocks:
        if "add_header" in block and "docs|redoc" not in block:
            assert "security-headers.conf" in block, block.splitlines()[0]


def test_only_the_api_docs_location_relaxes_the_csp_and_only_for_known_paths() -> None:
    relaxed = [b for b in re.split(r"\n    location ", CONF)[1:] if "unsafe-inline" in b]
    assert len(relaxed) == 1
    assert "docs|redoc|openapi" in relaxed[0]


def test_the_api_is_reached_through_the_same_origin() -> None:
    assert "location /api/" in CONF
    assert "proxy_pass $api_upstream" in CONF


def test_the_service_worker_and_shell_are_never_cached_blindly() -> None:
    assert r"sw\.js" in CONF and 'Cache-Control "no-cache"' in CONF
    assert "immutable" in CONF  # only for hashed /assets/
    assets, shell = CONF.split("location /assets/")[1].split("location ~ ^/(index")
    assert "immutable" in assets and "immutable" not in shell


def test_request_bodies_are_bounded() -> None:
    assert re.search(r"client_max_body_size\s+\d+m;", CONF)


def test_the_web_app_manifest_is_served_with_its_proper_media_type() -> None:
    assert "application/manifest+json" in CONF and "webmanifest" in CONF


def test_mime_types_file_is_not_nested_inside_a_types_block() -> None:
    # /etc/nginx/mime.types already contains its own `types { ... }`; nesting it breaks nginx.
    assert not re.search(r"types\s*\{[^}]*include\s+/etc/nginx/mime\.types", CONF)
    assert re.search(r"^\s*include\s+/etc/nginx/mime\.types;", CONF, re.MULTILINE)


def test_the_api_is_rate_limited_per_client_with_a_json_429() -> None:
    assert "limit_req_zone $binary_remote_addr zone=api_general" in CONF
    assert "limit_req_status 429;" in CONF
    assert 'return 429 \'{"error":"rate_limited"}\'' in CONF
    for block in re.split(r"\n    location ", CONF)[1:]:
        if block.startswith(("/api/ ", "/api/v1/auth/ ")):
            assert "limit_req zone=api_general" in block, block.splitlines()[0]


def test_unsafe_auth_requests_have_a_stricter_limit_than_the_rest() -> None:
    auth = next(b for b in re.split(r"\n    location ", CONF) if b.startswith("/api/v1/auth/ "))
    assert "limit_req zone=auth_write" in auth
    assert re.search(r"zone=auth_write:\w+\s+rate=\d+r/m", CONF)
    # Only POST is counted; reads (session checks) must not burn the sign-in allowance.
    assert re.search(r'map \$request_method \$auth_write_key \{\s+default ""', CONF)


def test_the_real_client_address_is_trusted_only_from_private_networks() -> None:
    assert "real_ip_header CF-Connecting-IP;" in CONF
    trusted = re.findall(r"set_real_ip_from\s+(\S+);", CONF)
    assert trusted and "0.0.0.0/0" not in trusted
    assert all(net.split("/")[0].startswith(("10.", "172.", "192.168.")) for net in trusted)


def test_forwarded_for_is_overwritten_not_appended() -> None:
    assert "$proxy_add_x_forwarded_for" not in CONF
    assert CONF.count("proxy_set_header X-Forwarded-For $remote_addr;") >= 2
