from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, RunState
from app.db.models import Agent, Challenge, Run
from app.orchestrator.spawn_policy import SpawnPolicy, evaluate_spawn_policy
from app.orchestrator.subagent_graph import persist_subagent_edge


@pytest.mark.asyncio
async def test_spawn_policy_enforces_max_children_and_max_depth(session: AsyncSession) -> None:
    challenge = Challenge(
        title="Spawn policy test",
        prompt="Build an MVP with selective subagent delegation.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, config_snapshot={})
    session.add(run)
    await session.flush()

    root = Agent(run_id=run.id, role=AgentRole.HACKER, name="root")
    child_a = Agent(run_id=run.id, role=AgentRole.SUBAGENT, name="child-a")
    child_b = Agent(run_id=run.id, role=AgentRole.SUBAGENT, name="child-b")
    grandchild = Agent(run_id=run.id, role=AgentRole.SUBAGENT, name="grandchild")
    session.add_all([root, child_a, child_b, grandchild])
    await session.flush()

    await persist_subagent_edge(session, run.id, root.id, child_a.id, depth=1)
    await persist_subagent_edge(session, run.id, root.id, child_b.id, depth=1)
    await session.commit()

    max_children_policy = SpawnPolicy(max_depth=3, max_children=2)
    children_decision = await evaluate_spawn_policy(session, run.id, root.id, policy=max_children_policy)
    assert children_decision.allowed is False
    assert children_decision.reason == "max_children_exceeded"

    max_depth_policy = SpawnPolicy(max_depth=1, max_children=5)
    depth_decision = await evaluate_spawn_policy(session, run.id, child_a.id, policy=max_depth_policy)
    assert depth_decision.allowed is False
    assert depth_decision.reason == "max_depth_exceeded"
