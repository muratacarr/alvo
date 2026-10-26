"""Import job bookkeeping and the per-project lock. No document content is ever stored."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from alvo.imports.domain import ImportJob
from alvo.shared.orm import Base

# Longest a single import statement may run; a stuck or hostile import cannot hold the lock.
STATEMENT_TIMEOUT_MS = 15_000


class ImportJobRow(Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key", name="uq_import_jobs_project_key"),
        Index("ix_import_jobs_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    source_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SqlImportStore:
    def __init__(self, db: Session) -> None:
        self._db = db

    def lock_project(self, project_id: UUID) -> None:
        """Serialise imports into one project until the transaction ends.

        This makes "find or create module/topic" safe without extra unique constraints, and
        lets a second request with the same idempotency key wait and then replay the first.
        """
        self._db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"import:{project_id}"},
        )

    def limit_statement_time(self) -> None:
        self._db.execute(text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}"))

    def commits_since(self, owner_id: UUID, since: datetime) -> int:
        return int(
            self._db.execute(
                select(func.count())
                .select_from(ImportJobRow)
                .where(ImportJobRow.owner_id == owner_id, ImportJobRow.created_at > since)
            ).scalar_one()
        )

    def find_job(self, project_id: UUID, key: str) -> ImportJob | None:
        row = self._db.execute(
            select(ImportJobRow).where(
                ImportJobRow.project_id == project_id, ImportJobRow.idempotency_key == key
            )
        ).scalar_one_or_none()
        return ImportJob(row.id, row.source_digest, dict(row.counts)) if row else None

    def create_job(
        self, *, project_id: UUID, owner_id: UUID, key: str, digest: str, now: datetime
    ) -> UUID:
        job_id = uuid4()
        self._db.add(
            ImportJobRow(
                id=job_id,
                project_id=project_id,
                owner_id=owner_id,
                idempotency_key=key,
                source_digest=digest,
                status="committed",
                counts={},
                created_at=now,
                completed_at=None,
            )
        )
        self._db.flush()
        return job_id

    def finish_job(self, job_id: UUID, counts: dict[str, int], now: datetime) -> None:
        row = self._db.get(ImportJobRow, job_id)
        if row is None:  # created earlier in this same transaction
            raise RuntimeError("import job disappeared inside its own transaction")
        row.counts = counts
        row.completed_at = now
        self._db.flush()
