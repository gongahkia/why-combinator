from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.models import LeaderboardEntry, PenaltyEvent, Run, ScoreEvent, Submission

router = APIRouter(prefix="/runs", tags=["export"])


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _serialize_submission(row: Submission) -> dict[str, object]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "agent_id": row.agent_id,
        "state": row.state.value,
        "value_hypothesis": row.value_hypothesis,
        "summary": row.summary,
        "accepted_at": row.accepted_at,
        "human_testing_required": row.human_testing_required,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _serialize_score_event(row: ScoreEvent) -> dict[str, object]:
    return {
        "id": row.id,
        "submission_id": row.submission_id,
        "checkpoint_id": row.checkpoint_id,
        "quality_score": row.quality_score,
        "novelty_score": row.novelty_score,
        "feasibility_score": row.feasibility_score,
        "criteria_score": row.criteria_score,
        "final_score": row.final_score,
        "payload": row.payload,
        "payload_checksum": row.payload_checksum,
        "created_at": row.created_at,
    }


def _serialize_penalty_event(row: PenaltyEvent) -> dict[str, object]:
    return {
        "id": row.id,
        "submission_id": row.submission_id,
        "checkpoint_id": row.checkpoint_id,
        "source": row.source,
        "penalty_type": row.penalty_type,
        "value": row.value,
        "explanation": row.explanation,
        "created_at": row.created_at,
    }


def _serialize_leaderboard_entry(row: LeaderboardEntry) -> dict[str, object]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "submission_id": row.submission_id,
        "rank": row.rank,
        "final_score": row.final_score,
        "tie_break_metadata": row.tie_break_metadata,
        "created_at": row.created_at,
    }


def _serialize_run(row: Run) -> dict[str, object]:
    return {
        "id": row.id,
        "challenge_id": row.challenge_id,
        "state": row.state.value,
        "started_at": row.started_at,
        "ended_at": row.ended_at,
        "config_snapshot": row.config_snapshot,
        "config_version": row.config_version,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def _stream_json_array(items: list[dict[str, object]]) -> AsyncIterator[bytes]:
    for index, item in enumerate(items):
        if index > 0:
            yield b","
        yield json.dumps(item, default=_json_default, separators=(",", ":")).encode("utf-8")


@router.get("/{run_id}/export")
async def export_run_bundle(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    submission_stmt: Select[tuple[Submission]] = (
        select(Submission).where(Submission.run_id == run_id).order_by(Submission.created_at.asc(), Submission.id.asc())
    )
    submissions = (await session.execute(submission_stmt)).scalars().all()

    score_stmt: Select[tuple[ScoreEvent]] = (
        select(ScoreEvent)
        .join(Submission, Submission.id == ScoreEvent.submission_id)
        .where(Submission.run_id == run_id)
        .order_by(ScoreEvent.created_at.asc(), ScoreEvent.id.asc())
    )
    score_events = (await session.execute(score_stmt)).scalars().all()

    penalty_stmt: Select[tuple[PenaltyEvent]] = (
        select(PenaltyEvent)
        .join(Submission, Submission.id == PenaltyEvent.submission_id)
        .where(Submission.run_id == run_id)
        .order_by(PenaltyEvent.created_at.asc(), PenaltyEvent.id.asc())
    )
    penalty_events = (await session.execute(penalty_stmt)).scalars().all()

    leaderboard_stmt: Select[tuple[LeaderboardEntry]] = (
        select(LeaderboardEntry)
        .where(LeaderboardEntry.run_id == run_id)
        .order_by(LeaderboardEntry.rank.asc(), LeaderboardEntry.id.asc())
    )
    leaderboard_entries = (await session.execute(leaderboard_stmt)).scalars().all()

    run_payload = _serialize_run(run)
    submission_payloads = [_serialize_submission(item) for item in submissions]
    score_payloads = [_serialize_score_event(item) for item in score_events]
    penalty_payloads = [_serialize_penalty_event(item) for item in penalty_events]
    leaderboard_payloads = [_serialize_leaderboard_entry(item) for item in leaderboard_entries]

    async def _stream() -> AsyncIterator[bytes]:
        yield b"{"
        yield b"\"run\":"
        yield json.dumps(run_payload, default=_json_default, separators=(",", ":")).encode("utf-8")

        yield b",\"submissions\":["
        async for chunk in _stream_json_array(submission_payloads):
            yield chunk
        yield b"]"

        yield b",\"scores\":["
        async for chunk in _stream_json_array(score_payloads):
            yield chunk
        yield b"]"

        yield b",\"penalties\":["
        async for chunk in _stream_json_array(penalty_payloads):
            yield chunk
        yield b"]"

        yield b",\"leaderboard\":["
        async for chunk in _stream_json_array(leaderboard_payloads):
            yield chunk
        yield b"]"
        yield b"}"

    return StreamingResponse(
        _stream(),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=run-{run_id}.json"},
    )
