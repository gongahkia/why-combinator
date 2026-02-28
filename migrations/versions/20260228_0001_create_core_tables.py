"""Create core normalized tables

Revision ID: 20260228_0001
Revises: 
Create Date: 2026-02-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260228_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("iteration_window_seconds", sa.Integer(), nullable=False),
        sa.Column("minimum_quality_threshold", sa.Float(), nullable=False),
        sa.Column("risk_appetite", sa.String(length=32), nullable=False),
        sa.Column("complexity_slider", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_challenges")),
    )
    op.create_index(op.f("ix_challenges_created_at"), "challenges", ["created_at"], unique=False)
    op.create_index(op.f("ix_challenges_updated_at"), "challenges", ["updated_at"], unique=False)

    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], name=op.f("fk_runs_challenge_id_challenges"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
    )
    op.create_index(op.f("ix_runs_challenge_id"), "runs", ["challenge_id"], unique=False)
    op.create_index(op.f("ix_runs_state"), "runs", ["state"], unique=False)
    op.create_index(op.f("ix_runs_created_at"), "runs", ["created_at"], unique=False)
    op.create_index(op.f("ix_runs_updated_at"), "runs", ["updated_at"], unique=False)

    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_agents_run_id_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agents")),
    )
    op.create_index(op.f("ix_agents_run_id"), "agents", ["run_id"], unique=False)
    op.create_index(op.f("ix_agents_role"), "agents", ["role"], unique=False)
    op.create_index(op.f("ix_agents_created_at"), "agents", ["created_at"], unique=False)
    op.create_index(op.f("ix_agents_updated_at"), "agents", ["updated_at"], unique=False)

    op.create_table(
        "subagent_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("parent_agent_id", sa.Uuid(), nullable=False),
        sa.Column("child_agent_id", sa.Uuid(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_subagent_edges_run_id_runs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_agent_id"], ["agents.id"], name=op.f("fk_subagent_edges_parent_agent_id_agents"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["child_agent_id"], ["agents.id"], name=op.f("fk_subagent_edges_child_agent_id_agents"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subagent_edges")),
        sa.UniqueConstraint("run_id", "parent_agent_id", "child_agent_id", name=op.f("uq_subagent_edges_run_id")),
    )
    op.create_index(op.f("ix_subagent_edges_run_id"), "subagent_edges", ["run_id"], unique=False)
    op.create_index(op.f("ix_subagent_edges_parent_agent_id"), "subagent_edges", ["parent_agent_id"], unique=False)
    op.create_index(op.f("ix_subagent_edges_child_agent_id"), "subagent_edges", ["child_agent_id"], unique=False)
    op.create_index(op.f("ix_subagent_edges_created_at"), "subagent_edges", ["created_at"], unique=False)
    op.create_index(op.f("ix_subagent_edges_updated_at"), "subagent_edges", ["updated_at"], unique=False)

    op.create_table(
        "submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("value_hypothesis", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_submissions_run_id_runs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], name=op.f("fk_submissions_agent_id_agents"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
    )
    op.create_index(op.f("ix_submissions_run_id"), "submissions", ["run_id"], unique=False)
    op.create_index(op.f("ix_submissions_agent_id"), "submissions", ["agent_id"], unique=False)
    op.create_index(op.f("ix_submissions_state"), "submissions", ["state"], unique=False)
    op.create_index(op.f("ix_submissions_created_at"), "submissions", ["created_at"], unique=False)
    op.create_index(op.f("ix_submissions_updated_at"), "submissions", ["updated_at"], unique=False)

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], name=op.f("fk_artifacts_submission_id_submissions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifacts")),
    )
    op.create_index(op.f("ix_artifacts_submission_id"), "artifacts", ["submission_id"], unique=False)
    op.create_index(op.f("ix_artifacts_artifact_type"), "artifacts", ["artifact_type"], unique=False)
    op.create_index(op.f("ix_artifacts_content_hash"), "artifacts", ["content_hash"], unique=False)
    op.create_index(op.f("ix_artifacts_created_at"), "artifacts", ["created_at"], unique=False)
    op.create_index(op.f("ix_artifacts_updated_at"), "artifacts", ["updated_at"], unique=False)

    op.create_table(
        "score_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=128), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("feasibility_score", sa.Float(), nullable=False),
        sa.Column("criteria_score", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], name=op.f("fk_score_events_submission_id_submissions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_score_events")),
    )
    op.create_index(op.f("ix_score_events_submission_id"), "score_events", ["submission_id"], unique=False)
    op.create_index(op.f("ix_score_events_checkpoint_id"), "score_events", ["checkpoint_id"], unique=False)
    op.create_index(op.f("ix_score_events_final_score"), "score_events", ["final_score"], unique=False)
    op.create_index(op.f("ix_score_events_created_at"), "score_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_score_events_updated_at"), "score_events", ["updated_at"], unique=False)

    op.create_table(
        "penalty_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=128), nullable=False),
        sa.Column("penalty_type", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], name=op.f("fk_penalty_events_submission_id_submissions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_penalty_events")),
    )
    op.create_index(op.f("ix_penalty_events_submission_id"), "penalty_events", ["submission_id"], unique=False)
    op.create_index(op.f("ix_penalty_events_checkpoint_id"), "penalty_events", ["checkpoint_id"], unique=False)
    op.create_index(op.f("ix_penalty_events_created_at"), "penalty_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_penalty_events_updated_at"), "penalty_events", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_penalty_events_updated_at"), table_name="penalty_events")
    op.drop_index(op.f("ix_penalty_events_created_at"), table_name="penalty_events")
    op.drop_index(op.f("ix_penalty_events_checkpoint_id"), table_name="penalty_events")
    op.drop_index(op.f("ix_penalty_events_submission_id"), table_name="penalty_events")
    op.drop_table("penalty_events")

    op.drop_index(op.f("ix_score_events_updated_at"), table_name="score_events")
    op.drop_index(op.f("ix_score_events_created_at"), table_name="score_events")
    op.drop_index(op.f("ix_score_events_final_score"), table_name="score_events")
    op.drop_index(op.f("ix_score_events_checkpoint_id"), table_name="score_events")
    op.drop_index(op.f("ix_score_events_submission_id"), table_name="score_events")
    op.drop_table("score_events")

    op.drop_index(op.f("ix_artifacts_updated_at"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_created_at"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_content_hash"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_artifact_type"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_submission_id"), table_name="artifacts")
    op.drop_table("artifacts")

    op.drop_index(op.f("ix_submissions_updated_at"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_created_at"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_state"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_agent_id"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_run_id"), table_name="submissions")
    op.drop_table("submissions")

    op.drop_index(op.f("ix_subagent_edges_updated_at"), table_name="subagent_edges")
    op.drop_index(op.f("ix_subagent_edges_created_at"), table_name="subagent_edges")
    op.drop_index(op.f("ix_subagent_edges_child_agent_id"), table_name="subagent_edges")
    op.drop_index(op.f("ix_subagent_edges_parent_agent_id"), table_name="subagent_edges")
    op.drop_index(op.f("ix_subagent_edges_run_id"), table_name="subagent_edges")
    op.drop_table("subagent_edges")

    op.drop_index(op.f("ix_agents_updated_at"), table_name="agents")
    op.drop_index(op.f("ix_agents_created_at"), table_name="agents")
    op.drop_index(op.f("ix_agents_role"), table_name="agents")
    op.drop_index(op.f("ix_agents_run_id"), table_name="agents")
    op.drop_table("agents")

    op.drop_index(op.f("ix_runs_updated_at"), table_name="runs")
    op.drop_index(op.f("ix_runs_created_at"), table_name="runs")
    op.drop_index(op.f("ix_runs_state"), table_name="runs")
    op.drop_index(op.f("ix_runs_challenge_id"), table_name="runs")
    op.drop_table("runs")

    op.drop_index(op.f("ix_challenges_updated_at"), table_name="challenges")
    op.drop_index(op.f("ix_challenges_created_at"), table_name="challenges")
    op.drop_table("challenges")
