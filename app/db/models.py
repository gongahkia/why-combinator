from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.enums import AgentRole, ArtifactType, RunState, SubmissionState


class Challenge(TimestampMixin, Base):
    __tablename__ = "challenges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    iteration_window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_quality_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    risk_appetite: Mapped[str] = mapped_column(String(32), nullable=False)
    complexity_slider: Mapped[float] = mapped_column(Float, nullable=False)

    runs: Mapped[list[Run]] = relationship(back_populates="challenge", cascade="all, delete-orphan")
    judge_profiles: Mapped[list[JudgeProfile]] = relationship(back_populates="challenge", cascade="all, delete-orphan")


class Run(TimestampMixin, Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    state: Mapped[RunState] = mapped_column(Enum(RunState, name="run_state"), nullable=False, default=RunState.CREATED, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    config_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    challenge: Mapped[Challenge] = relationship(back_populates="runs")
    agents: Mapped[list[Agent]] = relationship(back_populates="run", cascade="all, delete-orphan")
    edges: Mapped[list[SubagentEdge]] = relationship(back_populates="run", cascade="all, delete-orphan")
    submissions: Mapped[list[Submission]] = relationship(back_populates="run", cascade="all, delete-orphan")
    scoring_weight_configs: Mapped[list[ScoringWeightConfig]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    baseline_idea_vectors: Mapped[list[BaselineIdeaVector]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    leaderboard_entries: Mapped[list[LeaderboardEntry]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class BaselineIdeaVector(TimestampMixin, Base):
    __tablename__ = "baseline_idea_vectors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    idea_index: Mapped[int] = mapped_column(Integer, nullable=False)
    idea_text: Mapped[str] = mapped_column(Text, nullable=False)
    vector: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped[Run] = relationship(back_populates="baseline_idea_vectors")


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[AgentRole] = mapped_column(Enum(AgentRole, name="agent_role"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    run: Mapped[Run] = relationship(back_populates="agents")
    submissions: Mapped[list[Submission]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class SubagentEdge(TimestampMixin, Base):
    __tablename__ = "subagent_edges"
    __table_args__ = (UniqueConstraint("run_id", "parent_agent_id", "child_agent_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    child_agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    run: Mapped[Run] = relationship(back_populates="edges")


class Submission(TimestampMixin, Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    state: Mapped[SubmissionState] = mapped_column(
        Enum(SubmissionState, name="submission_state"), nullable=False, default=SubmissionState.PENDING, index=True
    )
    value_hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    human_testing_required: Mapped[bool] = mapped_column(default=False, nullable=False)

    run: Mapped[Run] = relationship(back_populates="submissions")
    agent: Mapped[Agent] = relationship(back_populates="submissions")
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    score_events: Mapped[list[ScoreEvent]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    penalty_events: Mapped[list[PenaltyEvent]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    judge_scores: Mapped[list[JudgeScore]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    leaderboard_entries: Mapped[list[LeaderboardEntry]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )


class Artifact(TimestampMixin, Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_type: Mapped[ArtifactType] = mapped_column(Enum(ArtifactType, name="artifact_type"), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    submission: Mapped[Submission] = relationship(back_populates="artifacts")


class ScoreEvent(TimestampMixin, Base):
    __tablename__ = "score_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    checkpoint_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False)
    feasibility_score: Mapped[float] = mapped_column(Float, nullable=False)
    criteria_score: Mapped[float] = mapped_column(Float, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    submission: Mapped[Submission] = relationship(back_populates="score_events")


class PenaltyEvent(TimestampMixin, Base):
    __tablename__ = "penalty_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    checkpoint_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    penalty_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    submission: Mapped[Submission] = relationship(back_populates="penalty_events")


class ScoringWeightConfig(TimestampMixin, Base):
    __tablename__ = "scoring_weight_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    weights: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)

    run: Mapped[Run] = relationship(back_populates="scoring_weight_configs")


class JudgeProfile(TimestampMixin, Base):
    __tablename__ = "judge_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scoring_style: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    head_judge: Mapped[bool] = mapped_column(default=False, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="inline_json")

    challenge: Mapped[Challenge] = relationship(back_populates="judge_profiles")
    judge_scores: Mapped[list[JudgeScore]] = relationship(back_populates="judge_profile", cascade="all, delete-orphan")


class JudgeScore(TimestampMixin, Base):
    __tablename__ = "judge_scores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    judge_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("judge_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    checkpoint_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    submission: Mapped[Submission] = relationship(back_populates="judge_scores")
    judge_profile: Mapped[JudgeProfile] = relationship(back_populates="judge_scores")


class LeaderboardEntry(TimestampMixin, Base):
    __tablename__ = "leaderboard_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    final_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    tie_break_metadata: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    run: Mapped[Run] = relationship(back_populates="leaderboard_entries")
    submission: Mapped[Submission] = relationship(back_populates="leaderboard_entries")


class IdempotencyKey(TimestampMixin, Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    response_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class ChallengeApiKey(TimestampMixin, Base):
    __tablename__ = "challenge_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)
