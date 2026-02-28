"""Add optimistic lock version for run config

Revision ID: 20260228_0010
Revises: 20260228_0009
Create Date: 2026-02-28 04:25:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0010"
down_revision = "20260228_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("config_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("runs", "config_version")
