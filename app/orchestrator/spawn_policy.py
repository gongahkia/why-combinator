from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SubagentEdge


@dataclass(frozen=True)
class SpawnPolicy:
    max_depth: int
    max_children: int


@dataclass(frozen=True)
class SpawnPolicyDecision:
    allowed: bool
    reason: str
    parent_depth: int
    existing_children: int


def load_spawn_policy_from_env() -> SpawnPolicy:
    return SpawnPolicy(
        max_depth=int(os.getenv("SUBAGENT_MAX_DEPTH", "3")),
        max_children=int(os.getenv("SUBAGENT_MAX_CHILDREN", "5")),
    )


async def evaluate_spawn_policy(
    session: AsyncSession,
    run_id: uuid.UUID,
    parent_agent_id: uuid.UUID,
    policy: SpawnPolicy | None = None,
) -> SpawnPolicyDecision:
    active_policy = policy or load_spawn_policy_from_env()

    children_stmt: Select[tuple[int]] = select(func.count()).select_from(SubagentEdge).where(
        SubagentEdge.run_id == run_id,
        SubagentEdge.parent_agent_id == parent_agent_id,
    )
    existing_children = (await session.execute(children_stmt)).scalar_one()

    depth_stmt: Select[tuple[int | None]] = select(func.max(SubagentEdge.depth)).where(
        SubagentEdge.run_id == run_id,
        SubagentEdge.child_agent_id == parent_agent_id,
    )
    parent_depth = (await session.execute(depth_stmt)).scalar_one() or 0
    next_depth = parent_depth + 1

    if existing_children >= active_policy.max_children:
        return SpawnPolicyDecision(
            allowed=False,
            reason="max_children_exceeded",
            parent_depth=parent_depth,
            existing_children=existing_children,
        )
    if next_depth > active_policy.max_depth:
        return SpawnPolicyDecision(
            allowed=False,
            reason="max_depth_exceeded",
            parent_depth=parent_depth,
            existing_children=existing_children,
        )
    return SpawnPolicyDecision(
        allowed=True,
        reason="ok",
        parent_depth=parent_depth,
        existing_children=existing_children,
    )
