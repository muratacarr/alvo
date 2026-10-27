"""Counters for the PostgreSQL-backed rate limiter.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_counters",
        sa.Column("bucket", sa.String(200), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("bucket", "window_start"),
    )
    # Old windows are pruned by window_start, so index it.
    op.create_index("ix_rate_limit_counters_window", "rate_limit_counters", ["window_start"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_counters_window", table_name="rate_limit_counters")
    op.drop_table("rate_limit_counters")
