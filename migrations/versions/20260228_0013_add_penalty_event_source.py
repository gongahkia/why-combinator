"""Add source field to penalty events

Revision ID: 20260228_0013
Revises: 20260228_0012
Create Date: 2026-02-28 05:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0013"
down_revision = "20260228_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("penalty_events", sa.Column("source", sa.String(length=64), nullable=False, server_default="system"))


def downgrade() -> None:
    op.drop_column("penalty_events", "source")
