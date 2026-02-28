from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SubmissionState
from app.db.models import LeaderboardEntry, PenaltyEvent, ScoreEvent, Submission


@dataclass(frozen=True)
class RankedSubmission:
    submission_id: uuid.UUID
    final_score: float
    accepted_at: datetime | None
    total_penalty: float
    tie_break_metadata: dict[str, object]


async def _latest_final_score(session: AsyncSession, submission_id: uuid.UUID) -> float | None:
    stmt: Select[tuple[ScoreEvent]] = (
        select(ScoreEvent).where(ScoreEvent.submission_id == submission_id).order_by(ScoreEvent.created_at.desc()).limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    return None if row is None else row.final_score


async def _total_penalty(session: AsyncSession, submission_id: uuid.UUID) -> float:
    stmt: Select[tuple[float]] = select(func.coalesce(func.sum(PenaltyEvent.value), 0.0)).where(
        PenaltyEvent.submission_id == submission_id
    )
    total = (await session.execute(stmt)).scalar_one()
    return round(float(total), 6)


async def materialize_leaderboard(session: AsyncSession, run_id: uuid.UUID) -> list[LeaderboardEntry]:
    await session.execute(delete(LeaderboardEntry).where(LeaderboardEntry.run_id == run_id))

    accepted_stmt: Select[tuple[Submission]] = select(Submission).where(
        Submission.run_id == run_id,
        Submission.state == SubmissionState.ACCEPTED,
    )
    submissions = (await session.execute(accepted_stmt)).scalars().all()

    ranked_candidates: list[RankedSubmission] = []
    for submission in submissions:
        score = await _latest_final_score(session, submission.id)
        if score is None:
            continue
        total_penalty = await _total_penalty(session, submission.id)
        tie_break_metadata = {
            "accepted_at": submission.accepted_at.isoformat() if submission.accepted_at else None,
            "total_penalty": total_penalty,
            "submission_id": str(submission.id),
        }
        ranked_candidates.append(
            RankedSubmission(
                submission_id=submission.id,
                final_score=score,
                accepted_at=submission.accepted_at,
                total_penalty=total_penalty,
                tie_break_metadata=tie_break_metadata,
            )
        )

    def _accepted_sort_key(value: RankedSubmission) -> datetime:
        return value.accepted_at if value.accepted_at is not None else datetime.max.replace(tzinfo=UTC)

    ranked_candidates.sort(
        key=lambda value: (
            -value.final_score,
            _accepted_sort_key(value),
            value.total_penalty,
            str(value.submission_id),
        )
    )

    entries: list[LeaderboardEntry] = []
    for index, candidate in enumerate(ranked_candidates, start=1):
        entry = LeaderboardEntry(
            run_id=run_id,
            submission_id=candidate.submission_id,
            rank=index,
            final_score=candidate.final_score,
            tie_break_metadata=candidate.tie_break_metadata,
        )
        session.add(entry)
        entries.append(entry)
    await session.flush()
    return entries
