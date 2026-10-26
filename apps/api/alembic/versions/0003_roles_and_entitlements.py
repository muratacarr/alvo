"""User roles and default-deny AI entitlements with an append-only audit table.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(16), nullable=False, server_default="user"))
    op.create_check_constraint("ck_users_role", "users", "role IN ('user', 'admin')")

    op.create_table(
        "entitlements",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("feature", sa.String(8), primary_key=True),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("requests_per_day", sa.Integer(), nullable=True),
        sa.Column("monthly_units", sa.Integer(), nullable=True),
        sa.Column("granted_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("feature IN ('llm', 'stt', 'tts')", name="ck_entitlements_feature"),
        sa.CheckConstraint(
            "(mode = 'exempt' AND requests_per_day IS NULL AND monthly_units IS NULL) OR "
            "(mode = 'limited' AND requests_per_day > 0 AND monthly_units > 0)",
            name="ck_entitlements_mode_limits",
        ),
    )

    # Audit rows carry plain ids (no foreign keys) so history survives user deletion.
    op.create_table(
        "entitlement_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=False),
        sa.Column("feature", sa.String(8), nullable=False),
        sa.Column("action", sa.String(8), nullable=False),
        sa.Column("mode", sa.String(8), nullable=True),
        sa.Column("requests_per_day", sa.Integer(), nullable=True),
        sa.Column("monthly_units", sa.Integer(), nullable=True),
        sa.CheckConstraint("action IN ('grant', 'revoke')", name="ck_entitlement_events_action"),
    )
    op.create_index(
        "ix_entitlement_events_target_user_id", "entitlement_events", ["target_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_entitlement_events_target_user_id", table_name="entitlement_events")
    op.drop_table("entitlement_events")
    op.drop_table("entitlements")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
