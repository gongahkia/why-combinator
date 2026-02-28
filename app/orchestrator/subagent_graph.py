from __future__ import annotations

import uuid
from collections import defaultdict, deque

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SubagentEdge


class SubagentGraphValidationError(Exception):
    pass


async def _build_adjacency(session: AsyncSession, run_id: uuid.UUID) -> dict[uuid.UUID, set[uuid.UUID]]:
    stmt: Select[tuple[SubagentEdge]] = select(SubagentEdge).where(SubagentEdge.run_id == run_id)
    edges = (await session.execute(stmt)).scalars().all()
    adjacency: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for edge in edges:
        adjacency[edge.parent_agent_id].add(edge.child_agent_id)
    return adjacency


def _has_path(adjacency: dict[uuid.UUID, set[uuid.UUID]], start: uuid.UUID, target: uuid.UUID) -> bool:
    queue: deque[uuid.UUID] = deque([start])
    visited: set[uuid.UUID] = set()
    while queue:
        node = queue.popleft()
        if node == target:
            return True
        if node in visited:
            continue
        visited.add(node)
        queue.extend(adjacency.get(node, set()))
    return False


async def persist_subagent_edge(
    session: AsyncSession,
    run_id: uuid.UUID,
    parent_agent_id: uuid.UUID,
    child_agent_id: uuid.UUID,
    depth: int,
) -> SubagentEdge:
    if parent_agent_id == child_agent_id:
        raise SubagentGraphValidationError("self-referential edges are not allowed")

    adjacency = await _build_adjacency(session, run_id)
    if _has_path(adjacency, start=child_agent_id, target=parent_agent_id):
        raise SubagentGraphValidationError("edge would introduce a cycle in subagent graph")

    edge = SubagentEdge(
        run_id=run_id,
        parent_agent_id=parent_agent_id,
        child_agent_id=child_agent_id,
        depth=depth,
    )
    session.add(edge)
    await session.flush()
    return edge
