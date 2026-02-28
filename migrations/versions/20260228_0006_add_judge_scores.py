"""Add judge scoring outputs table

Revision ID: 20260228_0006
Revises: 20260228_0005
Create Date: 2026-02-28 02:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0006"
down_revision = "20260228_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "judge_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("judge_profile_id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=128), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("raw_response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], name=op.f("fk_judge_scores_submission_id_submissions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["judge_profile_id"], ["judge_profiles.id"], name=op.f("fk_judge_scores_judge_profile_id_judge_profiles"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_judge_scores")),
    )
    op.create_index(op.f("ix_judge_scores_submission_id"), "judge_scores", ["submission_id"], unique=False)
    op.create_index(op.f("ix_judge_scores_judge_profile_id"), "judge_scores", ["judge_profile_id"], unique=False)
    op.create_index(op.f("ix_judge_scores_checkpoint_id"), "judge_scores", ["checkpoint_id"], unique=False)
    op.create_index(op.f("ix_judge_scores_created_at"), "judge_scores", ["created_at"], unique=False)
    op.create_index(op.f("ix_judge_scores_updated_at"), "judge_scores", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_judge_scores_updated_at"), table_name="judge_scores")
    op.drop_index(op.f("ix_judge_scores_created_at"), table_name="judge_scores")
    op.drop_index(op.f("ix_judge_scores_checkpoint_id"), table_name="judge_scores")
    op.drop_index(op.f("ix_judge_scores_judge_profile_id"), table_name="judge_scores")
    op.drop_index(op.f("ix_judge_scores_submission_id"), table_name="judge_scores")
    op.drop_table("judge_scores")
