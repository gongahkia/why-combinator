"""Add immutable payload checksum to score events

Revision ID: 20260228_0012
Revises: 20260228_0011
Create Date: 2026-02-28 05:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0012"
down_revision = "20260228_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("score_events", sa.Column("payload_checksum", sa.String(length=128), nullable=False, server_default=""))
    op.create_index(op.f("ix_score_events_payload_checksum"), "score_events", ["payload_checksum"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_score_events_payload_checksum"), table_name="score_events")
    op.drop_column("score_events", "payload_checksum")
