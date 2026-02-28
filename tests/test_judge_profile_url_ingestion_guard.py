from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.judges import JudgeProfileURLRequest, register_judge_profile_url
from app.db.models import Challenge, JudgeProfile


@pytest.mark.asyncio
async def test_judge_profile_url_ingestion_blocks_private_network_targets(session: AsyncSession) -> None:
    challenge = Challenge(
        title="URL ingestion guard test",
        prompt="Build a judge panel from external profile definitions.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.commit()

    payload = JudgeProfileURLRequest(url="http://127.0.0.1/profiles.yaml")
    fake_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=None)))

    with pytest.raises(HTTPException) as exc_info:
        await register_judge_profile_url(challenge.id, payload, fake_request, session)
    assert exc_info.value.status_code == 422
    assert str(exc_info.value.detail).startswith("url not allowed:")

    profiles_stmt: Select[tuple[JudgeProfile]] = select(JudgeProfile).where(JudgeProfile.challenge_id == challenge.id)
    profiles = (await session.execute(profiles_stmt)).scalars().all()
    assert profiles == []
