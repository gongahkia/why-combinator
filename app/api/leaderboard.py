from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.models import JudgeScore, LeaderboardEntry, PenaltyEvent, Run, ScoreEvent
from app.leaderboard.cache import read_leaderboard_scoreboard_cache

router = APIRouter(prefix="/runs", tags=["leaderboard"])


class PenaltySnippet(BaseModel):
    penalty_type: str
    value: float
    explanation: str


class LeaderboardItemResponse(BaseModel):
    rank: int
    submission_id: uuid.UUID
    final_score: float
    score_breakdown: dict[str, object]
    active_penalties: list[PenaltySnippet]
    judge_rationale_snippets: list[str]
    tie_break_metadata: dict[str, object]


class LeaderboardResponse(BaseModel):
    run_id: uuid.UUID
    generated_at: datetime
    items: list[LeaderboardItemResponse]


@router.get("/{run_id}/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> LeaderboardResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    entry_rows: list[tuple[int, uuid.UUID, float, dict[str, object]]] = []
    cached_entries = read_leaderboard_scoreboard_cache(run_id)
    if cached_entries is not None:
        for row in cached_entries:
            try:
                rank = int(row["rank"])
                submission_id = uuid.UUID(str(row["submission_id"]))
                final_score = float(row["final_score"])
                metadata = row.get("tie_break_metadata")
                tie_break_metadata = metadata if isinstance(metadata, dict) else {}
            except (KeyError, TypeError, ValueError):
                entry_rows = []
                break
            entry_rows.append((rank, submission_id, final_score, tie_break_metadata))

    if not entry_rows:
        entry_stmt: Select[tuple[LeaderboardEntry]] = (
            select(LeaderboardEntry).where(LeaderboardEntry.run_id == run_id).order_by(LeaderboardEntry.rank.asc())
        )
        entries = (await session.execute(entry_stmt)).scalars().all()
        entry_rows = [
            (
                entry.rank,
                entry.submission_id,
                entry.final_score,
                entry.tie_break_metadata,
            )
            for entry in entries
        ]

    items: list[LeaderboardItemResponse] = []
    for rank, submission_id, final_score, tie_break_metadata in entry_rows:
        score_stmt: Select[tuple[ScoreEvent]] = (
            select(ScoreEvent)
            .where(ScoreEvent.submission_id == submission_id)
            .order_by(ScoreEvent.created_at.desc())
            .limit(1)
        )
        latest_score = (await session.execute(score_stmt)).scalar_one_or_none()

        penalty_stmt: Select[tuple[PenaltyEvent]] = (
            select(PenaltyEvent).where(PenaltyEvent.submission_id == submission_id).order_by(PenaltyEvent.created_at.desc())
        )
        penalties = (await session.execute(penalty_stmt)).scalars().all()

        judge_stmt: Select[tuple[JudgeScore]] = (
            select(JudgeScore).where(JudgeScore.submission_id == submission_id).order_by(JudgeScore.created_at.desc())
        )
        judge_scores = (await session.execute(judge_stmt)).scalars().all()

        items.append(
            LeaderboardItemResponse(
                rank=rank,
                submission_id=submission_id,
                final_score=final_score,
                score_breakdown={} if latest_score is None else latest_score.payload,
                active_penalties=[
                    PenaltySnippet(
                        penalty_type=penalty.penalty_type,
                        value=penalty.value,
                        explanation=penalty.explanation,
                    )
                    for penalty in penalties
                ],
                judge_rationale_snippets=[row.rationale[:300] for row in judge_scores[:3]],
                tie_break_metadata=tie_break_metadata,
            )
        )

    return LeaderboardResponse(
        run_id=run_id,
        generated_at=datetime.now(UTC),
        items=items,
    )
