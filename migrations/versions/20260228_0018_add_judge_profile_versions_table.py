"""Add judge profile versions table

Revision ID: 20260228_0018
Revises: 20260228_0017
Create Date: 2026-02-28 16:55:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0018"
down_revision = "20260228_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "judge_profile_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("profiles_payload", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_judge_profile_versions")),
        sa.UniqueConstraint(
            "challenge_id",
            "version_number",
            name=op.f("uq_judge_profile_versions_challenge_id"),
        ),
    )
    op.create_index(
        op.f("ix_judge_profile_versions_challenge_id"),
        "judge_profile_versions",
        ["challenge_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_judge_profile_versions_is_active"),
        "judge_profile_versions",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_judge_profile_versions_created_at"),
        "judge_profile_versions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_judge_profile_versions_updated_at"),
        "judge_profile_versions",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_judge_profile_versions_updated_at"), table_name="judge_profile_versions")
    op.drop_index(op.f("ix_judge_profile_versions_created_at"), table_name="judge_profile_versions")
    op.drop_index(op.f("ix_judge_profile_versions_is_active"), table_name="judge_profile_versions")
    op.drop_index(op.f("ix_judge_profile_versions_challenge_id"), table_name="judge_profile_versions")
    op.drop_table("judge_profile_versions")
