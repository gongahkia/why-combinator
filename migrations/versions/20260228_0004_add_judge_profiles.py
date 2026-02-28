"""Add judge profile table

Revision ID: 20260228_0004
Revises: 20260228_0003
Create Date: 2026-02-28 00:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0004"
down_revision = "20260228_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "judge_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.Uuid(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("scoring_style", sa.String(length=64), nullable=False),
        sa.Column("profile_prompt", sa.Text(), nullable=False),
        sa.Column("head_judge", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], name=op.f("fk_judge_profiles_challenge_id_challenges"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_judge_profiles")),
    )
    op.create_index(op.f("ix_judge_profiles_challenge_id"), "judge_profiles", ["challenge_id"], unique=False)
    op.create_index(op.f("ix_judge_profiles_domain"), "judge_profiles", ["domain"], unique=False)
    op.create_index(op.f("ix_judge_profiles_created_at"), "judge_profiles", ["created_at"], unique=False)
    op.create_index(op.f("ix_judge_profiles_updated_at"), "judge_profiles", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_judge_profiles_updated_at"), table_name="judge_profiles")
    op.drop_index(op.f("ix_judge_profiles_created_at"), table_name="judge_profiles")
    op.drop_index(op.f("ix_judge_profiles_domain"), table_name="judge_profiles")
    op.drop_index(op.f("ix_judge_profiles_challenge_id"), table_name="judge_profiles")
    op.drop_table("judge_profiles")
