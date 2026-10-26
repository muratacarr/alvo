"""HTTP transport for entitlements: a read endpoint for the caller, admin-only changes."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from alvo.entitlements import application
from alvo.entitlements.domain import Feature, GrantCaps
from alvo.identity.api import (
    get_db,
    principal_dependency,
    require_admin_change,
    require_admin_read,
    verify_origin,
)
from alvo.identity.application import IdentityService
from alvo.identity.domain import Principal
from alvo.shared.config import Settings
from alvo.shared.errors import ApiError


class GrantRequest(BaseModel):
    """Only these fields are writable; the target user and feature come from the path."""

    model_config = ConfigDict(extra="forbid", strict=True)

    mode: Literal["limited", "exempt"]
    requests_per_day: int | None = None
    monthly_units: int | None = None


def _parse_feature(raw: str) -> Feature:
    try:
        return Feature(raw)
    except ValueError:
        raise ApiError(404, "not_found") from None


def build_router(settings: Settings, service: IdentityService) -> APIRouter:
    router = APIRouter(dependencies=[Depends(verify_origin)])
    caps = GrantCaps(settings.ai_max_requests_per_day, settings.ai_max_monthly_units)

    @router.get("/api/v1/entitlements/me")
    def my_entitlements(
        principal: Annotated[Principal, Depends(principal_dependency)],
        db: Annotated[Session, Depends(get_db)],
    ) -> dict[str, list[dict[str, object]]]:
        summary = application.access_summary(db, principal.user_id)
        return {
            "features": [
                {"feature": feature.value, "allowed": access.allowed}
                for feature, access in summary.items()
            ]
        }

    @router.get("/api/v1/admin/users/{user_id}/entitlements")
    def user_entitlements(
        user_id: UUID,
        _admin: Annotated[Principal, Depends(require_admin_read)],
        db: Annotated[Session, Depends(get_db)],
    ) -> dict[str, list[dict[str, object]]]:
        summary = application.access_summary(db, user_id)
        return {
            "features": [
                {"feature": f.value, "allowed": a.allowed, "exempt": a.exempt}
                for f, a in summary.items()
            ]
        }

    @router.put("/api/v1/admin/users/{user_id}/entitlements/{feature}", status_code=204)
    def grant(
        user_id: UUID,
        feature: str,
        body: GrantRequest,
        admin: Annotated[Principal, Depends(require_admin_change)],
        db: Annotated[Session, Depends(get_db)],
    ) -> Response:
        application.grant(
            db,
            actor_id=admin.user_id,
            target_user_id=user_id,
            feature=_parse_feature(feature),
            mode=body.mode,
            requests_per_day=body.requests_per_day,
            monthly_units=body.monthly_units,
            caps=caps,
            now=service.now(),
        )
        return Response(status_code=204)

    @router.delete("/api/v1/admin/users/{user_id}/entitlements/{feature}", status_code=204)
    def revoke(
        user_id: UUID,
        feature: str,
        admin: Annotated[Principal, Depends(require_admin_change)],
        db: Annotated[Session, Depends(get_db)],
    ) -> Response:
        application.revoke(
            db,
            actor_id=admin.user_id,
            target_user_id=user_id,
            feature=_parse_feature(feature),
            now=service.now(),
        )
        return Response(status_code=204)

    return router
