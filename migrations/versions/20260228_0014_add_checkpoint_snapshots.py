"""Add checkpoint snapshots table

Revision ID: 20260228_0014
Revises: 20260228_0013
Create Date: 2026-02-28 05:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0014"
down_revision = "20260228_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkpoint_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=128), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_weights", sa.JSON(), nullable=False),
        sa.Column("active_policies", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_checkpoint_snapshots_run_id_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_checkpoint_snapshots")),
    )
    op.create_index(op.f("ix_checkpoint_snapshots_run_id"), "checkpoint_snapshots", ["run_id"], unique=False)
    op.create_index(op.f("ix_checkpoint_snapshots_checkpoint_id"), "checkpoint_snapshots", ["checkpoint_id"], unique=False)
    op.create_index(op.f("ix_checkpoint_snapshots_captured_at"), "checkpoint_snapshots", ["captured_at"], unique=False)
    op.create_index(op.f("ix_checkpoint_snapshots_created_at"), "checkpoint_snapshots", ["created_at"], unique=False)
    op.create_index(op.f("ix_checkpoint_snapshots_updated_at"), "checkpoint_snapshots", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_checkpoint_snapshots_updated_at"), table_name="checkpoint_snapshots")
    op.drop_index(op.f("ix_checkpoint_snapshots_created_at"), table_name="checkpoint_snapshots")
    op.drop_index(op.f("ix_checkpoint_snapshots_captured_at"), table_name="checkpoint_snapshots")
    op.drop_index(op.f("ix_checkpoint_snapshots_checkpoint_id"), table_name="checkpoint_snapshots")
    op.drop_index(op.f("ix_checkpoint_snapshots_run_id"), table_name="checkpoint_snapshots")
    op.drop_table("checkpoint_snapshots")
