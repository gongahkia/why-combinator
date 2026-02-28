from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import CheckpointSnapshot, LeaderboardEntry, Run

router = APIRouter(prefix="/runs", tags=["realtime"])


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def load_realtime_stream_interval_seconds() -> float:
    return max(0.25, _env_float("REALTIME_STREAM_INTERVAL_SECONDS", 2.0))


def load_realtime_stream_max_entries() -> int:
    return max(1, _env_int("REALTIME_STREAM_MAX_ENTRIES", 25))


def _build_leaderboard_index(rows: list[dict[str, object]]) -> dict[str, tuple[int, float]]:
    index: dict[str, tuple[int, float]] = {}
    for row in rows:
        submission_id = str(row["submission_id"])
        index[submission_id] = (int(row["rank"]), float(row["final_score"]))
    return index


def compute_leaderboard_deltas(
    previous: dict[str, tuple[int, float]],
    current_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    current = _build_leaderboard_index(current_rows)
    deltas: list[dict[str, object]] = []

    for submission_id, (rank, final_score) in current.items():
        previous_value = previous.get(submission_id)
        if previous_value is None:
            deltas.append(
                {
                    "submission_id": submission_id,
                    "change_type": "added",
                    "rank": rank,
                    "final_score": round(final_score, 6),
                    "rank_delta": None,
                    "score_delta": None,
                }
            )
            continue

        previous_rank, previous_score = previous_value
        rank_delta = rank - previous_rank
        score_delta = round(final_score - previous_score, 6)
        if rank_delta != 0 or abs(score_delta) > 1e-9:
            deltas.append(
                {
                    "submission_id": submission_id,
                    "change_type": "updated",
                    "rank": rank,
                    "final_score": round(final_score, 6),
                    "rank_delta": rank_delta,
                    "score_delta": score_delta,
                }
            )

    for submission_id, (rank, final_score) in previous.items():
        if submission_id in current:
            continue
        deltas.append(
            {
                "submission_id": submission_id,
                "change_type": "removed",
                "rank": rank,
                "final_score": round(final_score, 6),
                "rank_delta": None,
                "score_delta": None,
            }
        )

    deltas.sort(
        key=lambda row: (
            {"updated": 0, "added": 1, "removed": 2}.get(str(row.get("change_type")), 3),
            -abs(float(row.get("score_delta") or 0.0)),
            str(row["submission_id"]),
        )
    )
    return deltas


def build_realtime_stream_payload(
    state: dict[str, object],
    previous_index: dict[str, tuple[int, float]],
) -> tuple[dict[str, object], dict[str, tuple[int, float]]]:
    leaderboard_rows = state["leaderboard"] if isinstance(state.get("leaderboard"), list) else []
    deltas = compute_leaderboard_deltas(previous_index, leaderboard_rows)
    current_index = _build_leaderboard_index(leaderboard_rows)
    payload = {
        "event": "checkpoint_update",
        **state,
        "leaderboard_deltas": deltas,
    }
    return payload, current_index


def format_sse_event(event: str, data: dict[str, object]) -> str:
    encoded = json.dumps(data, separators=(",", ":"), default=str)
    return f"event: {event}\\ndata: {encoded}\\n\\n"


async def fetch_realtime_run_state(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    max_entries: int,
) -> dict[str, object]:
    run = await session.get(Run, run_id)
    if run is None:
        raise ValueError("run not found")

    checkpoint_stmt: Select[tuple[CheckpointSnapshot]] = (
        select(CheckpointSnapshot)
        .where(CheckpointSnapshot.run_id == run_id)
        .order_by(desc(CheckpointSnapshot.captured_at))
        .limit(1)
    )
    checkpoint = (await session.execute(checkpoint_stmt)).scalar_one_or_none()

    leaderboard_stmt: Select[tuple[LeaderboardEntry]] = (
        select(LeaderboardEntry)
        .where(LeaderboardEntry.run_id == run_id)
        .order_by(LeaderboardEntry.rank.asc())
        .limit(max_entries)
    )
    leaderboard_rows = (await session.execute(leaderboard_stmt)).scalars().all()

    return {
        "run_id": str(run_id),
        "generated_at": datetime.now(UTC).isoformat(),
        "checkpoint": None
        if checkpoint is None
        else {
            "checkpoint_id": checkpoint.checkpoint_id,
            "captured_at": checkpoint.captured_at.isoformat(),
            "active_weights": checkpoint.active_weights,
            "active_policies": checkpoint.active_policies,
        },
        "leaderboard": [
            {
                "rank": row.rank,
                "submission_id": str(row.submission_id),
                "final_score": round(float(row.final_score), 6),
                "tie_break_metadata": row.tie_break_metadata,
            }
            for row in leaderboard_rows
        ],
    }


@router.websocket("/{run_id}/realtime/ws")
async def stream_run_realtime_updates(websocket: WebSocket, run_id: str) -> None:
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    session_factory: async_sessionmaker[AsyncSession] = websocket.app.state.db_session_factory
    interval_seconds = load_realtime_stream_interval_seconds()
    max_entries = load_realtime_stream_max_entries()
    previous_index: dict[str, tuple[int, float]] = {}

    try:
        while True:
            async with session_factory() as session:
                try:
                    state = await fetch_realtime_run_state(session, run_uuid, max_entries=max_entries)
                except ValueError:
                    await websocket.send_json(
                        {
                            "event": "error",
                            "detail": "run not found",
                            "run_id": run_id,
                        }
                    )
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return

            payload, previous_index = build_realtime_stream_payload(state, previous_index)

            await websocket.send_json(payload)
            await asyncio.sleep(interval_seconds)
    except WebSocketDisconnect:
        return


@router.get("/{run_id}/realtime/sse")
async def stream_run_realtime_updates_sse(
    run_id: uuid.UUID,
    request: Request,
) -> StreamingResponse:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.db_session_factory
    max_entries = load_realtime_stream_max_entries()
    interval_seconds = load_realtime_stream_interval_seconds()

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    async def _stream() -> AsyncIterator[str]:
        previous_index: dict[str, tuple[int, float]] = {}
        while True:
            if await request.is_disconnected():
                break
            async with session_factory() as session:
                state = await fetch_realtime_run_state(session, run_id, max_entries=max_entries)
            payload, previous_index = build_realtime_stream_payload(state, previous_index)
            yield format_sse_event("checkpoint_update", payload)
            await asyncio.sleep(interval_seconds)

    return StreamingResponse(_stream(), media_type="text/event-stream")
