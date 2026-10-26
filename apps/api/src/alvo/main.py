"""Application factory.

`create_app` accepts its collaborators so tests can substitute them; production
uses `uvicorn --factory alvo.main:create_app`.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker

from alvo.entitlements.api import build_router as build_entitlements_router
from alvo.identity.api import build_router as build_identity_router
from alvo.identity.application import IdentityService
from alvo.identity.domain import SessionPolicy
from alvo.shared.config import Settings
from alvo.shared.db import create_db_engine, make_readiness_probe
from alvo.shared.errors import ApiError

logger = logging.getLogger("alvo")

ReadinessProbe = Callable[[], bool]
Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def create_app(
    settings: Settings | None = None,
    readiness_probe: ReadinessProbe | None = None,
    clock: Clock | None = None,
) -> FastAPI:
    # Settings() validates secrets and raises at startup if anything is missing or weak.
    settings = settings or Settings()
    engine = create_db_engine(settings)
    probe = readiness_probe or make_readiness_probe(engine)
    identity_service = IdentityService(
        secret=settings.session_secret.get_secret_value(),
        policy=SessionPolicy(
            idle=timedelta(minutes=settings.session_idle_minutes),
            absolute=timedelta(minutes=settings.session_absolute_minutes),
        ),
        clock=clock or _utc_now,
    )

    docs_enabled = settings.environment != "production"
    app = FastAPI(
        title="Alvo API",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.state.session_factory = sessionmaker(engine, expire_on_commit=False)
    app.state.identity_service = identity_service
    app.state.settings = settings
    app.include_router(build_identity_router(settings, identity_service))
    app.include_router(build_entitlements_router(settings, identity_service))

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse({"error": exc.code}, status_code=exc.status_code)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        # Never echo exception text: it may contain SQL, hosts or credentials.
        logger.error("unhandled_error type=%s", type(exc).__name__)
        return JSONResponse({"error": "internal_error"}, status_code=500)

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> JSONResponse:
        try:
            is_ready = probe()
        except Exception:
            is_ready = False
        if is_ready:
            return JSONResponse({"status": "ok"})
        return JSONResponse({"status": "unavailable"}, status_code=503)

    return app
