"""Application factory.

`create_app` accepts its collaborators so tests can substitute them; production
uses `uvicorn --factory alvo.main:create_app`.
"""

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from alvo.shared.config import Settings
from alvo.shared.db import create_db_engine, make_readiness_probe

logger = logging.getLogger("alvo")

ReadinessProbe = Callable[[], bool]


def create_app(
    settings: Settings | None = None, readiness_probe: ReadinessProbe | None = None
) -> FastAPI:
    # Settings() validates secrets and raises at startup if anything is missing or weak.
    settings = settings or Settings()
    probe = readiness_probe or make_readiness_probe(create_db_engine(settings))

    docs_enabled = settings.environment != "production"
    app = FastAPI(
        title="Alvo API",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

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
