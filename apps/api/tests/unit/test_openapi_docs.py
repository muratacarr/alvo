"""The CSRF header must be visible in the API docs so Swagger UI can send it."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from alvo.main import create_app
from tests.conftest import SettingsFactory


def spec(settings_factory: SettingsFactory) -> dict[str, Any]:
    app = create_app(settings_factory(environment="development"), readiness_probe=lambda: True)
    body: dict[str, Any] = TestClient(app).get("/openapi.json").json()
    return body


def test_csrf_header_is_declared_as_a_security_scheme(settings_factory: SettingsFactory) -> None:
    schemes = spec(settings_factory)["components"]["securitySchemes"]
    csrf = next(s for s in schemes.values() if s.get("name") == "X-CSRF-Token")
    assert csrf["type"] == "apiKey"
    assert csrf["in"] == "header"


def test_state_changing_operations_require_the_csrf_scheme(
    settings_factory: SettingsFactory,
) -> None:
    paths = spec(settings_factory)["paths"]
    logout = paths["/api/v1/auth/logout"]["post"]
    grant = paths["/api/v1/admin/users/{user_id}/entitlements/{feature}"]["put"]
    assert logout["security"]
    assert grant["security"]


def test_read_only_operations_do_not_ask_for_a_csrf_token(
    settings_factory: SettingsFactory,
) -> None:
    paths = spec(settings_factory)["paths"]
    assert "security" not in paths["/api/v1/auth/me"]["get"]
    assert "security" not in paths["/api/v1/entitlements/me"]["get"]


def test_docs_explain_how_to_get_the_token(settings_factory: SettingsFactory) -> None:
    description = spec(settings_factory)["info"]["description"]
    assert "dev-login" in description
    assert "csrf_token" in description


def test_documenting_the_header_does_not_weaken_enforcement(
    settings_factory: SettingsFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # This unit test has no database; the rate limiter (which needs one) is covered elsewhere.
    monkeypatch.setattr("alvo.identity.api.enforce", lambda *args, **kwargs: None)
    app = create_app(settings_factory(environment="development"), readiness_probe=lambda: True)
    client = TestClient(app, base_url="https://testserver")
    response = client.post("/api/v1/auth/logout", headers={"Origin": "https://testserver"})
    assert response.status_code in {401, 403}
