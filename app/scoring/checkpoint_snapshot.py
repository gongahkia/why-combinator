from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CheckpointSnapshot


async def capture_checkpoint_snapshot(
    session: AsyncSession,
    run_id: uuid.UUID,
    checkpoint_id: str,
    active_weights: dict[str, float],
    active_policies: dict[str, object],
) -> CheckpointSnapshot:
    snapshot = CheckpointSnapshot(
        run_id=run_id,
        checkpoint_id=checkpoint_id,
        captured_at=datetime.now(UTC),
        active_weights=active_weights,
        active_policies=active_policies,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot
