from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.models import JudgeScore, LeaderboardEntry, PenaltyEvent, Run, ScoreEvent
from app.leaderboard.cache import (
    read_leaderboard_cursor_snapshot,
    read_leaderboard_scoreboard_cache,
    write_leaderboard_cursor_snapshot,
)

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


class PaginatedLeaderboardResponse(BaseModel):
    run_id: uuid.UUID
    generated_at: datetime
    items: list[LeaderboardItemResponse]
    next_cursor: str | None
    has_more: bool


LeaderboardRow = tuple[int, uuid.UUID, float, dict[str, object]]


def _parse_entry_rows(cached_entries: list[dict[str, object]]) -> list[LeaderboardRow]:
    entry_rows: list[LeaderboardRow] = []
    for row in cached_entries:
        try:
            rank = int(row["rank"])
            submission_id = uuid.UUID(str(row["submission_id"]))
            final_score = float(row["final_score"])
            metadata = row.get("tie_break_metadata")
            tie_break_metadata = metadata if isinstance(metadata, dict) else {}
        except (KeyError, TypeError, ValueError):
            return []
        entry_rows.append((rank, submission_id, final_score, tie_break_metadata))
    return entry_rows


def _serialize_entry_rows(entry_rows: list[LeaderboardRow]) -> list[dict[str, object]]:
    return [
        {
            "rank": rank,
            "submission_id": str(submission_id),
            "final_score": final_score,
            "tie_break_metadata": tie_break_metadata,
        }
        for rank, submission_id, final_score, tie_break_metadata in entry_rows
    ]


def _encode_leaderboard_cursor(run_id: uuid.UUID, snapshot_id: str, offset: int) -> str:
    payload = {"run_id": str(run_id), "snapshot_id": snapshot_id, "offset": offset}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_leaderboard_cursor(cursor: str) -> dict[str, object]:
    padding = "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(cursor + padding)
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid leaderboard cursor") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid leaderboard cursor")
    return payload


async def _load_entry_rows(session: AsyncSession, run_id: uuid.UUID) -> list[LeaderboardRow]:
    cached_entries = read_leaderboard_scoreboard_cache(run_id)
    if cached_entries is not None:
        parsed_cached = _parse_entry_rows(cached_entries)
        if parsed_cached:
            return parsed_cached

    entry_stmt: Select[tuple[LeaderboardEntry]] = (
        select(LeaderboardEntry).where(LeaderboardEntry.run_id == run_id).order_by(LeaderboardEntry.rank.asc())
    )
    entries = (await session.execute(entry_stmt)).scalars().all()
    return [
        (
            entry.rank,
            entry.submission_id,
            entry.final_score,
            entry.tie_break_metadata,
        )
        for entry in entries
    ]


async def _build_leaderboard_items(
    session: AsyncSession,
    entry_rows: list[LeaderboardRow],
) -> list[LeaderboardItemResponse]:
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
    return items


@router.get("/{run_id}/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> LeaderboardResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    entry_rows = await _load_entry_rows(session, run_id)
    items = await _build_leaderboard_items(session, entry_rows)

    return LeaderboardResponse(
        run_id=run_id,
        generated_at=datetime.now(UTC),
        items=items,
    )


@router.get("/{run_id}/leaderboard/paginated", response_model=PaginatedLeaderboardResponse)
async def get_leaderboard_paginated(
    run_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedLeaderboardResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    snapshot_id: str
    offset: int
    snapshot_rows: list[LeaderboardRow]

    if cursor is None:
        snapshot_rows = await _load_entry_rows(session, run_id)
        snapshot_id = uuid.uuid4().hex
        write_leaderboard_cursor_snapshot(run_id, snapshot_id, _serialize_entry_rows(snapshot_rows))
        offset = 0
    else:
        payload = _decode_leaderboard_cursor(cursor)
        payload_run_id = str(payload.get("run_id", "")).strip()
        snapshot_id = str(payload.get("snapshot_id", "")).strip()
        offset_raw = payload.get("offset")
        if payload_run_id != str(run_id) or not snapshot_id or not isinstance(offset_raw, int) or offset_raw < 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid leaderboard cursor")

        snapshot_payload = read_leaderboard_cursor_snapshot(run_id, snapshot_id)
        if snapshot_payload is None:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="leaderboard cursor expired")
        snapshot_rows = _parse_entry_rows(snapshot_payload)
        if not snapshot_rows and snapshot_payload:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="leaderboard cursor expired")
        offset = offset_raw

    page_rows = snapshot_rows[offset : offset + limit]
    items = await _build_leaderboard_items(session, page_rows)

    next_offset = offset + len(page_rows)
    has_more = next_offset < len(snapshot_rows)
    next_cursor = _encode_leaderboard_cursor(run_id, snapshot_id, next_offset) if has_more else None

    return PaginatedLeaderboardResponse(
        run_id=run_id,
        generated_at=datetime.now(UTC),
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
    )
