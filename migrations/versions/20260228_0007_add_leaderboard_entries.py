"""Add leaderboard entries table

Revision ID: 20260228_0007
Revises: 20260228_0006
Create Date: 2026-02-28 02:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0007"
down_revision = "20260228_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leaderboard_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("tie_break_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_leaderboard_entries_run_id_runs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["submissions.id"], name=op.f("fk_leaderboard_entries_submission_id_submissions"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leaderboard_entries")),
    )
    op.create_index(op.f("ix_leaderboard_entries_run_id"), "leaderboard_entries", ["run_id"], unique=False)
    op.create_index(op.f("ix_leaderboard_entries_submission_id"), "leaderboard_entries", ["submission_id"], unique=False)
    op.create_index(op.f("ix_leaderboard_entries_rank"), "leaderboard_entries", ["rank"], unique=False)
    op.create_index(op.f("ix_leaderboard_entries_final_score"), "leaderboard_entries", ["final_score"], unique=False)
    op.create_index(op.f("ix_leaderboard_entries_created_at"), "leaderboard_entries", ["created_at"], unique=False)
    op.create_index(op.f("ix_leaderboard_entries_updated_at"), "leaderboard_entries", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_leaderboard_entries_updated_at"), table_name="leaderboard_entries")
    op.drop_index(op.f("ix_leaderboard_entries_created_at"), table_name="leaderboard_entries")
    op.drop_index(op.f("ix_leaderboard_entries_final_score"), table_name="leaderboard_entries")
    op.drop_index(op.f("ix_leaderboard_entries_rank"), table_name="leaderboard_entries")
    op.drop_index(op.f("ix_leaderboard_entries_submission_id"), table_name="leaderboard_entries")
    op.drop_index(op.f("ix_leaderboard_entries_run_id"), table_name="leaderboard_entries")
    op.drop_table("leaderboard_entries")
