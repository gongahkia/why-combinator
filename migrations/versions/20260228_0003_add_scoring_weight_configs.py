"""Add scoring weight config timeline table

Revision ID: 20260228_0003
Revises: 20260228_0002
Create Date: 2026-02-28 00:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0003"
down_revision = "20260228_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scoring_weight_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("weights", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_scoring_weight_configs_run_id_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scoring_weight_configs")),
    )
    op.create_index(op.f("ix_scoring_weight_configs_run_id"), "scoring_weight_configs", ["run_id"], unique=False)
    op.create_index(
        op.f("ix_scoring_weight_configs_effective_from"), "scoring_weight_configs", ["effective_from"], unique=False
    )
    op.create_index(op.f("ix_scoring_weight_configs_created_at"), "scoring_weight_configs", ["created_at"], unique=False)
    op.create_index(op.f("ix_scoring_weight_configs_updated_at"), "scoring_weight_configs", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scoring_weight_configs_updated_at"), table_name="scoring_weight_configs")
    op.drop_index(op.f("ix_scoring_weight_configs_created_at"), table_name="scoring_weight_configs")
    op.drop_index(op.f("ix_scoring_weight_configs_effective_from"), table_name="scoring_weight_configs")
    op.drop_index(op.f("ix_scoring_weight_configs_run_id"), table_name="scoring_weight_configs")
    op.drop_table("scoring_weight_configs")
