"""Add artifact retention policy columns

Revision ID: 20260228_0016
Revises: 20260228_0015
Create Date: 2026-02-28 15:05:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0016"
down_revision = "20260228_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("challenges", sa.Column("artifact_ttl_override_seconds", sa.Integer(), nullable=True))
    op.add_column("artifacts", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_artifacts_expires_at"), "artifacts", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_artifacts_expires_at"), table_name="artifacts")
    op.drop_column("artifacts", "expires_at")
    op.drop_column("challenges", "artifact_ttl_override_seconds")
