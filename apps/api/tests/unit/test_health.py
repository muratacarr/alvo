from fastapi.testclient import TestClient

from alvo.main import create_app
from tests.conftest import SettingsFactory

LEAKY_ERROR = "connection to server at db (10.0.0.5) failed: password authentication failed"


def client(settings_factory: SettingsFactory, ready: bool, environment: str = "test") -> TestClient:
    app = create_app(settings_factory(environment=environment), readiness_probe=lambda: ready)
    return TestClient(app, raise_server_exceptions=False)


def test_live_is_ok_without_touching_dependencies(settings_factory: SettingsFactory) -> None:
    def exploding_probe() -> bool:
        raise AssertionError("liveness must not call the database probe")

    app = create_app(settings_factory(), readiness_probe=exploding_probe)
    response = TestClient(app).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_is_ok_when_database_is_reachable(settings_factory: SettingsFactory) -> None:
    response = client(settings_factory, ready=True).get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_is_503_with_generic_body_when_database_is_down(
    settings_factory: SettingsFactory,
) -> None:
    response = client(settings_factory, ready=False).get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_ready_never_leaks_probe_exception_details(settings_factory: SettingsFactory) -> None:
    def failing_probe() -> bool:
        raise RuntimeError(LEAKY_ERROR)

    app = create_app(settings_factory(), readiness_probe=failing_probe)
    response = TestClient(app, raise_server_exceptions=False).get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "password" not in response.text
    assert "10.0.0.5" not in response.text


def test_unhandled_errors_return_a_generic_500(settings_factory: SettingsFactory) -> None:
    app = create_app(settings_factory(), readiness_probe=lambda: True)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError(LEAKY_ERROR)

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert response.json() == {"error": "internal_error"}
    assert "password" not in response.text


def test_api_docs_are_disabled_in_production(settings_factory: SettingsFactory) -> None:
    prod = client(settings_factory, ready=True, environment="production")
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert prod.get(path).status_code == 404


def test_api_docs_are_available_in_development(settings_factory: SettingsFactory) -> None:
    dev = client(settings_factory, ready=True, environment="development")
    assert dev.get("/openapi.json").status_code == 200


def test_responses_carry_no_server_banner_and_forbid_caching(
    settings_factory: SettingsFactory,
) -> None:
    response = client(settings_factory, ready=True).get("/health/live")
    assert "server" not in response.headers
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
