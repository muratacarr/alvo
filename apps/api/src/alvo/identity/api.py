"""HTTP transport for identity. Routes stay thin: validation, cookies, CSRF, status codes."""

from collections.abc import Iterator
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from alvo.identity.application import AuthenticatedSession, IdentityService
from alvo.identity.domain import Principal, VerifiedIdentity
from alvo.identity.security import tokens_match
from alvo.shared.config import Settings
from alvo.shared.errors import ApiError

COOKIE_NAME = "__Host-alvo_session"
CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class DevLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    subject: Annotated[str, Field(min_length=1, max_length=200)]


class LoginResponse(BaseModel):
    user_id: str
    csrf_token: str


def get_db(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    with factory() as db:
        yield db


def require_session(
    request: Request, db: Annotated[Session, Depends(get_db)]
) -> AuthenticatedSession:
    service: IdentityService = request.app.state.identity_service
    token = request.cookies.get(COOKIE_NAME)
    session = service.authenticate(db, token) if token else None
    if session is None:
        raise ApiError(401, "unauthenticated")
    return session


def principal_dependency(
    session: Annotated[AuthenticatedSession, Depends(require_session)],
) -> Principal:
    """Dependency for other modules: the authenticated caller, or a generic 401."""
    return session.principal


def verify_origin(request: Request) -> None:
    """Router-level guard: unsafe methods must come from the configured public origin."""
    if request.method in _SAFE_METHODS:
        return
    settings: Settings = request.app.state.settings
    if request.headers.get("origin") != settings.public_origin:
        raise ApiError(403, "forbidden")


def require_csrf(
    request: Request, session: Annotated[AuthenticatedSession, Depends(require_session)]
) -> AuthenticatedSession:
    presented = request.headers.get(CSRF_HEADER, "")
    if not tokens_match(session.csrf_token, presented):
        raise ApiError(403, "forbidden")
    return session


def require_admin_read(
    session: Annotated[AuthenticatedSession, Depends(require_session)],
) -> Principal:
    if session.principal.role != "admin":
        raise ApiError(403, "forbidden")
    return session.principal


def require_admin_change(
    request: Request, session: Annotated[AuthenticatedSession, Depends(require_csrf)]
) -> Principal:
    """CSRF-checked admin that signed in recently (step-up authentication)."""
    if session.principal.role != "admin":
        raise ApiError(403, "forbidden")
    settings: Settings = request.app.state.settings
    service: IdentityService = request.app.state.identity_service
    age = service.now() - session.session_created_at
    if age > timedelta(minutes=settings.admin_recent_login_minutes):
        raise ApiError(403, "reauthentication_required")
    return session.principal


def build_router(settings: Settings, service: IdentityService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/auth", dependencies=[Depends(verify_origin)])
    max_age = settings.session_absolute_minutes * 60

    def set_session_cookie(response: Response, token: str) -> None:
        response.set_cookie(
            COOKIE_NAME,
            token,
            max_age=max_age,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )

    # The development login exists only for the mock provider and never in production.
    if settings.identity_provider == "mock" and settings.environment != "production":

        @router.post("/dev-login")
        def dev_login(
            body: DevLoginRequest,
            request: Request,
            response: Response,
            db: Annotated[Session, Depends(get_db)],
        ) -> LoginResponse:
            signed_in = service.sign_in(
                db,
                VerifiedIdentity(provider="mock", subject=body.subject),
                request.cookies.get(COOKIE_NAME),
            )
            set_session_cookie(response, signed_in.token)
            return LoginResponse(user_id=str(signed_in.user_id), csrf_token=signed_in.csrf_token)

    @router.get("/me")
    def me(session: Annotated[AuthenticatedSession, Depends(require_session)]) -> dict[str, str]:
        return {
            "user_id": str(session.principal.user_id),
            "role": session.principal.role,
        }

    @router.get("/csrf")
    def csrf(
        session: Annotated[AuthenticatedSession, Depends(require_session)],
    ) -> dict[str, str]:
        return {"csrf_token": session.csrf_token}

    @router.post("/logout", status_code=204)
    def logout(
        request: Request,
        db: Annotated[Session, Depends(get_db)],
        _session: Annotated[AuthenticatedSession, Depends(require_csrf)],
    ) -> Response:
        token = request.cookies.get(COOKIE_NAME)
        if token:
            service.sign_out(db, token)
        response = Response(status_code=204)
        response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="lax")
        return response

    return router
