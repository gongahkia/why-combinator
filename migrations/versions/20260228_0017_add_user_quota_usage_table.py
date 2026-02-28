"""Add user quota usage table

Revision ID: 20260228_0017
Revises: 20260228_0016
Create Date: 2026-02-28 15:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0017"
down_revision = "20260228_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_quota_usages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quota_user_id", sa.String(length=128), nullable=False),
        sa.Column("challenges_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("runs_started", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("artifact_storage_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_quota_usages")),
        sa.UniqueConstraint("quota_user_id", name=op.f("uq_user_quota_usages_quota_user_id")),
    )
    op.create_index(op.f("ix_user_quota_usages_quota_user_id"), "user_quota_usages", ["quota_user_id"], unique=False)
    op.create_index(op.f("ix_user_quota_usages_created_at"), "user_quota_usages", ["created_at"], unique=False)
    op.create_index(op.f("ix_user_quota_usages_updated_at"), "user_quota_usages", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_quota_usages_updated_at"), table_name="user_quota_usages")
    op.drop_index(op.f("ix_user_quota_usages_created_at"), table_name="user_quota_usages")
    op.drop_index(op.f("ix_user_quota_usages_quota_user_id"), table_name="user_quota_usages")
    op.drop_table("user_quota_usages")
