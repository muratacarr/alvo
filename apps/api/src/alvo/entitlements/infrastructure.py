"""SQLAlchemy persistence for entitlements and their audit trail."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from alvo.entitlements.domain import Entitlement, Feature, Mode
from alvo.shared.orm import Base


class EntitlementRow(Base):
    __tablename__ = "entitlements"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    feature: Mapped[str] = mapped_column(String(8), primary_key=True)
    mode: Mapped[str] = mapped_column(String(8))
    requests_per_day: Mapped[int | None] = mapped_column(Integer)
    monthly_units: Mapped[int | None] = mapped_column(Integer)
    granted_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EntitlementEventRow(Base):
    __tablename__ = "entitlement_events"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[UUID]
    target_user_id: Mapped[UUID] = mapped_column(index=True)
    feature: Mapped[str] = mapped_column(String(8))
    action: Mapped[str] = mapped_column(String(8))
    mode: Mapped[str | None] = mapped_column(String(8))
    requests_per_day: Mapped[int | None] = mapped_column(Integer)
    monthly_units: Mapped[int | None] = mapped_column(Integer)


def _to_entitlement(row: EntitlementRow) -> Entitlement:
    mode: Mode = "exempt" if row.mode == "exempt" else "limited"
    return Entitlement(Feature(row.feature), mode, row.requests_per_day, row.monthly_units)


class SqlEntitlementStore:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, user_id: UUID, feature: Feature) -> Entitlement | None:
        row = self._db.get(EntitlementRow, (user_id, feature.value))
        return _to_entitlement(row) if row else None

    def list_for_user(self, user_id: UUID) -> dict[Feature, Entitlement]:
        rows = self._db.execute(
            select(EntitlementRow).where(EntitlementRow.user_id == user_id)
        ).scalars()
        return {Feature(r.feature): _to_entitlement(r) for r in rows}

    def upsert(
        self,
        user_id: UUID,
        feature: Feature,
        mode: str,
        requests_per_day: int | None,
        monthly_units: int | None,
        granted_by: UUID,
        now: datetime,
    ) -> None:
        values = {
            "mode": mode,
            "requests_per_day": requests_per_day,
            "monthly_units": monthly_units,
            "granted_by": granted_by,
            "granted_at": now,
        }
        self._db.execute(
            insert(EntitlementRow)
            .values(user_id=user_id, feature=feature.value, **values)
            .on_conflict_do_update(index_elements=["user_id", "feature"], set_=values)
        )

    def delete(self, user_id: UUID, feature: Feature) -> bool:
        result = self._db.execute(
            delete(EntitlementRow).where(
                EntitlementRow.user_id == user_id, EntitlementRow.feature == feature.value
            )
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]

    def add_event(
        self,
        *,
        actor_id: UUID,
        target_user_id: UUID,
        feature: Feature,
        action: str,
        mode: str | None,
        requests_per_day: int | None,
        monthly_units: int | None,
        now: datetime,
    ) -> None:
        self._db.add(
            EntitlementEventRow(
                id=uuid4(),
                occurred_at=now,
                actor_id=actor_id,
                target_user_id=target_user_id,
                feature=feature.value,
                action=action,
                mode=mode,
                requests_per_day=requests_per_day,
                monthly_units=monthly_units,
            )
        )
