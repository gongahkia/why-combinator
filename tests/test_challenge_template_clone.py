from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.challenges import ChallengeCreateRequest, clone_challenge, create_challenge
from app.auth.quotas import reset_current_quota_user_id, set_current_quota_user_id
from app.db.models import Challenge, JudgeProfile, UserQuotaUsage


@pytest.mark.asyncio
async def test_clone_challenge_copies_configuration_and_judge_panel(session: AsyncSession) -> None:
    quota_token = set_current_quota_user_id("clone-user-a")
    try:
        source = await create_challenge(
            ChallengeCreateRequest(
                title="Retail assistant challenge",
                prompt="Build a workflow copilot for retail return processing.",
                iteration_window_seconds=2400,
                minimum_quality_threshold=0.22,
                risk_appetite="balanced",
                complexity_slider=0.66,
                artifact_ttl_override_seconds=7200,
            ),
            _rate_limit=None,
            session=session,
        )

        session.add_all(
            [
                JudgeProfile(
                    challenge_id=source.id,
                    domain="operations",
                    scoring_style="balanced",
                    profile_prompt="Score operational reliability and throughput.",
                    head_judge=True,
                    source_type="inline_json",
                ),
                JudgeProfile(
                    challenge_id=source.id,
                    domain="finance",
                    scoring_style="strict",
                    profile_prompt="Score cost and margin impact.",
                    head_judge=False,
                    source_type="inline_json",
                ),
            ]
        )
        await session.commit()

        cloned = await clone_challenge(
            source.id,
            payload=None,
            _rate_limit=None,
            session=session,
        )
    finally:
        reset_current_quota_user_id(quota_token)

    cloned_challenge = await session.get(Challenge, cloned.id)
    assert cloned.source_challenge_id == source.id
    assert cloned.is_draft is True
    assert cloned.title == "Retail assistant challenge (Draft)"
    assert cloned.cloned_judge_profile_count == 2
    assert cloned_challenge is not None
    assert cloned_challenge.id != source.id
    assert cloned_challenge.prompt == source.prompt
    assert cloned_challenge.iteration_window_seconds == source.iteration_window_seconds
    assert cloned_challenge.minimum_quality_threshold == source.minimum_quality_threshold
    assert cloned_challenge.risk_appetite == source.risk_appetite
    assert cloned_challenge.complexity_slider == source.complexity_slider
    assert cloned_challenge.artifact_ttl_override_seconds == source.artifact_ttl_override_seconds

    source_judges_stmt: Select[tuple[JudgeProfile]] = (
        select(JudgeProfile).where(JudgeProfile.challenge_id == source.id).order_by(JudgeProfile.domain.asc())
    )
    cloned_judges_stmt: Select[tuple[JudgeProfile]] = (
        select(JudgeProfile).where(JudgeProfile.challenge_id == cloned.id).order_by(JudgeProfile.domain.asc())
    )
    source_judges = (await session.execute(source_judges_stmt)).scalars().all()
    cloned_judges = (await session.execute(cloned_judges_stmt)).scalars().all()
    assert [(row.domain, row.scoring_style, row.profile_prompt, row.head_judge, row.source_type) for row in cloned_judges] == [
        (row.domain, row.scoring_style, row.profile_prompt, row.head_judge, row.source_type) for row in source_judges
    ]

    usage_stmt: Select[tuple[UserQuotaUsage]] = select(UserQuotaUsage).where(UserQuotaUsage.quota_user_id == "clone-user-a")
    usage = (await session.execute(usage_stmt)).scalar_one()
    assert usage.challenges_created == 2


@pytest.mark.asyncio
async def test_clone_challenge_rejects_unknown_source(session: AsyncSession) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await clone_challenge(
            uuid.uuid4(),
            payload=None,
            _rate_limit=None,
            session=session,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "challenge not found"
