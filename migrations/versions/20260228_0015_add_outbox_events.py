"""Add outbox events table

Revision ID: 20260228_0015
Revises: 20260228_0014
Create Date: 2026-02-28 13:55:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0015"
down_revision = "20260228_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stream_name", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publish_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
        sa.UniqueConstraint("event_key", name=op.f("uq_outbox_events_event_key")),
    )
    op.create_index(op.f("ix_outbox_events_stream_name"), "outbox_events", ["stream_name"], unique=False)
    op.create_index(op.f("ix_outbox_events_event_type"), "outbox_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_outbox_events_event_key"), "outbox_events", ["event_key"], unique=False)
    op.create_index(op.f("ix_outbox_events_published_at"), "outbox_events", ["published_at"], unique=False)
    op.create_index(op.f("ix_outbox_events_created_at"), "outbox_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_outbox_events_updated_at"), "outbox_events", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_outbox_events_updated_at"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_created_at"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_published_at"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_event_key"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_event_type"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_stream_name"), table_name="outbox_events")
    op.drop_table("outbox_events")
