"""Entitlement use cases. `check_access` is the single read path the budget gateway will use."""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from alvo.entitlements.domain import (
    Access,
    Feature,
    GrantCaps,
    GrantError,
    evaluate,
    validate_grant,
)
from alvo.entitlements.infrastructure import SqlEntitlementStore
from alvo.identity.infrastructure import SqlIdentityStore
from alvo.shared.errors import ApiError

audit = logging.getLogger("alvo.audit")


def check_access(db: Session, user_id: UUID, feature: Feature) -> Access:
    return evaluate(SqlEntitlementStore(db).get(user_id, feature))


def access_summary(db: Session, user_id: UUID) -> dict[Feature, Access]:
    store = SqlEntitlementStore(db)
    granted = store.list_for_user(user_id)
    return {feature: evaluate(granted.get(feature)) for feature in Feature}


def grant(
    db: Session,
    *,
    actor_id: UUID,
    target_user_id: UUID,
    feature: Feature,
    mode: str,
    requests_per_day: int | None,
    monthly_units: int | None,
    caps: GrantCaps,
    now: datetime,
) -> None:
    try:
        validate_grant(
            mode, requests_per_day=requests_per_day, monthly_units=monthly_units, caps=caps
        )
    except GrantError as exc:
        raise ApiError(422, "invalid_grant") from exc
    if not SqlIdentityStore(db).user_exists(target_user_id):
        raise ApiError(404, "not_found")
    store = SqlEntitlementStore(db)
    store.upsert(target_user_id, feature, mode, requests_per_day, monthly_units, actor_id, now)
    store.add_event(
        actor_id=actor_id,
        target_user_id=target_user_id,
        feature=feature,
        action="grant",
        mode=mode,
        requests_per_day=requests_per_day,
        monthly_units=monthly_units,
        now=now,
    )
    db.commit()
    audit.info(
        "event=entitlement_grant actor=%s target=%s feature=%s mode=%s",
        actor_id,
        target_user_id,
        feature.value,
        mode,
    )


def revoke(
    db: Session, *, actor_id: UUID, target_user_id: UUID, feature: Feature, now: datetime
) -> None:
    """Idempotent: revoking something that is not granted changes and records nothing."""
    store = SqlEntitlementStore(db)
    if not store.delete(target_user_id, feature):
        db.rollback()
        return
    store.add_event(
        actor_id=actor_id,
        target_user_id=target_user_id,
        feature=feature,
        action="revoke",
        mode=None,
        requests_per_day=None,
        monthly_units=None,
        now=now,
    )
    db.commit()
    audit.info(
        "event=entitlement_revoke actor=%s target=%s feature=%s",
        actor_id,
        target_user_id,
        feature.value,
    )
