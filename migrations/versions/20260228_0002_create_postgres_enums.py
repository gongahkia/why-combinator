"""Create postgres enum types for state and artifact fields

Revision ID: 20260228_0002
Revises: 20260228_0001
Create Date: 2026-02-28 00:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260228_0002"
down_revision = "20260228_0001"
branch_labels = None
depends_on = None

run_state_enum = postgresql.ENUM(
    "created",
    "running",
    "canceling",
    "completed",
    "canceled",
    "failed",
    name="run_state",
)
agent_role_enum = postgresql.ENUM("hacker", "subagent", "judge", name="agent_role")
submission_state_enum = postgresql.ENUM("pending", "scored", "accepted", "rejected", name="submission_state")
artifact_type_enum = postgresql.ENUM("web_bundle", "cli_package", "api_service", "notebook", name="artifact_type")


def upgrade() -> None:
    bind = op.get_bind()

    run_state_enum.create(bind, checkfirst=True)
    agent_role_enum.create(bind, checkfirst=True)
    submission_state_enum.create(bind, checkfirst=True)
    artifact_type_enum.create(bind, checkfirst=True)

    op.alter_column(
        "runs",
        "state",
        existing_type=sa.String(length=32),
        type_=sa.Enum(name="run_state"),
        postgresql_using="state::run_state",
        existing_nullable=False,
    )
    op.alter_column(
        "agents",
        "role",
        existing_type=sa.String(length=32),
        type_=sa.Enum(name="agent_role"),
        postgresql_using="role::agent_role",
        existing_nullable=False,
    )
    op.alter_column(
        "submissions",
        "state",
        existing_type=sa.String(length=32),
        type_=sa.Enum(name="submission_state"),
        postgresql_using="state::submission_state",
        existing_nullable=False,
    )
    op.alter_column(
        "artifacts",
        "artifact_type",
        existing_type=sa.String(length=64),
        type_=sa.Enum(name="artifact_type"),
        postgresql_using="artifact_type::artifact_type",
        existing_nullable=False,
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.alter_column(
        "artifacts",
        "artifact_type",
        existing_type=sa.Enum(name="artifact_type"),
        type_=sa.String(length=64),
        postgresql_using="artifact_type::text",
        existing_nullable=False,
    )
    op.alter_column(
        "submissions",
        "state",
        existing_type=sa.Enum(name="submission_state"),
        type_=sa.String(length=32),
        postgresql_using="state::text",
        existing_nullable=False,
    )
    op.alter_column(
        "agents",
        "role",
        existing_type=sa.Enum(name="agent_role"),
        type_=sa.String(length=32),
        postgresql_using="role::text",
        existing_nullable=False,
    )
    op.alter_column(
        "runs",
        "state",
        existing_type=sa.Enum(name="run_state"),
        type_=sa.String(length=32),
        postgresql_using="state::text",
        existing_nullable=False,
    )

    artifact_type_enum.drop(bind, checkfirst=True)
    submission_state_enum.drop(bind, checkfirst=True)
    agent_role_enum.drop(bind, checkfirst=True)
    run_state_enum.drop(bind, checkfirst=True)
