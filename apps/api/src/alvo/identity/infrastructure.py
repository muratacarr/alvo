"""SQLAlchemy persistence for users and sessions."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from alvo.identity.domain import Role, SessionRecord
from alvo.shared.orm import Base


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("provider", "subject", name="uq_users_provider_subject"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    role: Mapped[str] = mapped_column(String(16), server_default="user")


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _to_record(row: SessionRow) -> SessionRecord:
    return SessionRecord(
        id=row.id,
        user_id=row.user_id,
        created_at=row.created_at,
        last_seen_at=row.last_seen_at,
        revoked_at=row.revoked_at,
    )


class SqlIdentityStore:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_or_create_user(self, provider: str, subject: str, now: datetime) -> UUID:
        # ON CONFLICT DO NOTHING keeps concurrent first logins safe against the unique constraint.
        self._db.execute(
            insert(UserRow)
            .values(id=uuid4(), provider=provider, subject=subject, created_at=now)
            .on_conflict_do_nothing(constraint="uq_users_provider_subject")
        )
        return self._db.execute(
            select(UserRow.id).where(UserRow.provider == provider, UserRow.subject == subject)
        ).scalar_one()

    def user_exists(self, user_id: UUID) -> bool:
        found = self._db.execute(select(UserRow.id).where(UserRow.id == user_id)).first()
        return found is not None

    def get_role(self, user_id: UUID) -> Role:
        role = self._db.execute(select(UserRow.role).where(UserRow.id == user_id)).scalar_one()
        return "admin" if role == "admin" else "user"

    def set_role(self, provider: str, subject: str, role: Role) -> bool:
        """Change the role of an existing user; returns False when the user does not exist."""
        result = self._db.execute(
            update(UserRow)
            .where(UserRow.provider == provider, UserRow.subject == subject)
            .values(role=role)
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]

    def create_session(self, user_id: UUID, token_hash: str, now: datetime) -> SessionRecord:
        row = SessionRow(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            created_at=now,
            last_seen_at=now,
            revoked_at=None,
        )
        self._db.add(row)
        self._db.flush()
        return _to_record(row)

    def find_session(self, token_hash: str) -> SessionRecord | None:
        row = self._db.execute(
            select(SessionRow).where(SessionRow.token_hash == token_hash)
        ).scalar_one_or_none()
        return _to_record(row) if row else None

    def touch(self, session_id: UUID, now: datetime) -> None:
        self._db.execute(
            update(SessionRow).where(SessionRow.id == session_id).values(last_seen_at=now)
        )

    def revoke(self, session_id: UUID, now: datetime) -> None:
        self._db.execute(
            update(SessionRow)
            .where(SessionRow.id == session_id, SessionRow.revoked_at.is_(None))
            .values(revoked_at=now)
        )
