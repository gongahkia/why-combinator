"""Add per-challenge API keys table

Revision ID: 20260228_0011
Revises: 20260228_0010
Create Date: 2026-02-28 04:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0011"
down_revision = "20260228_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "challenge_api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.Uuid(), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_last4", sa.String(length=4), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["challenge_id"], ["challenges.id"], name=op.f("fk_challenge_api_keys_challenge_id_challenges"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_challenge_api_keys")),
    )
    op.create_index(op.f("ix_challenge_api_keys_challenge_id"), "challenge_api_keys", ["challenge_id"], unique=False)
    op.create_index(op.f("ix_challenge_api_keys_key_hash"), "challenge_api_keys", ["key_hash"], unique=False)
    op.create_index(op.f("ix_challenge_api_keys_is_active"), "challenge_api_keys", ["is_active"], unique=False)
    op.create_index(op.f("ix_challenge_api_keys_created_at"), "challenge_api_keys", ["created_at"], unique=False)
    op.create_index(op.f("ix_challenge_api_keys_updated_at"), "challenge_api_keys", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_challenge_api_keys_updated_at"), table_name="challenge_api_keys")
    op.drop_index(op.f("ix_challenge_api_keys_created_at"), table_name="challenge_api_keys")
    op.drop_index(op.f("ix_challenge_api_keys_is_active"), table_name="challenge_api_keys")
    op.drop_index(op.f("ix_challenge_api_keys_key_hash"), table_name="challenge_api_keys")
    op.drop_index(op.f("ix_challenge_api_keys_challenge_id"), table_name="challenge_api_keys")
    op.drop_table("challenge_api_keys")
