"""Projects and the module/topic/item hierarchy.

Composite foreign keys (project_id, parent_id) make the database reject any child whose parent
belongs to another project, independently of application checks.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_projects_owner_created", "projects", ["owner_id", "created_at", "id"])

    op.create_table(
        "modules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("project_id", "id", name="uq_modules_project_id"),
    )
    op.create_index("ix_modules_project_id", "modules", ["project_id"])

    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("project_id", "id", name="uq_topics_project_id"),
        sa.ForeignKeyConstraint(
            ["project_id", "module_id"],
            ["modules.project_id", "modules.id"],
            name="fk_topics_module_same_project",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_topics_project_id", "topics", ["project_id"])

    op.create_table(
        "learning_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("prompt", sa.String(2000), nullable=False),
        sa.Column("sample_answer", sa.Text(), nullable=True),
        sa.Column("translation", sa.String(2000), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.String(64)), nullable=False, server_default="{}"),
        sa.Column("tags", postgresql.ARRAY(sa.String(64)), nullable=False, server_default="{}"),
        sa.Column(
            "follow_up_questions",
            postgresql.ARRAY(sa.String(500)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("difficulty", sa.SmallInteger(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id", "topic_id"],
            ["topics.project_id", "topics.id"],
            name="fk_items_topic_same_project",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "type IN ('question', 'phrase', 'vocabulary', 'concept', 'scenario')",
            name="ck_items_type",
        ),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_items_difficulty"),
        sa.CheckConstraint(
            "cardinality(keywords) <= 30 AND cardinality(tags) <= 30 "
            "AND cardinality(follow_up_questions) <= 10",
            name="ck_items_list_sizes",
        ),
    )
    op.create_index("ix_learning_items_project_id", "learning_items", ["project_id"])


def downgrade() -> None:
    op.drop_table("learning_items")
    op.drop_table("topics")
    op.drop_table("modules")
    op.drop_index("ix_projects_owner_created", table_name="projects")
    op.drop_table("projects")
