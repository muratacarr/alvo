"""Duplicate identity for learning items, practice modes, and import jobs.

Adds `external_id`, `fingerprint`, `loose_key` and `practice_modes` to learning_items and
back-fills existing rows with a frozen copy of the normalisation rules (a migration must not
depend on application code that may change later). Databases that already hold two items
with the same type and prompt in one project must be cleaned up first: the unique index
below will refuse to build otherwise.

Revision ID: 0005
Revises: 0004
"""

import hashlib
import re
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WHITESPACE = re.compile(r"\s+")


def _fingerprint(item_type: str, prompt: str) -> str:
    strict = _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", prompt)).strip().casefold()
    return hashlib.sha256(f"{item_type}\n{strict}".encode()).hexdigest()


def _loose_key(prompt: str) -> str:
    decomposed = unicodedata.normalize("NFKD", prompt)
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    kept = "".join(c for c in without_marks.casefold() if c.isalnum() or c.isspace())
    return hashlib.sha256(_WHITESPACE.sub(" ", kept).strip().encode()).hexdigest()


def upgrade() -> None:
    op.add_column("learning_items", sa.Column("external_id", sa.String(100), nullable=True))
    op.add_column("learning_items", sa.Column("fingerprint", sa.String(64), nullable=True))
    op.add_column("learning_items", sa.Column("loose_key", sa.String(64), nullable=True))
    op.add_column(
        "learning_items",
        sa.Column(
            "practice_modes",
            postgresql.ARRAY(sa.String(32)),
            nullable=False,
            server_default="{}",
        ),
    )

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, type, prompt FROM learning_items")).all()
    for row in rows:
        connection.execute(
            sa.text("UPDATE learning_items SET fingerprint = :f, loose_key = :l WHERE id = :i"),
            {"f": _fingerprint(row.type, row.prompt), "l": _loose_key(row.prompt), "i": row.id},
        )

    op.alter_column("learning_items", "fingerprint", nullable=False)
    op.alter_column("learning_items", "loose_key", nullable=False)
    op.create_check_constraint(
        "ck_items_practice_modes_size", "learning_items", "cardinality(practice_modes) <= 7"
    )
    op.create_index(
        "uq_items_project_fingerprint",
        "learning_items",
        ["project_id", "fingerprint"],
        unique=True,
    )
    op.create_index(
        "uq_items_project_external_id",
        "learning_items",
        ["project_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_index("ix_items_project_loose_key", "learning_items", ["project_id", "loose_key"])

    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_import_jobs_project_key"),
        sa.CheckConstraint("status IN ('committed')", name="ck_import_jobs_status"),
    )
    op.create_index("ix_import_jobs_owner_created", "import_jobs", ["owner_id", "created_at"])


def downgrade() -> None:
    op.drop_table("import_jobs")
    op.drop_index("ix_items_project_loose_key", table_name="learning_items")
    op.drop_index("uq_items_project_external_id", table_name="learning_items")
    op.drop_index("uq_items_project_fingerprint", table_name="learning_items")
    op.drop_constraint("ck_items_practice_modes_size", "learning_items", type_="check")
    op.drop_column("learning_items", "practice_modes")
    op.drop_column("learning_items", "loose_key")
    op.drop_column("learning_items", "fingerprint")
    op.drop_column("learning_items", "external_id")
