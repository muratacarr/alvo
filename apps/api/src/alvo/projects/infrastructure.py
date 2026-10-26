"""SQLAlchemy persistence for projects. Every query is scoped by owner."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, select, tuple_
from sqlalchemy.orm import Mapped, Session, mapped_column

from alvo.projects.domain import ProjectRecord
from alvo.shared.orm import Base


class ProjectRow(Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_owner_created", "owner_id", "created_at", "id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _to_record(row: ProjectRow) -> ProjectRecord:
    return ProjectRecord(
        row.id,
        row.owner_id,
        row.title,
        row.description,
        row.created_at,
        row.updated_at,
        row.archived_at,
    )


class SqlProjectStore:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self, owner_id: UUID, title: str, description: str | None, now: datetime
    ) -> ProjectRecord:
        row = ProjectRow(
            id=uuid4(),
            owner_id=owner_id,
            title=title,
            description=description,
            created_at=now,
            updated_at=now,
            archived_at=None,
        )
        self._db.add(row)
        self._db.flush()
        return _to_record(row)

    def get_owned(self, owner_id: UUID, project_id: UUID) -> ProjectRecord | None:
        """The owner filter is part of the query, so a foreign id is indistinguishable from none."""
        row = self._db.execute(
            select(ProjectRow).where(ProjectRow.id == project_id, ProjectRow.owner_id == owner_id)
        ).scalar_one_or_none()
        return _to_record(row) if row else None

    def list_owned(
        self,
        owner_id: UUID,
        *,
        include_archived: bool,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[ProjectRecord]:
        statement = select(ProjectRow).where(ProjectRow.owner_id == owner_id)
        if not include_archived:
            statement = statement.where(ProjectRow.archived_at.is_(None))
        if after is not None:
            statement = statement.where(
                tuple_(ProjectRow.created_at, ProjectRow.id) > tuple_(after[0], after[1])
            )
        rows = self._db.execute(
            statement.order_by(ProjectRow.created_at, ProjectRow.id).limit(limit)
        ).scalars()
        return [_to_record(r) for r in rows]

    def update(
        self,
        owner_id: UUID,
        project_id: UUID,
        changes: dict[str, Any],
        now: datetime,
    ) -> ProjectRecord | None:
        row = self._db.execute(
            select(ProjectRow).where(ProjectRow.id == project_id, ProjectRow.owner_id == owner_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        for key, value in changes.items():
            setattr(row, key, value)
        row.updated_at = now
        self._db.flush()
        return _to_record(row)

    def set_archived(
        self, owner_id: UUID, project_id: UUID, archived_at: datetime | None, now: datetime
    ) -> ProjectRecord | None:
        row = self._db.execute(
            select(ProjectRow).where(ProjectRow.id == project_id, ProjectRow.owner_id == owner_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        row.archived_at = archived_at
        row.updated_at = now
        self._db.flush()
        return _to_record(row)
