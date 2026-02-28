from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CheckpointSnapshot, ScoringWeightConfig


@dataclass(frozen=True)
class ConfigTimelineEntry:
    timestamp: datetime
    source: str
    weights: dict[str, float]
    policies: dict[str, object]


async def reconstruct_effective_config_timeline(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> list[ConfigTimelineEntry]:
    weight_stmt: Select[tuple[ScoringWeightConfig]] = (
        select(ScoringWeightConfig)
        .where(ScoringWeightConfig.run_id == run_id)
        .order_by(ScoringWeightConfig.effective_from.asc())
    )
    weight_rows = (await session.execute(weight_stmt)).scalars().all()

    snapshot_stmt: Select[tuple[CheckpointSnapshot]] = (
        select(CheckpointSnapshot)
        .where(CheckpointSnapshot.run_id == run_id)
        .order_by(CheckpointSnapshot.captured_at.asc())
    )
    snapshot_rows = (await session.execute(snapshot_stmt)).scalars().all()

    timeline: list[ConfigTimelineEntry] = []
    for row in weight_rows:
        timeline.append(
            ConfigTimelineEntry(
                timestamp=row.effective_from,
                source="weight_config",
                weights={key: float(value) for key, value in row.weights.items()},
                policies={},
            )
        )
    for row in snapshot_rows:
        timeline.append(
            ConfigTimelineEntry(
                timestamp=row.captured_at,
                source="checkpoint_snapshot",
                weights=row.active_weights,
                policies=row.active_policies,
            )
        )
    timeline.sort(key=lambda item: (item.timestamp, item.source))
    return timeline


async def resolve_effective_config_at(
    session: AsyncSession,
    run_id: uuid.UUID,
    at_timestamp: datetime,
) -> ConfigTimelineEntry | None:
    timeline = await reconstruct_effective_config_timeline(session, run_id)
    effective_entries = [entry for entry in timeline if entry.timestamp <= at_timestamp]
    if not effective_entries:
        return None
    return effective_entries[-1]
