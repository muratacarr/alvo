"""Application factory.

`create_app` accepts its collaborators so tests can substitute them; production
uses `uvicorn --factory alvo.main:create_app`.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker

from alvo.content.api import router as content_router
from alvo.entitlements.api import build_router as build_entitlements_router
from alvo.identity.api import build_router as build_identity_router
from alvo.identity.application import IdentityService
from alvo.identity.domain import SessionPolicy
from alvo.imports.api import router as imports_router
from alvo.projects.api import router as projects_router
from alvo.shared.config import Settings
from alvo.shared.db import create_db_engine, make_readiness_probe
from alvo.shared.errors import ApiError
from alvo.shared.http import BodySizeLimitMiddleware, PayloadTooLarge

logger = logging.getLogger("alvo")

ReadinessProbe = Callable[[], bool]
Clock = Callable[[], datetime]


_DOCS_HELP = """
**Trying write requests in Swagger UI (development only)**

1. Run `POST /api/v1/auth/dev-login` with `{"subject": "alice"}`. The session cookie is
   stored by the browser automatically.
2. Copy `csrf_token` from the response, click **Authorize** and paste it into `CSRFToken`.
3. State-changing requests (POST, PATCH, DELETE) can now be sent from this page.
   The browser adds the required `Origin` header itself.
"""


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
        description=_DOCS_HELP if docs_enabled else "",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.state.session_factory = sessionmaker(engine, expire_on_commit=False)
    app.state.identity_service = identity_service
    app.state.settings = settings
    app.state.clock = clock or _utc_now
    app.include_router(build_identity_router(settings, identity_service))
    app.include_router(build_entitlements_router(settings, identity_service))
    app.include_router(projects_router)
    app.include_router(content_router)
    app.include_router(imports_router)
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=settings.max_request_bytes,
        large_suffixes=("/imports/preview", "/imports/commit"),
        large_max_bytes=settings.max_import_bytes,
    )

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse({"error": exc.code, **exc.extra}, status_code=exc.status_code)

    @app.exception_handler(PayloadTooLarge)
    async def payload_too_large(request: Request, exc: PayloadTooLarge) -> JSONResponse:
        return JSONResponse({"error": "payload_too_large"}, status_code=413)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Report which fields failed, never the submitted values.
        fields = [".".join(str(part) for part in err["loc"]) for err in exc.errors()]
        return JSONResponse({"error": "invalid_request", "fields": fields}, status_code=422)

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
