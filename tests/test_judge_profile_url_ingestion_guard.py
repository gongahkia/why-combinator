from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.judges import JudgeProfileURLRequest, register_judge_profile_url
from app.db.models import Challenge, JudgeProfile


class _FakeURLCacheRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.kv.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:  # noqa: ARG002
        self.kv[key] = value
        return True


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


@pytest.mark.asyncio
async def test_judge_profile_url_ingestion_blocks_private_redirect_chain_targets(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenge = Challenge(
        title="URL redirect chain guard test",
        prompt="Block redirect chains that resolve to private network URLs.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.commit()

    payload = JudgeProfileURLRequest(url="https://example.com/profiles.yaml")
    fake_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=_FakeURLCacheRedis())))

    monkeypatch.setattr(
        "app.ingest.url_fetch._resolve_effective_url",
        lambda url, connect_timeout_seconds, read_timeout_seconds, max_redirects: "http://127.0.0.1/private.yaml",  # noqa: ARG005
    )

    with pytest.raises(HTTPException) as exc_info:
        await register_judge_profile_url(challenge.id, payload, fake_request, session)
    assert exc_info.value.status_code == 422
    assert str(exc_info.value.detail).startswith("url fetch failed: redirect blocked by URL sanitization:")

    profiles_stmt: Select[tuple[JudgeProfile]] = select(JudgeProfile).where(JudgeProfile.challenge_id == challenge.id)
    profiles = (await session.execute(profiles_stmt)).scalars().all()
    assert profiles == []
