"""Add human testing required flag to submissions

Revision ID: 20260228_0008
Revises: 20260228_0007
Create Date: 2026-02-28 03:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0008"
down_revision = "20260228_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "submissions",
        sa.Column("human_testing_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("submissions", "human_testing_required")
