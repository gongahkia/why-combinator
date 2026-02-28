from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.challenges import ChallengeCreateRequest, create_challenge
from app.api.leaderboard import get_leaderboard
from app.api.runs import start_run
from app.api.submissions import SubmissionCreateRequest, create_submission
from app.db.enums import AgentRole
from app.db.models import Agent
from app.orchestrator.jobs import run_hacker_job
from app.scoring.checkpoint import run_checkpoint_scoring_worker


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str | int] = {}
        self.published: list[tuple[str, str]] = []

    async def setnx(self, key: str, value: int) -> bool:
        if key in self.kv:
            return False
        self.kv[key] = value
        return True

    async def publish(self, channel: str, payload: str) -> int:
        self.published.append((channel, payload))
        return 1


@pytest.mark.asyncio
async def test_end_to_end_run_flow_challenge_to_leaderboard(session: AsyncSession) -> None:
    challenge_response = await create_challenge(
        ChallengeCreateRequest(
            title="E2E hackathon flow",
            prompt="Build an MVP that triages incident alerts for engineering teams.",
            iteration_window_seconds=1800,
            minimum_quality_threshold=0.0,
            risk_appetite="balanced",
            complexity_slider=0.5,
        ),
        _rate_limit=None,
        session=session,
    )

    fake_redis = _FakeAsyncRedis()
    fake_settings = SimpleNamespace(default_run_budget_units=100, artifact_storage_path="/tmp/hackathon-artifacts")
    fake_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=fake_redis, settings=fake_settings)))
    run_response = await start_run(
        challenge_response.id,
        request=fake_request,
        _rate_limit=None,
        session=session,
    )

    # Agent execution phase (runner may be disabled in local test environment).
    hacker_execution = run_hacker_job(str(run_response.id), trace_id="e2e-trace")
    assert hacker_execution["status"] in {"runner-disabled", "completed", "timeout"}

    agent = Agent(run_id=run_response.id, role=AgentRole.HACKER, name="e2e-agent")
    session.add(agent)
    await session.commit()
    await session.refresh(agent)

    await create_submission(
        run_response.id,
        SubmissionCreateRequest(
            agent_id=agent.id,
            value_hypothesis="Automated incident triage should cut acknowledgment time by 30 percent.",
        ),
        idempotency_key=None,
        session=session,
    )

    await run_checkpoint_scoring_worker(
        session,
        run_response.id,
        trace_id="e2e-trace",
        score_time=datetime(2026, 2, 28, 0, 0, tzinfo=UTC),
    )

    leaderboard = await get_leaderboard(run_response.id, session=session)
    assert leaderboard.run_id == run_response.id
    assert len(leaderboard.items) >= 1
