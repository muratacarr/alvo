"""HTTP transport for identity. Routes stay thin: validation, cookies, CSRF, status codes."""

import logging
from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from alvo.identity.application import AuthenticatedSession, IdentityService
from alvo.identity.domain import NotInvited, Principal, VerifiedIdentity
from alvo.identity.oidc import GoogleOidc, OidcError
from alvo.identity.security import open_flow_state, seal_flow_state, tokens_match
from alvo.shared.config import Settings
from alvo.shared.errors import ApiError
from alvo.shared.http import client_address
from alvo.shared.ratelimit import enforce

COOKIE_NAME = "__Host-alvo_session"
FLOW_COOKIE = "__Host-alvo_oidc"
_FLOW_SECONDS = 600
_MAX_CODE_LENGTH = 2048
audit = logging.getLogger("alvo.audit")
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
    settings: Settings = request.app.state.settings
    enforce(request, f"user:{session.principal.user_id}", settings.user_requests_per_minute)
    return session


def limit_auth_attempts(request: Request) -> None:
    """Router-level guard: unsafe auth requests are limited per client address."""
    if request.method in _SAFE_METHODS:
        return
    settings: Settings = request.app.state.settings
    address = client_address(request, trust_forwarded_for=settings.trust_forwarded_for)
    enforce(request, f"auth:{address}", settings.auth_attempts_per_minute)


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


# Declares the header in the OpenAPI document so Swagger UI's "Authorize" can send it.
# Documentation only (auto_error=False): the real check is `require_csrf` below.
csrf_header_scheme = APIKeyHeader(
    name=CSRF_HEADER,
    scheme_name="CSRFToken",
    auto_error=False,
    description="The `csrf_token` returned by login (or GET /api/v1/auth/csrf).",
)


def require_csrf(
    request: Request,
    session: Annotated[AuthenticatedSession, Depends(require_session)],
    _documented: Annotated[str | None, Depends(csrf_header_scheme)] = None,
) -> AuthenticatedSession:
    presented = request.headers.get(CSRF_HEADER, "")
    if not tokens_match(session.csrf_token, presented):
        raise ApiError(403, "forbidden")
    return session


def csrf_principal_dependency(
    session: Annotated[AuthenticatedSession, Depends(require_csrf)],
) -> Principal:
    """For state-changing routes: the authenticated caller whose CSRF token checked out."""
    return session.principal


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


def build_router(
    settings: Settings, service: IdentityService, oidc: GoogleOidc | None = None
) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/auth",
        dependencies=[Depends(verify_origin), Depends(limit_auth_attempts)],
    )
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

    if oidc is not None:
        _add_google_routes(router, settings, service, oidc, set_session_cookie)

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


def _add_google_routes(
    router: APIRouter,
    settings: Settings,
    service: IdentityService,
    oidc: GoogleOidc,
    set_session_cookie: "Callable[[Response, str], None]",
) -> None:
    key = settings.session_secret.get_secret_value()
    home = f"{settings.public_origin}/"

    def throttle(request: Request) -> None:
        # Safe (GET) routes skip the router-level limit, but the callback calls Google.
        address = client_address(request, trust_forwarded_for=settings.trust_forwarded_for)
        enforce(request, f"oidc:{address}", settings.auth_attempts_per_minute)

    def finish(outcome: str) -> Response:
        response = RedirectResponse(f"{home}?signin={outcome}", status_code=302)
        response.delete_cookie(FLOW_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
        return response

    @router.get("/google/start", include_in_schema=False)
    def google_start(request: Request) -> Response:
        throttle(request)
        flow = oidc.begin()
        expires = int(service.now().timestamp()) + _FLOW_SECONDS
        sealed = seal_flow_state(
            key, {"s": flow.state, "n": flow.nonce, "v": flow.verifier, "e": expires}
        )
        response = RedirectResponse(flow.url, status_code=302)
        response.set_cookie(
            FLOW_COOKIE,
            sealed,
            max_age=_FLOW_SECONDS,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        return response

    @router.get("/google/callback", include_in_schema=False)
    def google_callback(
        request: Request,
        db: Annotated[Session, Depends(get_db)],
        code: str | None = None,
        state: str | None = None,
    ) -> Response:
        throttle(request)
        sealed = request.cookies.get(FLOW_COOKIE)
        flow = open_flow_state(key, sealed) if sealed else None
        if (
            flow is None
            or not code
            or len(code) > _MAX_CODE_LENGTH
            or not state
            or not isinstance(flow.get("e"), int)
            or int(flow["e"]) < int(service.now().timestamp())
            or not tokens_match(str(flow.get("s", "")), state)
        ):
            audit.warning("event=login_failed provider=google reason=flow")
            return finish("failed")
        try:
            claims = oidc.complete(code, str(flow["v"]), str(flow["n"]))
        except OidcError as exc:
            audit.warning("event=login_failed provider=google reason=%s", exc)
            return finish("failed")
        identity = VerifiedIdentity("google", claims.subject, claims.email)
        try:
            signed_in = service.sign_in_invited(db, identity, request.cookies.get(COOKIE_NAME))
        except NotInvited:
            audit.warning("event=login_denied provider=google reason=not_invited")
            return finish("not_invited")
        response = finish("ok")
        set_session_cookie(response, signed_in.token)
        return response
