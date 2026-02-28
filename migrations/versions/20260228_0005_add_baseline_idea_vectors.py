"""Add baseline idea vectors table

Revision ID: 20260228_0005
Revises: 20260228_0004
Create Date: 2026-02-28 01:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0005"
down_revision = "20260228_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "baseline_idea_vectors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("idea_index", sa.Integer(), nullable=False),
        sa.Column("idea_text", sa.Text(), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_baseline_idea_vectors_run_id_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_baseline_idea_vectors")),
    )
    op.create_index(op.f("ix_baseline_idea_vectors_run_id"), "baseline_idea_vectors", ["run_id"], unique=False)
    op.create_index(op.f("ix_baseline_idea_vectors_created_at"), "baseline_idea_vectors", ["created_at"], unique=False)
    op.create_index(op.f("ix_baseline_idea_vectors_updated_at"), "baseline_idea_vectors", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_baseline_idea_vectors_updated_at"), table_name="baseline_idea_vectors")
    op.drop_index(op.f("ix_baseline_idea_vectors_created_at"), table_name="baseline_idea_vectors")
    op.drop_index(op.f("ix_baseline_idea_vectors_run_id"), table_name="baseline_idea_vectors")
    op.drop_table("baseline_idea_vectors")
