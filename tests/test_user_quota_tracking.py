from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace

import pytest
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.api.artifacts import upload_artifact
from app.api.challenges import ChallengeCreateRequest, create_challenge
from app.api.runs import start_run
from app.auth.quotas import reset_current_quota_user_id, set_current_quota_user_id
from app.db.enums import AgentRole, SubmissionState
from app.db.models import Agent, Submission, UserQuotaUsage


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str | int] = {}

    async def setnx(self, key: str, value: int) -> bool:
        if key in self.kv:
            return False
        self.kv[key] = value
        return True


@pytest.mark.asyncio
async def test_quota_tracking_counts_challenges_runs_and_artifact_storage(
    session: AsyncSession,
    tmp_path,
) -> None:
    quota_user_id = "user-quotas-1"
    quota_token = set_current_quota_user_id(quota_user_id)

    try:
        challenge = await create_challenge(
            ChallengeCreateRequest(
                title="Quota tracking challenge",
                prompt="Track per-user quotas for challenge, run, and artifact writes.",
                iteration_window_seconds=1200,
                minimum_quality_threshold=0.0,
                risk_appetite="balanced",
                complexity_slider=0.5,
            ),
            _rate_limit=None,
            session=session,
        )
    finally:
        reset_current_quota_user_id(quota_token)

    run_request = SimpleNamespace(
        state=SimpleNamespace(quota_user_id=quota_user_id),
        app=SimpleNamespace(
            state=SimpleNamespace(
                redis=_FakeAsyncRedis(),
                settings=SimpleNamespace(default_run_budget_units=100, artifact_storage_path=str(tmp_path)),
            )
        ),
    )
    run = await start_run(
        challenge.id,
        request=run_request,
        _rate_limit=None,
        session=session,
    )

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="quota-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Quota tracking should record storage usage bytes.",
        summary="Quota tracking submission.",
    )
    session.add(submission)
    await session.commit()

    artifact_request = SimpleNamespace(
        state=SimpleNamespace(quota_user_id=quota_user_id),
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(artifact_storage_path=str(tmp_path)))),
    )
    payload = b"quota-artifact-content"
    await upload_artifact(
        submission_id=submission.id,
        request=artifact_request,
        artifact_type="cli_package",
        file=UploadFile(filename="quota.txt", file=BytesIO(payload)),
        session=session,
    )

    quota_stmt: Select[tuple[UserQuotaUsage]] = select(UserQuotaUsage).where(UserQuotaUsage.quota_user_id == quota_user_id)
    usage = (await session.execute(quota_stmt)).scalar_one()

    assert usage.challenges_created == 1
    assert usage.runs_started == 1
    assert usage.artifact_storage_bytes == len(payload)
